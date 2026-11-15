import fastapi
from .consts import *
import asyncio
import json

loop = asyncio.get_running_loop() 
app = fastapi.FastAPI(title="Atlas server", version="")

def get_config():
    with open(CONF_FILE, "r") as conf_file:
        return json.load(conf_file)

@app.post("/atlas/server/get/")
async def get_package(data: dict, headers: dict):
    config: dict = await loop.run_in_executor(None, get_config)
    if config.get("atlas-server").get("passwordStatus") and config.get("atlas-config").get("atlas-password") != headers["token"]:
        return {
            "status": 2,
            "Message": "Incorrect password for server. :\\"
        }
