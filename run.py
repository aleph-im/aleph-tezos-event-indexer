import os
import sys
import asyncio
import threading
from src.indexer import Indexer
from src.config import config
from src.graphql.server import app
from src.utils.common import setInterval
from fastapi.logger import logger
from src.tezos.client import TezosClient
from src.storage.event import eventStorage
os.environ["TZ"] = "UTC"

running = False
tezosClient = TezosClient(config)
indexer = Indexer(tezosClient, eventStorage, config)
async def _run():
    global indexer
    logger.info("interval run event")
    global running
    if running:
        return

    running = True
    await indexer.run()
    running = False

async def prepare_intervals():
    logger.info("setting interval")
    try:
        print("call...")
        await setInterval(5, _run)
    except:
        logger.exception("Can't setup recurring indexing!")
        shutdown()

def shutdown():
    logger.info('bye, exiting in a minute...')
    for task in asyncio.all_tasks():
        task.cancel()
    sys.exit()

def start(loop, tasks):
    asyncio.set_event_loop(loop)
    
    loop.run_until_complete(
        asyncio.gather(*tasks)
    )

def background_run():
    loop = asyncio.new_event_loop()
    start(loop, [prepare_intervals()])

# start with uvicorn commandline
if __name__ == "run":
    # start background run
    timer = threading.Timer(1.0, background_run)
    timer.start()

# start from python commandline
if __name__ == "__main__":
    import uvicorn
    loop = asyncio.new_event_loop()
    _config = uvicorn.Config(app=app, loop=loop, host="0.0.0.0", port=config.port)
    server = uvicorn.Server(_config)
    server.install_signal_handlers = lambda: None
    start(loop, [prepare_intervals(), server.serve()])
