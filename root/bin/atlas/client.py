from .utils import get_config, save_config

class AtlasClient:
    def __init__(self):
        self.config = get_config()
