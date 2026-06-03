"""Run the Seatbelt proxy locally:  python -m seatbelt

Config path via SEATBELT_CONFIG (default: config/burritobot.yaml).
Binds to localhost only. NOTE: the proxy itself is unauthenticated — a real
deployment must put identity/principal verification in front of it (see D3 in
docs/open-questions.md); the upstream call uses OPENAI_API_KEY from the env.
"""
import os

import uvicorn

from seatbelt.app import create_app
from seatbelt.config import load_config

app = create_app(load_config(os.environ.get("SEATBELT_CONFIG", "config/burritobot.yaml")))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8088)
