import olca_schema as schema
import logging
import uuid
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class ProcessBuilder:
    """
    Se encarga de construir Flujos, Procesos e Intercambios y enviarlos a la base de datos de openLCA vía IPC.
    También maneja la creación de Sistemas de Producto y el cálculo de impacto.
    """
    def __init__(self, ipc_client):
        self.client = ipc_client

    def create_flow(self, name: str, flow_type_str: str, property_name: str) -> Optional[schema.Flow]:
        if not self.client:
            logger.error("No hay conexión con el cliente IPC.")
            return None

        try:
            flow_type = getattr(schema.FlowType, flow_type_str, schema.FlowType.PRODUCT_FLOW)
            
            flow_property_ref = self.client.get(schema.FlowProperty, name=property_name)
            if not flow_property_ref:
                logger.warning(f"Propiedad '{property_name}' no encontrada. Usando Mass por defecto.")
                flow_property_ref = self.client.get(schema.FlowProperty, name="Mass")
            
            if flow_property_ref:
                flow_property_factor = schema.FlowPropertyFactor(
                    flow_property=flow_property_ref,
                    conversion_factor=1.0,
                    is_ref_flow_property=True
                )
                properties = [flow_property_factor]
            else:
                properties = []

            flow = schema.Flow(
                id=str(uuid.uuid4()),
                name=name,
                flow_type=flow_type,
                flow_properties=properties
            )
            
            self.client.put(flow)
            logger.info(f"Flujo '{name}' creado exitosamente con ID {flow.id}")
            return flow

        except Exception as e:
            logger.error(f"Error al crear el flujo '{name}': {e}")
            return None

    def create_process(self, name: str, reference_flow: schema.Flow, unit_name: str = "kg") -> Optional[schema.Process]:
        if not self.client:
            return None

        try:
            process = schema.Process(
                id=str(uuid.uuid4()),
                name=name,
                process_type=schema.ProcessType.UNIT_PROCESS,
                exchanges=[]
            )
            
            # Obtener unidad
            unit_obj = None
            try:
                groups = self.client.get_all(schema.UnitGroup)
                for ug in groups:
                    for u in ug.units:
                        if u.name == unit_name:
                            unit_obj = u
                            break
                    if unit_obj: break
            except:
                pass
            
            ref_exchange = schema.Exchange(
                flow=reference_flow,
                flow_property=schema.Ref(name=reference_flow.name),
                amount=1.0,
                is_input=False,
                is_quantitative_reference=True
            )
            if unit_obj:
                ref_exchange.unit = unit_obj
                
            process.exchanges.append(ref_exchange)
            
            self.client.put(process)
            logger.info(f"Proceso '{process.name}' creado exitosamente con ID {process.id}")
            return process
            
        except Exception as e:
            logger.error(f"Error al crear el proceso '{name}': {e}")
            return None

    def add_exchanges(self, process_id: str, exchanges_data: list) -> int:
        process = self.client.get(schema.Process, process_id)
        if not process:
            logger.warning(f"⚠️ Proceso '{process_id}' no encontrado")
            return 0
        
        existing_flows = [ex.flow.name for ex in process.exchanges] if process.exchanges else []

        for ex_data in exchanges_data:
            provider_id = ex_data.get('Material_ID')
            unit_name = ex_data.get('Unidad', 'kg')
            
            if not provider_id:
                logger.warning("⚠️ Entrada sin Material_ID válido, omitiendo.")
                continue

            # 1. Obtener el Proceso Proveedor Exacto usando el ID
            provider_process = self.client.get(schema.Process, provider_id)
            if not provider_process:
                logger.warning(f"⚠️ Proceso proveedor (ID: {provider_id}) no encontrado en la base de datos.")
                continue

            # 2. Extraer el Flujo de Referencia de ese proceso
            ref_exchange = next((ex for ex in provider_process.exchanges if getattr(ex, 'is_quantitative_reference', False)), None)
            if not ref_exchange or not ref_exchange.flow:
                logger.warning(f"⚠️ El proceso '{provider_process.name}' no tiene flujo de referencia.")
                continue

            flow = ref_exchange.flow
            flow_name = flow.name
            
            if flow_name in existing_flows:
                logger.info(f"🔄 El flujo '{flow_name}' ya está en el proceso, se omite duplicado.")
                continue

            # --- NUEVA LÓGICA: Búsqueda dinámica de la unidad ---
            unit_obj = None
            
            if hasattr(flow, 'reference_flow_property') and flow.reference_flow_property:
                flow_prop = self.client.get(schema.FlowProperty, flow.reference_flow_property.id)
                if flow_prop and hasattr(flow_prop, 'unit_group') and flow_prop.unit_group:
                    unit_group = self.client.get(schema.UnitGroup, flow_prop.unit_group.id)
                    if unit_group:
                        unit_obj = next((u for u in unit_group.units if u.name == unit_name), None)
            
            if not unit_obj:
                for ug_desc in self.client.get_descriptors(schema.UnitGroup):
                    ug = self.client.get(schema.UnitGroup, ug_desc.id)
                    unit_obj = next((u for u in ug.units if u.name == unit_name), None)
                    if unit_obj:
                        break

            if not unit_obj:
                logger.warning(f"⚠️ Error crítico: La unidad '{unit_name}' no existe en openLCA.")
                continue 

            # --- Instanciar y asignar ---
            exchange = schema.Exchange()
            exchange.is_input = ex_data['Es_Entrada']
            exchange.flow = flow
            exchange.flow_property = schema.Ref(name=flow_name)
            exchange.amount = float(ex_data['Cantidad'])
            exchange.is_quantitative_reference = False
            exchange.unit = unit_obj

            # ¡Asignamos el proveedor exacto!
            exchange.default_provider = provider_process

            if not process.exchanges:
                process.exchanges = []
            process.exchanges.append(exchange)
            existing_flows.append(flow_name)

        # Guardar el proceso actualizado
        self.client.put(process)
        logger.info("✅ Inventario guardado exitosamente.")
        return len(exchanges_data)

    def calculate_impact(self, process_id: str, impact_method_id: str) -> List[dict]:
        """
        Crea el product system asociado al proceso y corre el cálculo de impacto.
        """
        if not self.client:
            return []
            
        try:
            process_ref = self.client.get_descriptor(schema.Process, process_id)
            if not process_ref:
                logger.error(f"No se pudo resolver el descriptor del proceso {process_id}")
                return []
                
            config = schema.LinkingConfig(prefer_unit_processes=True, provider_linking=schema.ProviderLinking.PREFER_DEFAULTS)
            product_system_ref = self.client.create_product_system(process_ref, config)
            
            impact_method_ref = self.client.get_descriptor(schema.ImpactMethod, impact_method_id)
            if not impact_method_ref:
                logger.error(f"Método de impacto {impact_method_id} no encontrado.")
                return []

            setup = schema.CalculationSetup(target=product_system_ref, impact_method=impact_method_ref)
            result = self.client.calculate(setup)
            
            state = result.wait_until_ready()
            logger.info(f"Cálculo completado: state {state.id}")
            
            impacts = []
            for impact in result.get_total_impacts():
                impacts.append({
                    "Categoría": impact.impact_category.name,
                    "Cantidad": impact.amount,
                    "Unidad": impact.impact_category.ref_unit
                })
                
            return impacts
        except Exception as e:
            logger.error(f"Error en el cálculo: {e}")
            return []
