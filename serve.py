"""Run the local NAZAR application: py -3.14 serve.py."""
import logging
from app.config import Settings
from app.server import create_app

logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(name)s: %(message)s")
settings=Settings.from_env()
app=create_app(settings,start_runtime=True)

if __name__=="__main__":
    try: app.run(host="127.0.0.1",port=8000,threaded=True,use_reloader=False)
    finally: app.config["NAZAR_RUNTIME"].close()
