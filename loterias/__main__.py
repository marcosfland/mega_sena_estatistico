"""Permite ``python -m loterias <comando>`` (CLI)."""

import sys

from loterias.cli import main
from loterias.logging_setup import setup_logging

setup_logging()
sys.exit(main())
