import streamlit as st
import pandas as pd
import olca_schema as schema
from ipc.connection import OpenLCAConnection
from data.manager import MaterialManager
from core.builder import ProcessBuilder

st.set_page_config(page_title="openLCA Python Framework", page_icon="🌱", layout="wide")

if 'ipc_connected' not in st.session_state:
    st.session_state.ipc_connected = False
if 'exchanges' not in st.session_state:
    st.session_state.exchanges = []
if 'connection' not in st.session_state:
    st.session_state.connection = OpenLCAConnection(port=8080)
if 'material_manager' not in st.session_state:
    db_path = '../process_descriptors_updated.txt' 
    st.session_state.material_manager = MaterialManager(db_path=db_path)
if 'impact_methods' not in st.session_state:
    st.session_state.impact_methods = []
if 'providers' not in st.session_state:
    st.session_state.providers = []
if 'units' not in st.session_state:
    st.session_state.units = []
if 'last_process_id' not in st.session_state:
    st.session_state.last_process_id = None

with st.sidebar:
    st.header("⚙️ Conexión openLCA")
    st.write("Puerto configurado: 8080")
    
    if st.button("Conectar a openLCA"):
        with st.spinner("Conectando..."):
            success = st.session_state.connection.connect()
            st.session_state.ipc_connected = success
            if success:
                # Precargar métodos de impacto desde openLCA
                try:
                    client = st.session_state.connection.get_client()
                    
                    # 1. Cargar Métodos de Impacto
                    methods = client.get_descriptors(schema.ImpactMethod)
                    st.session_state.impact_methods = [{"name": m.name, "id": m.id} for m in methods]
                    
                    # 2. (Removido) Ya no cargamos TODOS los procesos, lo haremos dinámicamente por flujo.
                    
                    # 3. Cargar Unidades
                    unit_groups = client.get_all(schema.UnitGroup)
                    all_units = []
                    for ug in unit_groups:
                        for u in ug.units:
                            all_units.append(u.name)
                    st.session_state.units = sorted(list(set(all_units)))
                    
                except Exception as e:
                    st.error(f"Error al cargar catálogos desde openLCA: {e}")
            
    if st.session_state.ipc_connected:
        st.success("Conectado exitosamente")
    else:
        st.error("No conectado")

st.title("Framework Generativo ACV - openLCA")

if not st.session_state.ipc_connected:
    st.warning("Conéctate usando la barra lateral para sincronizar datos.")

st.header("1. Definición del Producto (Reference Flow)")
col1, col2, col3 = st.columns(3)
with col1:
    product_name = st.text_input("Nombre del Producto/Proceso", placeholder="Ej. P3HT Purificado")
with col2:
    flow_type = st.selectbox("Tipo de Flujo", ["PRODUCT_FLOW", "WASTE_FLOW", "ELEMENTARY_FLOW"])
with col3:
    flow_property = st.selectbox("Propiedad de Referencia", ["Mass", "Item", "Energy", "Volume"])

st.markdown("---")

st.header("2. Inventario del Proceso (Intercambios)")
search_term = st.text_input("🔍 Buscar material (flujo) en base de datos local:", "")
filtered_materials = st.session_state.material_manager.search_materials(search_term, limit=30)

col_m1, col_m2, col_m3, col_m4 = st.columns([4, 1, 1, 1])
with col_m1:
    selected_display = st.selectbox("Flujo / Proveedor", filtered_materials)
with col_m2:
    amount = st.number_input("Cantidad", value=1.0, min_value=0.0, format="%.4f")
with col_m3:
    # Desplegable de unidades cargadas
    unit_options = st.session_state.units if st.session_state.units else ["kg", "Item(s)", "MJ"]
    
    # Intentar obtener la unidad por defecto del txt
    default_unit_idx = 0
    if selected_display:
        mat_info = st.session_state.material_manager.get_material_info(selected_display)
        txt_unit = str(mat_info.get('unidad', '')).strip()
        
        if txt_unit and txt_unit.lower() != "nan":
            # Buscar coincidencia en las opciones
            found = False
            for i, u in enumerate(unit_options):
                if u.lower() == txt_unit.lower():
                    default_unit_idx = i
                    found = True
                    break
            
            # Si no se encontró, añadirla a la lista de opciones
            if not found and txt_unit not in unit_options:
                unit_options.append(txt_unit)
                default_unit_idx = len(unit_options) - 1

    unit = st.selectbox("Unidad", unit_options, index=default_unit_idx)
with col_m4:
    io_type = st.selectbox("Dirección", ["Entrada", "Salida"])

if st.button("➕ Añadir al Inventario"):
    if selected_display:
        mat_info = st.session_state.material_manager.get_material_info(selected_display)
        mat_id = mat_info.get('id', '')
        
        # Separar el string rico para mostrar columnas limpias en la tabla
        parts = selected_display.split(" || ")
        provider = parts[0] if len(parts) > 0 else ""
        material = parts[1] if len(parts) > 1 else ""
        
        # Consultar la ubicación real desde openLCA usando el ID (si está conectado)
        ubicacion = "No especificada"
        try:
            if st.session_state.ipc_connected:
                client = st.session_state.connection.get_client()
                provider_process = client.get(schema.Process, mat_id)
                if provider_process and provider_process.location:
                    ubicacion = provider_process.location.name
        except Exception as e:
            print(f"No se pudo obtener la ubicación para {mat_id}: {e}")
        
        st.session_state.exchanges.append({
            "Proveedor": provider,
            "Material": material,
            "Ubicación": ubicacion,
            "ID": mat_id,
            "Cantidad": amount,
            "Unidad": unit,
            "Es_Entrada": True if io_type == "Entrada" else False,
            "Material_ID": mat_id  # Oculto para la lógica del backend
        })
        st.success("Añadido exitosamente al inventario")

if st.session_state.exchanges:
    # Mostramos el dataframe pero ocultamos la columna Material_ID para no duplicar el ID visualmente
    df_exchanges = pd.DataFrame(st.session_state.exchanges)
    st.dataframe(df_exchanges.drop(columns=['Material_ID']), use_container_width=True)
    if st.button("🗑️ Limpiar Inventario"):
        st.session_state.exchanges = []
        st.rerun()

st.markdown("---")

st.header("3. Ejecución y Cálculo")
if st.button("🚀 Crear y Enviar a openLCA", type="primary"):
    if not st.session_state.ipc_connected:
        st.error("Debes conectarte a openLCA primero.")
    elif not product_name:
        st.error("Debes especificar el nombre del producto.")
    else:
        with st.spinner("Construyendo en openLCA..."):
            client = st.session_state.connection.get_client()
            builder = ProcessBuilder(client)
            
            flow = builder.create_flow(product_name, flow_type, flow_property)
            if flow:
                process = builder.create_process(product_name, flow)
                if process:
                    success_count = builder.add_exchanges(process.id, st.session_state.exchanges)
                    if success_count > 0:
                        st.success(f"¡Proceso '{product_name}' creado exitosamente con {success_count}/{len(st.session_state.exchanges)} intercambios!")
                        
                        # 4. Guardar el nuevo proceso en la base local para futuros ensambles
                        st.session_state.material_manager.append_custom_process(process.id, product_name, "kg")
                    else:
                        st.warning(f"El proceso se creó pero hubo un problema agregando los intercambios.")
                    st.session_state.last_process_id = process.id
                else:
                    st.error("Hubo un error al crear el proceso.")

if st.session_state.last_process_id:
    st.markdown("### Calcular Impactos")
    
    # Preparar opciones del dropdown (priorizando el que diste: 61966689-76aa-4b3b-94f1-81989199433f)
    # Si logramos cargarlos dinámicamente, los usamos. Si no, mostramos un campo libre.
    method_options = {}
    if st.session_state.impact_methods:
        method_options = {m['name']: m['id'] for m in st.session_state.impact_methods}
    else:
        method_options = {"Default Method (ID)": "61966689-76aa-4b3b-94f1-81989199433f"}

    selected_method_name = st.selectbox("Selecciona un Método de Impacto:", list(method_options.keys()))
    
    if st.button("🧪 Calcular Resultados"):
        with st.spinner("Creando Product System y calculando..."):
            client = st.session_state.connection.get_client()
            builder = ProcessBuilder(client)
            
            method_id = method_options[selected_method_name]
            results = builder.calculate_impact(st.session_state.last_process_id, method_id)
            
            if results:
                st.success("Cálculo completado exitosamente.")
                df_results = pd.DataFrame(results)
                st.dataframe(df_results, use_container_width=True)
            else:
                st.error("Hubo un error durante el cálculo de impacto o la vinculación del sistema.")
