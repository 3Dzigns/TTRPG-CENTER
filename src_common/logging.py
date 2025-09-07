# Thin compatibility layer to align imports used in tests and scripts
"""Logging module compatibility layer"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from ttrpg_logging import *  # noqa: F401,F403

