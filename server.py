"""
Servidor Flask com streaming SSE.
Escuta em 0.0.0.0 para acesso via ethernet a partir do cliente.
"""

import json

from flask import Flask, request, jsonify, Response, send_from_directory
from flask_cors import CORS

from config import (
    PASTA_WEB,
    HOST,
    PORTA,
    DEBUG,
    MODELO,
    ORIGENS_PERMITIDAS,
)
from logger import log
from memory import Memoria
from ollama_client import OllamaClient, OllamaIndisponivelError

app = Flask(__name__, static_folder=None)
CORS(app, origins=ORIGENS_PERMITIDAS)

memoria = Memoria()
ollama = OllamaClient()


# Frontend
@app.route("/")
def index():
    return send_from_directory(PASTA_WEB, "index.html")


# Status 
@app.route("/api/status", methods=["GET"])
def status():
    online = ollama.online()
    return jsonify({
        "servidor": "online",
        "ollama": "online" if online else "offline",
        "modelo": MODELO,
        "modelo_disponivel": ollama.modelo_disponivel() if online else False,
        "total_mensagens": memoria.total(),
    })


# Chat com streaming (SSE)
@app.route("/api/chat", methods=["POST"])
def chat():
    dados = request.get_json(silent=True) or {}
    pergunta = (dados.get("pergunta") or "").strip()

    if not pergunta:
        return jsonify({"erro": "Pergunta vazia"}), 400

    if not ollama.online():
        return jsonify({"erro": "Ollama offline. Execute: ollama serve"}), 503

    # registra a pergunta e monta o contexto ANTES de começar o stream
    memoria.adicionar("user", pergunta)
    mensagens = memoria.contexto_para_modelo()

    def gerar():
        resposta_completa = []
        try:
            for trecho in ollama.chat_stream(mensagens):
                resposta_completa.append(trecho)
                # cada evento SSE carrega um token
                yield f"data: {json.dumps({'token': trecho})}\n\n"

            texto_final = "".join(resposta_completa)
            memoria.adicionar("assistant", texto_final)
            yield f"data: {json.dumps({'fim': True})}\n\n"
            log.info("Resposta gerada (%d chars)", len(texto_final))

        except OllamaIndisponivelError as e:
            log.error("Falha no streaming: %s", e)
            yield f"data: {json.dumps({'erro': str(e)})}\n\n"
        except Exception as e:  # rede caindo no meio, etc.
            log.exception("Erro inesperado no streaming")
            yield f"data: {json.dumps({'erro': f'Erro interno: {e}'})}\n\n"

    return Response(
        gerar(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # desativa buffering em proxies
            "Connection": "keep-alive",
        },
    )


# Histórico 
@app.route("/api/historico", methods=["GET"])
def historico():
    return jsonify({"mensagens": memoria.historico()})


@app.route("/api/limpar", methods=["POST"])
def limpar():
    memoria.limpar()
    return jsonify({"status": "ok"})