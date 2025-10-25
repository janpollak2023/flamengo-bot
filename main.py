# main.py
import os
import json
import traceback
from flask import Flask, request, jsonify

# ----------------- Bezpečné importy z tip_engine -----------------
# 'suggest_today' bereme jako povinné (jinak nemá app co vracet).
try:
    from tip_engine import suggest_today
except Exception as e:
    raise ImportError("Chybí povinná funkce 'suggest_today' v tip_engine: " + str(e))

# Volitelné funkce:
try:
    from tip_engine import suggest_full
    HAS_SUGGEST_FULL = True
except Exception:
    suggest_full = None
    HAS_SUGGEST_FULL = False

try:
    from tip_engine import debug_report
    HAS_DEBUG_REPORT = True
except Exception:
    debug_report = None
    HAS_DEBUG_REPORT = False

# ----------------- Pomocná routovací logika -----------------
def run_suggest(mode: str):
    """
    mode: 'today' | 'full' | 'debug'
    """
    mode = (mode or "today").lower()

    if mode == "today":
        return suggest_today()

    if mode == "full":
        if HAS_SUGGEST_FULL and callable(suggest_full):
            return suggest_full()
        return {
            "warning": "suggest_full není dostupné v tip_engine – vrácen fallback na suggest_today.",
            "data": suggest_today(),
        }

    if mode == "debug":
        if HAS_DEBUG_REPORT and callable(debug_report):
            return debug_report()
        return {
            "warning": "debug_report není dostupné v tip_engine – použijte mode=today nebo full.",
            "data": suggest_today(),
        }

    return {"error": "Neplatný mode. Použijte: today | full | debug"}

# ----------------- Flask app -----------------
app = Flask(__name__)

@app.get("/healthz")
def healthz():
    return "ok", 200

@app.get("/")
def index():
    return jsonify({
        "service": "tip-engine-api",
        "endpoints": {
            "/healthz": "healthcheck",
            "/suggest?mode=today|full|debug": "JSON výstup engine"
        },
        "has_suggest_full": HAS_SUGGEST_FULL,
        "has_debug_report": HAS_DEBUG_REPORT,
    })

@app.get("/suggest")
def suggest():
    mode = request.args.get("mode", "today")
    try:
        out = run_suggest(mode)
        try:
            json.dumps(out)  # ověří serializovatelnost
            return jsonify(out), 200
        except TypeError:
            return jsonify({"result": str(out)}), 200
    except Exception as e:
        return jsonify({
            "error": "Chyba při generování návrhu",
            "exception": str(e),
            "trace": traceback.format_exc()
        }), 500

# ----------------- Spuštění -----------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "0"))
    if port > 0:
        app.run(host="0.0.0.0", port=port, threaded=True)
    else:
        # CLI fallback pro lokální běh
        mode = os.getenv("MODE", "today")
        try:
            result = run_suggest(mode)
            try:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            except TypeError:
                print(str(result))
        except Exception as e:
            print("ERROR:", e)
            print(traceback.format_exc())
            raise
