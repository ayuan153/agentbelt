"""`seatbelt` CLI — the dev on-ramp.

  seatbelt init [path]      # scaffold a starter config (default: seatbelt.yaml)
  seatbelt check            # validate config + all providers (exit 0 ok / 1 errors)
  seatbelt serve            # run the OpenAI-compatible proxy (localhost:8088)

Config path resolves from SEATBELT_CONFIG, else ./seatbelt.yaml. The proxy is unauthenticated by
design — put identity/principal verification in front of it for real deployments.
"""
from __future__ import annotations

import argparse
import os
import sys

_STARTER = """\
# Seatbelt config — edit to fit your agent, then `seatbelt check` and `seatbelt serve`.
agent: my-assistant

scope:                       # what the agent is FOR (off-scope requests get deflected)
  charter: "Describe exactly what this assistant should help with, and nothing else."
  allow_intents: [help, account, billing]
  hard_deny: [code_generation, general_knowledge, role_override]
  on_offscope: deflect
  deflect_message: "I can only help with in-scope requests."

budget:                      # denial-of-wallet control (token-weighted, per principal)
  cost_units_per_window: 50
  window_seconds: 3600
  output_token_weight: 5

egress:
  allow_domains: ["example.com"]
  render_links: false        # strip links to kill the exfiltration channel

tool_tiers:                  # low=read, medium=bounded write, high=money/account (needs verification)
  get_status: low
trusted_tool_servers: []     # MCP servers whose ToolAnnotations you trust

# providers: { risk: "yourpkg:make_scorer" }   # bring your own component — see docs/lld/plugin-interface.md
upstream_base_url: "https://api.openai.com"
"""


def _config_path() -> str:
    return os.environ.get("SEATBELT_CONFIG", "seatbelt.yaml")


def _cmd_init(path: str) -> int:
    if os.path.exists(path):
        print(f"refusing to overwrite existing {path}", file=sys.stderr)
        return 1
    with open(path, "w") as f:
        f.write(_STARTER)
    print(f"wrote {path} — edit it, then `seatbelt check`")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(prog="seatbelt", description="Protective harness for conversational agents.")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("check", help="validate config + providers")
    sp = sub.add_parser("serve", help="run the proxy")
    sp.add_argument("--host", default="127.0.0.1")
    sp.add_argument("--port", type=int, default=8088)
    si = sub.add_parser("init", help="scaffold a starter config")
    si.add_argument("path", nargs="?", default="seatbelt.yaml")
    args = parser.parse_args(argv)
    cmd = args.cmd or "serve"

    if cmd == "init":
        return _cmd_init(args.path)

    # check / serve both need a valid config
    from seatbelt.config import load_config
    from seatbelt.validate import validate

    path = _config_path()
    if not os.path.exists(path):
        print(f"no config at {path} — run `seatbelt init` or set SEATBELT_CONFIG", file=sys.stderr)
        return 1
    cfg = load_config(path)
    errors = validate(cfg)
    if errors:
        print("\n".join(f"ERROR: {e}" for e in errors), file=sys.stderr)
        return 1
    if cmd == "check":
        print("config OK")
        return 0

    import uvicorn

    from seatbelt.app import create_app
    uvicorn.run(create_app(cfg), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
