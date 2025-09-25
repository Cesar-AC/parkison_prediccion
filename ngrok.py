import subprocess
import time
import os
from pathlib import Path
from pyngrok import ngrok, conf

# ==========================================================
#  ngrok launcher para la app Streamlit
#  Lee NGROK_AUTH_TOKEN desde .env o variables del sistema.
# ==========================================================

STREAMLIT_APP = "app.py"  # Nombre del archivo principal de Streamlit

def _load_dotenv():
    """Carga sencilla de .env (KEY=VALUE) sin dependencias externas.
    Solo establece claves que aún no existen en el entorno.
    """
    env_path = Path(__file__).resolve().parent / '.env'
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            k = k.strip(); v = v.strip()
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception:
        pass  # No romper si hay un formato raro.

_load_dotenv()

NGROK_AUTH_TOKEN = os.getenv("NGROK_AUTH_TOKEN")
if NGROK_AUTH_TOKEN:
    conf.get_default().auth_token = NGROK_AUTH_TOKEN
else:
    print("[Aviso] NGROK_AUTH_TOKEN no encontrado. Usando modo anónimo (más límites). Añádelo a .env si deseas más estabilidad.")

# --- CIERRA TÚNELES PREVIOS (si los hay) ---
ngrok.kill()  # Cierra posibles túneles abiertos previos

# --- LANZA STREAMLIT COMO SUBPROCESO ---
cmd = [
    "streamlit", "run", STREAMLIT_APP,
    "--server.port", "8501",
    "--server.address", "0.0.0.0",
    "--server.enableCORS", "false",
    "--server.enableXsrfProtection", "false"
]
# OPCIONAL: log a archivo
logfile = open("streamlit_logs.txt", "w")
proc = subprocess.Popen(cmd, stdout=logfile, stderr=logfile)

# --- ESPERA QUE INICIE ---
time.sleep(4)

# --- ABRE EL TÚNEL ---
public_url = ngrok.connect(8501, "http")
print("\n🚀 Tu aplicación está disponible en:", public_url)

# --- OPCIONAL: Mantén la app viva hasta que la detengas ---
try:
    while True:
        time.sleep(60)
except KeyboardInterrupt:
    print("Cerrando app y túnel ngrok...")
    ngrok.kill()
    proc.terminate()
