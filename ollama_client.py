"""
Cliente Ollama com streaming, health-check e retry com backoff exponencial.
"""

import json
import time
from typing import Iterator, List, Dict

import requests

from config import (
    OLLAMA_URL_CHAT,
    OLLAMA_URL_TAGS,
    MODELO,
    NUM_CTX,
    NUM_PREDICT,
    TEMPERATURA,
    TOP_P,
    TIMEOUT_CONEXAO,
    TIMEOUT_LEITURA,
    MAX_TENTATIVAS,
    BACKOFF_BASE,
)
from logger import log


class OllamaIndisponivelError(Exception):
    """Ollama não respondeu após todas as tentativas."""


class OllamaClient:
    def __init__(self, modelo: str = MODELO):
        self.modelo = modelo
        self._sessao = requests.Session()

    # Health 
    def online(self) -> bool:
        try:
            r = self._sessao.get(OLLAMA_URL_TAGS, timeout=TIMEOUT_CONEXAO)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def listar_modelos(self) -> List[str]:
        try:
            r = self._sessao.get(OLLAMA_URL_TAGS, timeout=TIMEOUT_CONEXAO)
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]
        except requests.RequestException as e:
            log.warning("Falha ao listar modelos: %s", e)
            return []

    def modelo_disponivel(self) -> bool:
        modelos = self.listar_modelos()
        # aceita "deepseek-coder-v2:16b" ou variações com o mesmo prefixo
        base = self.modelo.split(":")[0]
        return any(m.split(":")[0] == base for m in modelos)

    # Chat com streaming 
    def chat_stream(self, mensagens: List[Dict[str, str]]) -> Iterator[str]:
        """
        Envia mensagens ao Ollama e devolve tokens conforme chegam.
        Faz retry na fase de conexão; uma vez em streaming, não reenvia.
        """
        payload = {
            "model": self.modelo,
            "messages": mensagens,
            "stream": True,
            "options": {
                "num_ctx": NUM_CTX,
                "num_predict": NUM_PREDICT,
                "temperature": TEMPERATURA,
                "top_p": TOP_P,
            },
        }

        ultimo_erro = None
        for tentativa in range(1, MAX_TENTATIVAS + 1):
            try:
                resposta = self._sessao.post(
                    OLLAMA_URL_CHAT,
                    json=payload,
                    stream=True,
                    timeout=(TIMEOUT_CONEXAO, TIMEOUT_LEITURA),
                )
                resposta.raise_for_status()
                yield from self._processar_stream(resposta)
                return  # sucesso

            except requests.exceptions.ConnectionError as e:
                ultimo_erro = e
                espera = BACKOFF_BASE ** tentativa
                log.warning(
                    "Conexão falhou (tentativa %d/%d). Retry em %.1fs",
                    tentativa, MAX_TENTATIVAS, espera,
                )
                time.sleep(espera)
            except requests.exceptions.Timeout as e:
                ultimo_erro = e
                log.error("Timeout ao contatar Ollama: %s", e)
                break
            except requests.exceptions.HTTPError as e:
                ultimo_erro = e
                log.error("Erro HTTP do Ollama: %s", e)
                break

        raise OllamaIndisponivelError(
            f"Ollama indisponível após {MAX_TENTATIVAS} tentativas: {ultimo_erro}"
        )

    @staticmethod
    def _processar_stream(resposta: requests.Response) -> Iterator[str]:
        for linha in resposta.iter_lines(decode_unicode=True):
            if not linha:
                continue
            try:
                dado = json.loads(linha)
            except json.JSONDecodeError:
                log.debug("Linha não-JSON ignorada: %s", linha[:80])
                continue

            if dado.get("error"):
                log.error("Erro reportado pelo Ollama: %s", dado["error"])
                raise OllamaIndisponivelError(dado["error"])

            trecho = dado.get("message", {}).get("content", "")
            if trecho:
                yield trecho

            if dado.get("done"):
                break

    def fechar(self):
        self._sessao.close()