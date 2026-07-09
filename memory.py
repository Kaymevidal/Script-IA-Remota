"""
Memória de conversa thread-safe, persistida em JSON.

"""

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict

from config import (
    ARQUIVO_MEMORIA,
    LIMITE_MENSAGENS,
    CONTEXTO_MENSAGENS,
    SYSTEM_PROMPT,
)
from logger import log


class Memoria:
    def __init__(self, arquivo: Path = ARQUIVO_MEMORIA):
        self.arquivo = arquivo
        self._lock = threading.Lock()
        self._mensagens: List[Dict] = []
        self._carregar()

    # Persistência 
    def _carregar(self):
        if not self.arquivo.exists():
            return
        try:
            with open(self.arquivo, "r", encoding="utf-8") as f:
                dados = json.load(f)
            self._mensagens = dados.get("mensagens", [])
            log.info("Memória carregada: %d mensagens", len(self._mensagens))
        except (json.JSONDecodeError, OSError) as e:
            log.warning("Memória corrompida/inacessível, iniciando vazia: %s", e)
            self._mensagens = []

    def _salvar(self):
        tmp = self.arquivo.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(
                    {"mensagens": self._mensagens, "atualizado": datetime.now().isoformat()},
                    f, ensure_ascii=False, indent=2,
                )
            tmp.replace(self.arquivo)  # escrita atômica
        except OSError as e:
            log.error("Falha ao salvar memória: %s", e)

    # API pública 
    def adicionar(self, role: str, content: str):
        with self._lock:
            self._mensagens.append({
                "role": role,
                "content": content,
                "ts": datetime.now().isoformat(),
            })
            if len(self._mensagens) > LIMITE_MENSAGENS:
                self._mensagens = self._mensagens[-LIMITE_MENSAGENS:]
            self._salvar()

    def contexto_para_modelo(self) -> List[Dict[str, str]]:
        """Monta a lista de mensagens (system + histórico recente) p/ o Ollama."""
        with self._lock:
            recentes = self._mensagens[-CONTEXTO_MENSAGENS:]
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
        msgs += [{"role": m["role"], "content": m["content"]} for m in recentes]
        return msgs

    def historico(self) -> List[Dict]:
        with self._lock:
            return list(self._mensagens)

    def total(self) -> int:
        with self._lock:
            return len(self._mensagens)

    def limpar(self):
        with self._lock:
            self._mensagens = []
            self._salvar()
        log.info("Memória limpa")