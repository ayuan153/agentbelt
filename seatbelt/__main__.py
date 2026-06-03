"""`python -m seatbelt` — delegates to the CLI (see seatbelt/cli.py)."""
import sys

from seatbelt.cli import main

if __name__ == "__main__":
    sys.exit(main())
