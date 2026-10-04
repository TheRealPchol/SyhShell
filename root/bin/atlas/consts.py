import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CONF_DIR = os.path.join(CURRENT_DIR, '..', 'config')
CONF_FILE = os.path.join(CONF_DIR, "atlas-config.json")