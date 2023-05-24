import os
import sys
import asyncio
import shutil
from src.indexer import Indexer
from src.config import config
from src.graphql.server import app
from src.utils.common import setInterval
from fastapi.logger import logger
from src.tezos.client import TezosClient
from src.storage.event import eventStorage, initialize_db
from src.storage.common import initialize_aleph_event_storage

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
    logger.info("bye, exiting in a minute...")
    for task in asyncio.all_tasks():
        task.cancel()
    sys.exit()


async def start(loop, server=None):
    asyncio.set_event_loop(loop)
    tasks = []
    if server:
        api_server = server.serve()
        tasks.append(api_server)

    logger.info("initialize application")

    # reset db reset_db file present
    if os.path.isfile(f"{config.db_folder}/reset_db"):
        shutil.rmtree(f"{config.db_folder}/indexing_stats", ignore_errors=True)
        shutil.rmtree(f"{config.db_folder}/event", ignore_errors=True)
        shutil.rmtree(f"{config.db_folder}/event_index", ignore_errors=True)
        shutil.rmtree(f"{config.db_folder}/event_wildcard_index", ignore_errors=True)

    aleph_instance = await initialize_aleph_event_storage(app)
    await initialize_db(aleph_instance)
    logger.info("indexing are in waiting mode...")
    await aleph_instance.on_ready()

    # reindex the blocks if the database has been reset
    if os.path.isfile(f"{config.db_folder}/reset_db"):
        await indexer._reset()
        os.remove(f"{config.db_folder}/reset_db")

    if aleph_instance.get_mode() != "readonly":
        logger.info("start in indexing mode")
        tasks.append(prepare_intervals())
    else:
        logger.info("start in readonly mode")
    await asyncio.gather(*tasks)


def background_run():
    loop = asyncio.new_event_loop()
    asyncio.gather(start(loop, None))


# start with uvicorn commandline
if __name__ == "run":
    loop = asyncio.new_event_loop()
    asyncio.gather(start(loop))

# start from python commandline
if __name__ == "__main__":
    import uvicorn

    loop = asyncio.new_event_loop()
    _config = uvicorn.Config(app=app, loop=loop, host=config.host, port=config.port)
    server = uvicorn.Server(_config)
    server.install_signal_handlers = lambda: None
    asyncio.run(start(loop, server))
