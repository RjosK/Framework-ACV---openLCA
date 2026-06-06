# pyLCAFramework

Un framework nativo en Python orientado a objetos para realizar Análisis de Ciclo de Vida (ACV) interactuando con openLCA vía IPC. Incluye una interfaz gráfica basada en Streamlit.

## Características
* **Conexión IPC Segura:** Verifica si el puerto de openLCA (8080) está disponible antes de conectarse.
* **Carga Optimizada de Materiales:** Lee tu base de datos de referencias en TXT o CSV sin hacer consultas lentas al servidor.
* **Orientado a Objetos:** Modularizado en `core`, `ipc` y `data` para ser fácilmente extensible.
* **Interfaz de Usuario Interactiva:** Crea Flujos, Procesos y arma tu Inventario de Ciclo de Vida con pocos clics en tu navegador local.

## Requisitos
* Python 3.9 o superior
* openLCA 2.x con el servidor IPC activado (por defecto en el puerto 8080)

## Instalación

1. Clona o descarga esta carpeta.
2. Abre una terminal en esta carpeta (`lca_framework`).
3. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```

## Uso

1. Abre **openLCA**.
2. Ve a *Tools > Developer tools > IPC Server* y asegúrate de que esté corriendo en el puerto `8080`.
3. En la terminal, ejecuta la aplicación Streamlit:
   ```bash
   streamlit run app.py
   ```
4. Se abrirá una pestaña en tu navegador web. Utiliza el panel lateral para conectarte y empieza a crear tus procesos ACV.

## Estructura
* `app.py`: La aplicación principal de interfaz (UI).
* `core/builder.py`: Lógica principal (`olca-schema`) para la instanciación y creación de objetos en la DB de openLCA.
* `data/manager.py`: Módulo para la lectura del catálogo de descriptores (ej. `process_descriptors_updated.txt`).
* `ipc/connection.py`: Envoltura segura alrededor de `olca_ipc.Client`.
