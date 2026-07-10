"""
Diagnóstico completo do servidor IA.

Verifica: hardware (RAM/disco/CPU), Ollama, modelo, servidor Flask,
porta, firewall, rede/ethernet, Task Scheduler e saúde dos logs.

Uso:
    python diagnostico.py              # relatório completo no console
    python diagnostico.py --salvar     # também salva .txt e .json em logs/diagnosticos/
    python diagnostico.py --json       # imprime só o JSON (para automação)
"""

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

RAIZ = Path(__file__).parent.resolve()
sys.path.insert(0, str(RAIZ))

from config import (  # noqa: E402
    OLLAMA_URL_TAGS, MODELO, HOST, PORTA,
    PASTA_LOGS, PASTA_DADOS, ARQUIVO_MEMORIA, ARQUIVO_LOG,
)

try:
    import psutil
    TEM_PSUTIL = True
except ImportError:
    TEM_PSUTIL = False

WINDOWS = sys.platform == "win32"

# Requisitos mínimos para deepseek-coder-v2:16b (Q4)
RAM_MINIMA_GB = 10
DISCO_MINIMO_GB = 5
NOME_TAREFA = "IA_Servidor_Autostart"

# ---------- Cores ANSI (com fallback) ----------
class Cor:
    OK = "\033[92m"
    WARN = "\033[93m"
    ERRO = "\033[91m"
    INFO = "\033[94m"
    RESET = "\033[0m"
    NEGRITO = "\033[1m"


def _habilitar_ansi_windows():
    if WINDOWS:
        os.system("")  # truque: ativa processamento VT100 no cmd moderno


_habilitar_ansi_windows()

SIMBOLOS = {"ok": "✅", "warn": "⚠️ ", "erro": "❌", "info": "ℹ️ "}
CORES = {"ok": Cor.OK, "warn": Cor.WARN, "erro": Cor.ERRO, "info": Cor.INFO}

resultados = []  # lista de dicts para o relatório final


def checar(nome: str, nivel: str, detalhe: str = ""):
    """Registra um resultado e imprime formatado."""
    resultados.append({"item": nome, "nivel": nivel, "detalhe": detalhe})
    cor = CORES.get(nivel, "")
    simbolo = SIMBOLOS.get(nivel, "•")
    linha = f"  {simbolo} {nome}"
    if detalhe:
        linha += f" — {detalhe}"
    print(f"{cor}{linha}{Cor.RESET}")


def secao(titulo: str):
    print(f"\n{Cor.NEGRITO}{'─' * 60}{Cor.RESET}")
    print(f"{Cor.NEGRITO}{titulo}{Cor.RESET}")
    print(f"{Cor.NEGRITO}{'─' * 60}{Cor.RESET}")


def rodar(cmd: list, timeout=10) -> tuple:
    """Roda comando e retorna (codigo, stdout, stderr)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return -1, "", str(e)


# ============================================================
# 1. HARDWARE
# ============================================================
def diagnosticar_hardware():
    secao("1. HARDWARE")

    if TEM_PSUTIL:
        # RAM
        mem = psutil.virtual_memory()
        total_gb = mem.total / (1024 ** 3)
        disponivel_gb = mem.available / (1024 ** 3)
        uso_pct = mem.percent

        nivel = "ok" if disponivel_gb >= RAM_MINIMA_GB else (
            "warn" if disponivel_gb >= RAM_MINIMA_GB * 0.7 else "erro"
        )
        checar(
            "Memória RAM",
            nivel,
            f"{disponivel_gb:.1f} GB livres de {total_gb:.1f} GB ({uso_pct:.0f}% em uso) "
            f"— mínimo recomendado: {RAM_MINIMA_GB} GB",
        )

        # CPU
        nucleos_fisicos = psutil.cpu_count(logical=False)
        nucleos_logicos = psutil.cpu_count(logical=True)
        uso_cpu = psutil.cpu_percent(interval=1)
        checar(
            "CPU",
            "ok" if uso_cpu < 85 else "warn",
            f"{nucleos_fisicos} núcleos físicos / {nucleos_logicos} threads, uso atual: {uso_cpu:.0f}%",
        )

        # Disco (drive onde o projeto está)
        disco = psutil.disk_usage(str(RAIZ.anchor))
        livre_gb = disco.free / (1024 ** 3)
        nivel_disco = "ok" if livre_gb >= DISCO_MINIMO_GB else "erro"
        checar(
            "Espaço em disco",
            nivel_disco,
            f"{livre_gb:.1f} GB livres em {RAIZ.anchor} — mínimo: {DISCO_MINIMO_GB} GB",
        )

        # Processos relevantes (memória usada por ollama/python)
        for proc in psutil.process_iter(["name", "memory_info", "pid"]):
            try:
                nome = (proc.info["name"] or "").lower()
                if "ollama" in nome:
                    mb = proc.info["memory_info"].rss / (1024 ** 2)
                    checar(f"Processo {proc.info['name']} (PID {proc.info['pid']})", "info", f"{mb:.0f} MB em uso")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    else:
        checar(
            "psutil não instalado",
            "warn",
            "Instale com: pip install psutil — checagens de hardware limitadas",
        )
        # fallback simples de disco (stdlib)
        import shutil as _sh
        uso = _sh.disk_usage(str(RAIZ.anchor))
        livre_gb = uso.free / (1024 ** 3)
        checar(
            "Espaço em disco",
            "ok" if livre_gb >= DISCO_MINIMO_GB else "erro",
            f"{livre_gb:.1f} GB livres",
        )


# ============================================================
# 2. AMBIENTE PYTHON
# ============================================================
def diagnosticar_python():
    secao("2. AMBIENTE PYTHON")

    versao = sys.version.split()[0]
    ok_versao = sys.version_info >= (3, 10)
    checar("Versão do Python", "ok" if ok_versao else "warn", f"{versao} (recomendado: 3.10+)")

    checar("Interpretador", "info", sys.executable)

    # Verifica dependências do requirements.txt
    req_file = RAIZ / "requirements.txt"
    if not req_file.exists():
        checar("requirements.txt", "warn", "arquivo não encontrado")
        return

    pacotes = []
    for linha in req_file.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#"):
            pacotes.append(re.split(r"[=<>]", linha)[0].strip())

    faltando = []
    for pacote in pacotes:
        try:
            __import__(pacote.replace("-", "_"))
        except ImportError:
            # alguns nomes de import diferem do nome do pacote pip
            nomes_alt = {"flask-cors": "flask_cors"}
            alt = nomes_alt.get(pacote)
            if alt:
                try:
                    __import__(alt)
                    continue
                except ImportError:
                    pass
            faltando.append(pacote)

    if faltando:
        checar("Dependências", "erro", f"faltando: {', '.join(faltando)} — rode: pip install -r requirements.txt")
    else:
        checar("Dependências", "ok", f"{len(pacotes)} pacotes verificados, todos presentes")


# ============================================================
# 3. OLLAMA
# ============================================================
def diagnosticar_ollama():
    secao("3. OLLAMA")

    # Processo rodando
    if WINDOWS:
        codigo, saida, _ = rodar(["tasklist", "/FI", "IMAGENAME eq ollama.exe"])
        rodando = "ollama.exe" in saida
    else:
        codigo, saida, _ = rodar(["pgrep", "-f", "ollama"])
        rodando = codigo == 0

    checar("Processo ollama", "ok" if rodando else "erro", "em execução" if rodando else "não encontrado")

    # API respondendo
    online = False
    latencia = None
    try:
        t0 = time.time()
        r = requests.get(OLLAMA_URL_TAGS, timeout=5)
        latencia = (time.time() - t0) * 1000
        online = r.status_code == 200
    except requests.RequestException as e:
        checar("API do Ollama", "erro", f"sem resposta ({e.__class__.__name__})")

    if online:
        checar("API do Ollama", "ok", f"respondendo em {latencia:.0f}ms")

        # Modelos instalados
        try:
            modelos = [m["name"] for m in r.json().get("models", [])]
        except (ValueError, KeyError):
            modelos = []

        if modelos:
            checar("Modelos instalados", "info", ", ".join(modelos))
        else:
            checar("Modelos instalados", "warn", "nenhum modelo baixado")

        base_desejado = MODELO.split(":")[0]
        tem_modelo = any(m.split(":")[0] == base_desejado