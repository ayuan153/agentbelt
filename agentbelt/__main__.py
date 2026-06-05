"""`python -m agentbelt` — delegates to the CLI (see agentbelt/cli.py)."""
import sys

from agentbelt.cli import main

if __name__ == "__main__":
    sys.exit(main())
