#!/usr/bin/env python3
"""Run TTRPG Center server with proper imports"""

import os
import sys

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Load environment variables
def load_env_file(env_path):
    """Load environment variables from file"""
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value

# Load environment based on APP_ENV or default to dev
app_env = os.environ.get("APP_ENV", "dev")
env_file = f"config/.env.{app_env}"

# If environment variables are not already loaded, load from file
if not os.environ.get("ASTRA_DB_APPLICATION_TOKEN"):
    load_env_file(env_file)
    print(f"Loaded environment from {env_file}")
else:
    print(f"Using pre-loaded environment variables for {app_env}")

# Now import and run the server
from app.server import main

if __name__ == "__main__":
    main()