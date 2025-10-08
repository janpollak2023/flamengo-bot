from flask import Flask
import os

app = Flask(__name__)

@app.get("/")
def home():
    return "flamengo-bot alive"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
