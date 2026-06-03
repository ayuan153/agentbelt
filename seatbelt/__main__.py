"""Run or validate the Seatbelt proxy.

  python -m seatbelt            # validate config, then serve on localhost:8088
  python -m seatbelt --check    # validate config only, exit 0 (ok) / 1 (errors)

Config path via SEATBELT_CONFIG (default: config/burritobot.yaml). The proxy itself is
unauthenticated by design — a real deployment puts identity/principal verification in front of it
(see D3 in docs/open-questions.md); the upstream call uses OPENAI_API_KEY from the env.
"""
import os
import sys

from seatbelt.config import load_config
from seatbelt.validate import validate


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    cfg = load_config(os.environ.get("SEATBELT_CONFIG", "config/burritobot.yaml"))

    errors = validate(cfg)
    if errors:
        print("\n".join(f"ERROR: {e}" for e in errors), file=sys.stderr)
        return 1
    if "--check" in argv:
        print("config OK")
        return 0

    import uvicorn

    from seatbelt.app import create_app
    uvicorn.run(create_app(cfg), host="127.0.0.1", port=8088)
    return 0


if __name__ == "__main__":
    sys.exit(main())
