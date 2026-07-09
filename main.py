"""
Entry point. Tenta usar waitress (produção); cai para Flask dev se ausente.
"""

import sys

from config import HOST, PORTA, DEBUG, MODELO
from logger import log


def main():
    from server import app, ollama, memoria  # noqa: importa app já configurado

    log.info("=" * 60)
    log.info("SERVIDOR IA — boot")
    log.info("Escutando em %s:%d | Modelo: %s", HOST, PORTA, MODELO)

    if not ollama.online():
        log.warning("Ollama OFFLINE. Inicie com: ollama serve")
    elif not ollama.modelo_disponivel():
        log.warning("Modelo ausente. Baixe: ollama pull %s", MODELO)
    else:
        log.info("Ollama OK, modelo disponível. Memória: %d msgs", memoria.total())

    log.info("=" * 60)

    if DEBUG:
        log.info("Modo DEBUG — usando servidor de desenvolvimento Flask")
        app.run(host=HOST, port=PORTA, debug=True, threaded=True)
        return

    try:
        from waitress import serve
        log.info("Servindo com waitress (produção)")
        # threads: nº de requisições simultâneas; channel_timeout alto p/ streaming
        serve(app, host=HOST, port=PORTA, threads=8, channel_timeout=1200)
    except ImportError:
        log.warning("waitress não instalado — caindo para Flask dev. "
                    "Instale com: pip install waitress")
        app.run(host=HOST, port=PORTA, threaded=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Encerrado pelo usuário")
    except Exception:
        log.exception("Falha fatal no boot")
        sys.exit(1)