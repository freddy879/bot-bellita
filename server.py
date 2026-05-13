#!/usr/bin/env python3

from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import urllib.error
import json
import os
import time
from datetime import datetime

# =========================================
# CONFIG
# =========================================

PORT = int(os.environ.get("PORT", 8000))

BAZAR_API = "https://bazar-bellita.onrender.com"

# ⚠️ TU API KEY
OPENAI_KEY = "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"

# Caché de contexto
CONTEXT_CACHE = {
    "data": None,
    "timestamp": 0
}

CACHE_TTL_SECONDS = 300

# =========================================
# ENDPOINTS
# =========================================

ENDPOINTS = {
    "ventas": "/api/ventas",
    "productos": "/api/productos",
    "clientes": "/api/clientes",
    "inventario": "/api/inventario",
    "pedidos": "/api/pedidos",
}

# =========================================
# PROMPT
# =========================================

SYSTEM_PROMPT = """
Eres BellitaBot, la IA oficial de Bazar Bellita.

Funciones:
- Analizar ventas
- Revisar productos
- Detectar tendencias
- Recomendar estrategias
- Ayudar al negocio

Reglas:
- Habla siempre español
- Sé claro y profesional
- No inventes información
""".strip()

# =========================================
# FETCH API
# =========================================

def fetch_bazar(path):
    url = BAZAR_API + path

    try:
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json"
            }
        )

        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read().decode("utf-8")
            data = json.loads(raw)

            return {
                "ok": True,
                "data": data
            }

    except Exception as e:
        return {
            "ok": False,
            "error": str(e)
        }

# =========================================
# CONTEXTO
# =========================================

def gather_business_context():

    now = time.time()

    # usar caché
    if (
        CONTEXT_CACHE["data"]
        and (now - CONTEXT_CACHE["timestamp"]) < CACHE_TTL_SECONDS
    ):
        print("📦 Contexto desde caché")
        return CONTEXT_CACHE["data"]

    print("🔄 Actualizando contexto...")

    fecha = datetime.now().strftime("%Y-%m-%d %H:%M")

    partes = [
        f"Fecha actual: {fecha}\n"
    ]

    for nombre, ruta in ENDPOINTS.items():

        resultado = fetch_bazar(ruta)

        if resultado["ok"]:

            datos = resultado["data"]

            if isinstance(datos, list):
                datos = datos[:50]

            texto = json.dumps(
                datos,
                ensure_ascii=False,
                indent=2
            )

            if len(texto) > 3000:
                texto = texto[:3000] + "\n... datos truncados"

            partes.append(
                f"\n=== {nombre.upper()} ===\n{texto}"
            )

        else:

            partes.append(
                f"\n=== {nombre.upper()} ===\nERROR: {resultado['error']}"
            )

    contexto = "\n".join(partes)

    CONTEXT_CACHE["data"] = contexto
    CONTEXT_CACHE["timestamp"] = now

    return contexto

# =========================================
# VALIDAR MENSAJES
# =========================================

def validate_messages(messages):

    if not isinstance(messages, list):
        return False, "messages debe ser lista"

    if len(messages) == 0:
        return False, "messages vacío"

    valid_roles = {"user", "assistant"}

    for i, msg in enumerate(messages):

        if not isinstance(msg, dict):
            return False, f"Mensaje {i} inválido"

        if "role" not in msg:
            return False, f"Mensaje {i} sin role"

        if "content" not in msg:
            return False, f"Mensaje {i} sin content"

        if msg["role"] not in valid_roles:
            return False, f"Role inválido en mensaje {i}"

        if not isinstance(msg["content"], str):
            return False, f"Content inválido en mensaje {i}"

    return True, None

# =========================================
# OPENAI
# =========================================

def ask_openai(messages, business_data):

    if not OPENAI_KEY:
        return "⚠️ API key faltante"

    system_message = {
        "role": "system",
        "content": SYSTEM_PROMPT + "\n\nDATOS:\n" + business_data
    }

    full_messages = [system_message] + messages

    payload = {
        "model": "gpt-4o-mini",
        "messages": full_messages,
        "max_tokens": 1200,
        "temperature": 0.7
    }

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_KEY}"
        },
        method="POST"
    )

    try:

        with urllib.request.urlopen(req, timeout=60) as response:

            raw = response.read().decode("utf-8")

            data = json.loads(raw)

            return data["choices"][0]["message"]["content"]

    except urllib.error.HTTPError as e:

        error_body = e.read().decode("utf-8")

        print("❌ OPENAI ERROR:")
        print(error_body)

        return f"⚠️ Error OpenAI {e.code}"

    except Exception as e:

        print("❌ ERROR GENERAL:")
        print(str(e))

        return "⚠️ Error interno IA"

# =========================================
# SERVER
# =========================================

class Handler(BaseHTTPRequestHandler):

    # -------------------------------------
    # CORS
    # -------------------------------------

    def end_headers(self):

        self.send_header(
            "Access-Control-Allow-Origin",
            "*"
        )

        self.send_header(
            "Access-Control-Allow-Methods",
            "GET, POST, OPTIONS"
        )

        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type"
        )

        super().end_headers()

    # -------------------------------------

    def log_message(self, fmt, *args):

        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] {fmt % args}"
        )

    # -------------------------------------

    def send_json(self, code, obj):

        body = json.dumps(
            obj,
            ensure_ascii=False
        ).encode("utf-8")

        self.send_response(code)

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8"
        )

        self.send_header(
            "Content-Length",
            str(len(body))
        )

        self.end_headers()

        self.wfile.write(body)

    # =====================================
    # OPTIONS
    # =====================================

    def do_OPTIONS(self):

        self.send_response(200)

        self.send_header(
            "Access-Control-Allow-Origin",
            "*"
        )

        self.send_header(
            "Access-Control-Allow-Methods",
            "GET, POST, OPTIONS"
        )

        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type"
        )

        self.end_headers()

    # =====================================
    # GET
    # =====================================

    def do_GET(self):

        if self.path == "/":

            self.send_json(
                200,
                {
                    "status": "online",
                    "bot": "BellitaBot",
                    "version": "2.1"
                }
            )

        elif self.path == "/health":

            self.send_json(
                200,
                {
                    "status": "ok"
                }
            )

        else:

            self.send_json(
                404,
                {
                    "error": "Ruta no encontrada"
                }
            )

    # =====================================
    # POST
    # =====================================

    def do_POST(self):

        if self.path != "/chat":

            self.send_json(
                404,
                {
                    "error": "Ruta no encontrada"
                }
            )

            return

        try:

            length = int(
                self.headers.get("Content-Length", 0)
            )

            if length <= 0:

                self.send_json(
                    400,
                    {
                        "error": "Body vacío"
                    }
                )

                return

            body = self.rfile.read(length)

            try:

                req_data = json.loads(
                    body.decode("utf-8")
                )

            except Exception:

                self.send_json(
                    400,
                    {
                        "error": "JSON inválido"
                    }
                )

                return

            messages = req_data.get("messages", [])

            valid, error = validate_messages(messages)

            if not valid:

                self.send_json(
                    400,
                    {
                        "error": error
                    }
                )

                return

            print("📊 Obteniendo datos...")

            business_data = gather_business_context()

            print("🤖 Preguntando a OpenAI...")

            reply = ask_openai(
                messages,
                business_data
            )

            self.send_json(
                200,
                {
                    "reply": reply
                }
            )

        except Exception as e:

            print("❌ ERROR POST:")
            print(str(e))

            self.send_json(
                500,
                {
                    "error": "Error interno servidor"
                }
            )

# =========================================
# MAIN
# =========================================

def main():

    print("=" * 50)
    print("🛍️ BellitaBot v2.1")
    print("=" * 50)

    print(f"Puerto : {PORT}")
    print(f"API    : {BAZAR_API}")

    if OPENAI_KEY:
        print("✅ OpenAI OK")
    else:
        print("❌ OpenAI faltante")

    server = HTTPServer(
        ("0.0.0.0", PORT),
        Handler
    )

    print(f"🚀 Servidor online puerto {PORT}")

    server.serve_forever()

# =========================================

if __name__ == "__main__":
    main()
