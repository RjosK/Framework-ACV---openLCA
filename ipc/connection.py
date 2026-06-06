import olca_ipc as ipc
import logging
import socket

logger = logging.getLogger(__name__)

class OpenLCAConnection:
    """
    Gestiona la conexión con el servidor IPC de openLCA.
    """
    def __init__(self, port: int = 8080):
        self.port = port
        self.client = None

    def is_server_running(self) -> bool:
        """Comprueba si el puerto local está respondiendo."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            try:
                s.connect(('127.0.0.1', self.port))
                return True
            except (ConnectionRefusedError, socket.timeout):
                return False

    def connect(self) -> bool:
        """Establece la conexión con el cliente IPC de openLCA."""
        if not self.is_server_running():
            logger.error(f"El servidor IPC no está respondiendo en el puerto {self.port}. ¿Está openLCA abierto y el servidor IPC activo?")
            return False
            
        try:
            self.client = ipc.Client(self.port)
            logger.info(f"Conectado exitosamente a openLCA en el puerto {self.port}")
            return True
        except Exception as e:
            logger.error(f"Error al conectar con openLCA: {e}")
            self.client = None
            return False

    def get_client(self) -> ipc.Client:
        """Devuelve el cliente IPC activo."""
        return self.client
