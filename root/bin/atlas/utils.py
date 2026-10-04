import os
import json
from .consts import *


def get_config():
    if os.path.isfile(CONF_FILE):
        with open(CONF_FILE, "r", encoding="utf-8") as config_file:
            return json.load(config_file)
    return {}

def save_config(config):
    os.makedirs(CONF_DIR, exist_ok=True)
    with open(CONF_FILE, "w", encoding="utf-8") as config_file:
        json.dump(config, config_file, ensure_ascii=False, indent=4)
