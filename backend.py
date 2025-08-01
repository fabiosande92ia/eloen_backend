import os
import json
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv

# ⬅️ Carrega variáveis do ficheiro .env
load_dotenv(dotenv_path="chave.env")

# Inicializar app Flask
app = Flask(__name__)
CORS(app)

# Carregar variáveis do ambiente
API_KEY = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID = os.getenv("ASSISTANT_ID")
PERFIL_PATH = os.getenv("PERFIL_PATH", "perfil_usuario.json")
HISTORICO_PATH = os.getenv("HISTORICO_PATH", "historico_eloen.json")

client = OpenAI(api_key=API_KEY)

# Estado inicial da sessão
thread = client.beta.threads.create()
memoria_sessao = []
perfil_enviado = False

def carregar_perfil():
    try:
        with open(PERFIL_PATH, "r", encoding="utf-8") as f:
            perfil = json.load(f)
            return json.dumps(perfil, indent=2, ensure_ascii=False)
    except Exception:
        return None

def guardar_historico(pergunta, resposta):
    historico = []
    if os.path.exists(HISTORICO_PATH):
        with open(HISTORICO_PATH, "r", encoding="utf-8") as f:
            historico = json.load(f)
    historico.append({"pergunta": pergunta, "resposta": resposta})
    with open(HISTORICO_PATH, "w", encoding="utf-8") as f:
        json.dump(historico, f, ensure_ascii=False, indent=2)

@app.route("/perguntar", methods=["POST"])
def perguntar():
    global perfil_enviado

    dados = request.get_json()
    pergunta = dados.get("pergunta", "")

    if not pergunta:
        return jsonify({"erro": "Nenhuma pergunta recebida"}), 400

    if not perfil_enviado:
        perfil_texto = carregar_perfil()
        if perfil_texto:
            client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=f"[PERFIL DO UTILIZADOR]\n{perfil_texto}"
            )
        perfil_enviado = True

    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=pergunta
    )

    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=ASSISTANT_ID
    )

    while True:
        status = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        if status.status == "completed":
            break
        elif status.status == "failed":
            return jsonify({"erro": "A execução falhou."}), 500
        time.sleep(1)

    mensagens = client.beta.threads.messages.list(thread_id=thread.id)
    resposta = mensagens.data[0].content[0].text.value

    memoria_sessao.append({"pergunta": pergunta, "resposta": resposta})
    guardar_historico(pergunta, resposta)

    return jsonify({"resposta": resposta})

@app.route("/nova_thread", methods=["GET"])
def nova_thread():
    global thread, memoria_sessao, perfil_enviado
    thread = client.beta.threads.create()
    memoria_sessao = []
    perfil_enviado = False
    return jsonify({"mensagem": "Nova sessão iniciada", "thread_id": thread.id})

@app.route("/estado", methods=["GET"])
def estado():
    return jsonify({"status": "online"})

@app.route("/memoria_sessao", methods=["GET"])
def ver_memoria_sessao():
    return jsonify(memoria_sessao)

@app.route("/historico", methods=["GET"])
def ver_historico():
    if os.path.exists(HISTORICO_PATH):
        with open(HISTORICO_PATH, "r", encoding="utf-8") as f:
            historico = json.load(f)
        return jsonify(historico)
    else:
        return jsonify([])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
