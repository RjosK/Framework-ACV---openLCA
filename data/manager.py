import pandas as pd
import logging
from typing import List

logger = logging.getLogger(__name__)

class MaterialManager:
    """
    Gestiona la carga y búsqueda de materiales a partir de una base de datos local (TXT/CSV).
    Esto permite una interfaz de usuario rápida sin depender de búsquedas pesadas vía IPC.
    """
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.materials_df = pd.DataFrame()
        self.material_names = []
        self._load_data()

    def _load_data(self):
        """Carga el archivo local de materiales."""
        try:
            self.materials_df = pd.read_csv(
                self.db_path, sep='\t', names=['id', 'nombre', 'categoria', 'unidad'],
                header=None, on_bad_lines='skip', dtype=str
            )
            # Limpiar posible encabezado
            if not self.materials_df.empty and str(self.materials_df.iloc[0]['id']).lower() == 'id':
                self.materials_df = self.materials_df.iloc[1:]
                
            # Procesar la columna 'nombre' que tiene formato: Proveedor | Material | Base de datos
            display_names = []
            for _, row in self.materials_df.iterrows():
                raw_name = str(row['nombre'])
                parts = [p.strip() for p in raw_name.split('|')]
                
                provider = parts[0] if len(parts) > 0 else "N/A"
                material = parts[1] if len(parts) > 1 else raw_name
                
                cat = str(row['categoria'])
                # Eliminamos la categoría del string visual para evitar confundirla con la ubicación.
                display_str = f"{provider} || {material} || {row['id']}"
                display_names.append(display_str)
                
            self.materials_df['display_name'] = display_names
            self.material_names = self.materials_df['display_name'].tolist()
            
            logger.info(f"Base local cargada exitosamente: {len(self.material_names)} materiales listos.")
        except Exception as e:
            logger.error(f"Error al cargar el archivo de materiales ({self.db_path}): {e}")

    def get_all_names(self) -> List[str]:
        """Devuelve la lista de todos los nombres de materiales únicos."""
        return self.material_names

    def search_materials(self, term: str, limit: int = 50) -> List[str]:
        """Busca materiales por nombre (case-insensitive)."""
        if not term:
            return self.material_names[:limit]
        
        term = term.lower()
        matches = [name for name in self.material_names if term in name.lower()]
        return matches[:limit]

    def get_material_info(self, display_name: str) -> dict:
        """Devuelve información detallada dado el string de display."""
        if self.materials_df.empty:
            return {}
            
        row = self.materials_df[self.materials_df['display_name'] == display_name]
        if not row.empty:
            return row.iloc[0].to_dict()
        return {}

    def append_custom_process(self, process_id: str, name: str, unit: str = "kg"):
        """Añade un nuevo proceso creado por el usuario al archivo local para futuros ensambles."""
        # Formato: id \t nombre \t categoria \t unidad
        # nombre = Usuario | {name} | Custom DB
        line = f"{process_id}\tUsuario | {name} | Custom DB\tMis Procesos / Ensambles\t{unit}\n"
        try:
            with open(self.db_path, 'a', encoding='utf-8') as f:
                f.write(line)
            # Recargar memoria para que aparezca inmediatamente en el dropdown
            self._load_data()
            logger.info(f"Proceso {name} (ID: {process_id}) agregado a la base de datos local.")
        except Exception as e:
            logger.error(f"Error al guardar el proceso personalizado: {e}")
