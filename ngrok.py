import subprocess
import time
from pyngrok import ngrok, conf

# CONFIGURA TU TOKEN AQUÍ
NGROK_AUTH_TOKEN = "2z4EnVUZMa4H6gDPsWp5Z59eGUt_49BX1fJ2HwbaxkENYNcNJ"

# NOMBRE DE TU APP STREAMLIT
STREAMLIT_APP = "app.py"

# --- CONFIGURACIÓN NGROK ---
conf.get_default().auth_token = NGROK_AUTH_TOKEN

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
