"""
Configuração de logging com rotação de arquivo + saída no console.
"""

import logging
from logging.handlers import RotatingFileHandler

from config import ARQUIVO_LOG, DEBUG


def configurar_logger(nome: str = "ia_servidor") -> logging.Logger:
    logger = logging.getLogger(nome)

    if logger.handlers:  # evita duplicar handlers em reload
        return logger

    logger.setLevel(logging.DEBUG if DEBUG else logging.INFO)

    formato = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console
    console = logging.StreamHandler()
    console.setFormatter(formato)
    logger.addHandler(console)

    # Arquivo rotativo (5 arquivos de 2MB)
    arquivo = RotatingFileHandler(
        ARQUIVO_LOG, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    arquivo.setFormatter(formato)
    logger.addHandler(arquivo)

    return logger


log = configurar_logger()