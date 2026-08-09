from flask import Flask
from threading import Thread
import os
import logging

app = Flask('')

# Desabilita logs excessivos do Flask no terminal
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

@app.route('/')
def home():
    return "Bot TTS está acordado e operando normalmente!"

    def run():
        # Pega a porta do ambiente (Render injeta a variável PORT automaticamente)
            port = int(os.environ.get("PORT", 8080))
                app.run(host='0.0.0.0', port=port)

                def keep_alive():
                    """Inicia o servidor Flask em uma Thread daemon"""
                        t = Thread(target=run, daemon=True)
                            t.start()
                            