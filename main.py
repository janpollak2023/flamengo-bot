# main.py
import os
import json
import traceback
from flask import Flask, request, jsonify

# --- Safe import z tip_engine ----------------------------------------------
# Počítáme s tím, že suggest_full může chybět.
try:
    from tip_engine import suggest_today, debug_report  # jisté funkce
except Exception as e:
    raise ImportError("Nepodařilo se importovat 'suggest_today' nebo 'debug_report' z tip_engine: " + str(e))

try:
    from tip_engine import suggest_full  # volitelná funkce
    HAS_SUGGEST_FULL = True
except Exception:
    suggest_full = None
    HAS_SUGGEST_FULL = False

# --- Pomocné funkce ---------------------------------------------------------
def run_suggest(mode: str):
    """
    Vrátí data podle zvoleného režimu.
    mode: 'today' | 'full' | 'debug'
    """
    if mode == "today":
        return suggest_today()
    if mode == "full":
        if HAS_SUGGEST_FULL and callable(suggest_full):
            return suggest_full()
        # Fallback: když suggest_full není, vrátíme today + hlášku
        return {
            "warning": "suggest_full není dostupné v tip_engine – vracím fallback na suggest_today.",
            "data": suggest_today()
        }
    if mode == "debug":
        return debug_report()

    # default
    return {"error": "Neplatný mode. Použijte: today | full | debug"}

# --- Flask aplikace ---------------------------------------------------------
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
            "/suggest?mode=today|full|debug": "vrátí JSON s výstupem engine"
        },
        "has_suggest_full": HAS_SUGGEST_FULL
    })

@app.get("/suggest")
def suggest():
    mode = request.args.get("mode", "today").lower()
    try:
        out = run_suggest(mode)
        # pokud výstup není JSON-serializable, zkusíme převést na string
        try:
            json.dumps(out)
            return jsonify(out), 200
        except TypeError:
            return jsonify({"result": str(out)}), 200
    except Exception as e:
        return jsonify({
            "error": "Chyba při generování návrhu",
            "exception": str(e),
            "trace": traceback.format_exc()
        }), 500

# --- Hlavní vstup -----------------------------------------------------------
if __name__ == "__main__":
    # Pokud Render spouští jako web (má proměnnou PORT), naběhne server.
    # Jinak to umí i CLI režim (vypíše návrh a skončí).
    port = int(os.getenv("PORT", "0"))
    if port > 0:
        # Web mód pro Render
        app.run(host="0.0.0.0", port=port, threaded=True)
    else:
        # CLI mód (užitečné pro lokální test)
        mode = os.getenv("MODE", "today").lower()
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
