"""
Configuração central do servidor IA.
Todos os valores podem ser sobrescritos via variáveis de ambiente.
"""

import os
from pathlib import Path


def _env(chave: str, padrao: str) -> str:
    return os.getenv(chave, padrao)


def _env_int(chave: str, padrao: int) -> int:
    try:
        return int(os.getenv(chave, str(padrao)))
    except ValueError:
        return padrao


def _env_float(chave: str, padrao: float) -> float:
    try:
        return float(os.getenv(chave, str(padrao)))
    except ValueError:
        return padrao


# Caminhos
RAIZ = Path(__file__).parent.resolve()
PASTA_WEB = RAIZ / "web"
PASTA_DADOS = RAIZ / "dados"
PASTA_LOGS = RAIZ / "logs"

PASTA_DADOS.mkdir(exist_ok=True)
PASTA_LOGS.mkdir(exist_ok=True)

ARQUIVO_MEMORIA = PASTA_DADOS / "memoria.json"
ARQUIVO_LOG = PASTA_LOGS / "servidor.log"

# Ollama 
OLLAMA_HOST = _env("OLLAMA_HOST", "localhost")
OLLAMA_PORT = _env_int("OLLAMA_PORT", 11434)
OLLAMA_BASE = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"
OLLAMA_URL_CHAT = f"{OLLAMA_BASE}/api/chat"
OLLAMA_URL_TAGS = f"{OLLAMA_BASE}/api/tags"

MODELO = _env("IA_MODELO", "deepseek-coder-v2:16b")

# Parâmetros de inferência
NUM_CTX = _env_int("IA_NUM_CTX", 8192)       # baixe p/ 4096 se faltar RAM
NUM_PREDICT = _env_int("IA_NUM_PREDICT", 2048)
TEMPERATURA = _env_float("IA_TEMPERATURA", 0.3)  # baixa = mais preciso p/ código
TOP_P = _env_float("IA_TOP_P", 0.9)

# Timeouts e retry
TIMEOUT_CONEXAO = _env_int("IA_TIMEOUT_CONEXAO", 10)
TIMEOUT_LEITURA = _env_int("IA_TIMEOUT_LEITURA", 600)  # streaming longo
MAX_TENTATIVAS = _env_int("IA_MAX_TENTATIVAS", 3)
BACKOFF_BASE = _env_float("IA_BACKOFF_BASE", 1.5)

# ---------- Servidor ----------
# 0.0.0.0 = escuta em todas as interfaces
HOST = _env("IA_HOST", "0.0.0.0")
PORTA = _env_int("IA_PORTA", 5000)
DEBUG = _env("IA_DEBUG", "false").lower() == "true"

# IPs permitidos na LAN (CORS). Vazio = permite qualquer origem da rede local.
ORIGENS_PERMITIDAS = _env("IA_ORIGENS", "*")

# Memória
LIMITE_MENSAGENS = _env_int("IA_LIMITE_MENSAGENS", 40)
CONTEXTO_MENSAGENS = _env_int("IA_CONTEXTO_MENSAGENS", 12)

# System prompt
SYSTEM_PROMPT = _env(
    "IA_SYSTEM_PROMPT",
    "Você é um assistente de programação especializado. "
    "Responda em português. Seja direto e preciso. "
    "Ao mostrar código, use blocos de código com a linguagem indicada."
)