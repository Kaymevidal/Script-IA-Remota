"""
Watchdog de inicialização headless.

Fluxo:
  1. Verifica se o Ollama já está rodando; se não, inicia detached.
  2. Aguarda o Ollama ficar online (com timeout).
  3. Inicia o servidor (main.py) detached, sem janela de console.
  4. Monitora os dois processos periodicamente; reinicia o que cair.

Pensado para ser chamado pelo Task Scheduler no boot do Windows,
sem usuário logado (sessão 0 / non-interactive).
"""

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

RAIZ = Path(__file__).parent.resolve()
sys.path.insert(0, str(RAIZ))

from config import OLLAMA_URL_TAGS, HOST, PORTA, PASTA_LOGS  # noqa: E402

# Arquivos de controle
PASTA_LOGS.mkdir(exist_ok=True)
LOG_AUTOSTART = PASTA_LOGS / "autostart.log"
PID_OLLAMA = PASTA_LOGS / "ollama.pid"
PID_SERVIDOR = PASTA_LOGS / "servidor.pid"
STATUS_JSON = PASTA_LOGS / "autostart_status.json"

# Parâmetros
TIMEOUT_OLLAMA_ONLINE = 90     # segundos esperando o Ollama subir
INTERVALO_MONITOR = 15         # segundos entre checagens
MAX_REINICIOS_HORA = 5         # protege contra crash-loop


def log(msg: str):
    linha = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {msg}"
    print(linha, flush=True)
    with open(LOG_AUTOSTART, "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def salvar_status(**kwargs):
    dados = {}
    if STATUS_JSON.exists():
        try:
            dados = json.loads(STATUS_JSON.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    dados.update(kwargs)
    dados["atualizado"] = datetime.now().isoformat()
    STATUS_JSON.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")


# Localizar executáveis
def localizar_ollama() -> str:
    """Procura ollama.exe nos locais padrão de instalação no Windows."""
    candidatos = [
        shutil.which("ollama"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe"),
        os.path.expandvars(r"%ProgramFiles%\Ollama\ollama.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Ollama\ollama.exe"),
    ]
    for c in candidatos:
        if c and Path(c).exists():
            return c
    raise FileNotFoundError(
        "ollama.exe não encontrado. Instale em https://ollama.ai ou "
        "ajuste localizar_ollama() com o caminho correto."
    )


# Processos detached (sem janela, sobrevive ao fechar o pai)
FLAGS_DETACHED = (
    subprocess.CREATE_NEW_PROCESS_GROUP
    | subprocess.DETACHED_PROCESS
    | subprocess.CREATE_NO_WINDOW
) if sys.platform == "win32" else 0


def processo_vivo(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        r = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True, text=True
        )
        return str(pid) in r.stdout
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def ler_pid(arquivo: Path) -> int:
    try:
        return int(arquivo.read_text().strip())
    except (FileNotFoundError, ValueError):
        return -1


def escrever_pid(arquivo: Path, pid: int):
    arquivo.write_text(str(pid), encoding="utf-8")


# Ollama
def ollama_online() -> bool:
    try:
        r = requests.get(OLLAMA_URL_TAGS, timeout=5)
        return r.status_code == 200
    except requests.RequestException:
        return False


def iniciar_ollama():
    if ollama_online():
        log("Ollama já está online.")
        return

    pid_salvo = ler_pid(PID_OLLAMA)
    if processo_vivo(pid_salvo):
        log(f"Processo Ollama (PID {pid_salvo}) já rodando, aguardando ficar online...")
    else:
        exe = localizar_ollama()
        log(f"Iniciando Ollama: {exe} serve")
        log_out = open(PASTA_LOGS / "ollama_stdout.log", "a", encoding="utf-8")
        proc = subprocess.Popen(
            [exe, "serve"],
            stdout=log_out, stderr=subprocess.STDOUT,
            creationflags=FLAGS_DETACHED,
            close_fds=True,
        )
        escrever_pid(PID_OLLAMA, proc.pid)
        log(f"Ollama iniciado (PID {proc.pid}).")

    log(f"Aguardando Ollama ficar online (timeout {TIMEOUT_OLLAMA_ONLINE}s)...")
    inicio = time.time()
    while time.time() - inicio < TIMEOUT_OLLAMA_ONLINE:
        if ollama_online():
            log("Ollama está online.")
            salvar_status(ollama="online")
            return
        time.sleep(2)

    salvar_status(ollama="timeout")
    raise TimeoutError("Ollama não ficou online dentro do timeout.")


# Servidor Flask/Waitress
def servidor_respondendo() -> bool:
    try:
        r = requests.get(f"http://127.0.0.1:{PORTA}/api/status", timeout=5)
        return r.status_code == 200
    except requests.RequestException:
        return False


def iniciar_servidor():
    if servidor_respondendo():
        log("Servidor já está respondendo.")
        return

    pid_salvo = ler_pid(PID_SERVIDOR)
    if processo_vivo(pid_salvo):
        log(f"Processo do servidor (PID {pid_salvo}) já existe, mas não responde. Encerrando...")
        try:
            subprocess.run(["taskkill", "/PID", str(pid_salvo), "/F"], capture_output=True)
        except Exception:
            pass

    python_exe = sys.executable  # usa o mesmo interpretador (venv incluso, se houver)
    main_py = RAIZ / "main.py"

    log(f"Iniciando servidor: {python_exe} {main_py}")
    log_out = open(PASTA_LOGS / "servidor_stdout.log", "a", encoding="utf-8")
    proc = subprocess.Popen(
        [python_exe, str(main_py)],
        stdout=log_out, stderr=subprocess.STDOUT,
        cwd=str(RAIZ),
        creationflags=FLAGS_DETACHED,
        close_fds=True,
    )
    escrever_pid(PID_SERVIDOR, proc.pid)
    log(f"Servidor iniciado (PID {proc.pid}). Aguardando responder...")

    inicio = time.time()
    while time.time() - inicio < 30:
        if servidor_respondendo():
            log(f"Servidor respondendo em http://{HOST}:{PORTA}")
            salvar_status(servidor="online", pid=proc.pid)
            return
        time.sleep(2)

    salvar_status(servidor="timeout")
    log("AVISO: servidor não respondeu dentro do timeout esperado (ver servidor_stdout.log).")


# Loop de monitoramento
def monitorar():
    log("Entrando em modo de monitoramento contínuo...")
    reinicios_recentes = []

    while True:
        agora = time.time()
        reinicios_recentes = [t for t in reinicios_recentes if agora - t < 3600]

        problema = False

        if not ollama_online():
            log("Ollama caiu. Tentando reiniciar...")
            problema = True
            try:
                iniciar_ollama()
            except Exception as e:
                log(f"Falha ao reiniciar Ollama: {e}")

        if not servidor_respondendo():
            log("Servidor não está respondendo. Tentando reiniciar...")
            problema = True
            try:
                iniciar_servidor()
            except Exception as e:
                log(f"Falha ao reiniciar servidor: {e}")

        if problema:
            reinicios_recentes.append(agora)
            salvar_status(ultimo_reinicio=datetime.now().isoformat())
            if len(reinicios_recentes) > MAX_REINICIOS_HORA:
                log(f"ALERTA: mais de {MAX_REINICIOS_HORA} reinícios na última hora. "
                    f"Possível crash-loop. Continuando monitoramento mesmo assim.")
        else:
            salvar_status(ollama="online", servidor="online")

        time.sleep(INTERVALO_MONITOR)


def main():
    log("=" * 60)
    log("AUTOSTART HEADLESS — iniciando")
    log("=" * 60)

    try:
        iniciar_ollama()
    except Exception as e:
        log(f"ERRO CRÍTICO ao iniciar Ollama: {e}")
        salvar_status(erro=str(e))
        # segue para o monitor mesmo assim — ele tentará de novo no loop

    try:
        iniciar_servidor()
    except Exception as e:
        log(f"ERRO ao iniciar servidor: {e}")

    monitorar()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Encerrado manualmente.")