import os
from pathlib import Path

PASTA_RAIZ= Path (__file__).parent.parent
PASTA_DATA= PASTA_RAIZ / "data"
PASTA_DATA.mkdir(exist_ok=True)

OLLAMA_HOST = #IP servidor
OLLAMA_PORT = 11434
OLLAMA_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/generate"

MODELO_PRINCIPAL = "Deepseek-coder-v2:lite"

TIMEOUT_OLLAMA = 600 #tempo limite para resposta do modelo mais pesado

