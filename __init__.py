# Anki Web Browser Add-on
# Entry point for the add-on

import os
import sys

# Add current directory to path to find src module
addon_dir = os.path.dirname(__file__)
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)

# Import the main runner from src
from src import *