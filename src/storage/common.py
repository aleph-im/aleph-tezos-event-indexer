import os
import asyncio
import threading
import json
import base64
from functools import wraps
import plyvel
import requests
import hashlib
from pydantic import BaseModel
from typing import Optional, Iterable, Union, Any, Dict, List
from ..config import config
from fastapi.logger import logger

class MessageModel(BaseModel):
    dbname: str
    operation: str # put or del
    key: str
    data: Any

class EventModel(BaseModel):
    namespace: str
    from_uuid: str
    message: MessageModel

class SubscribeModel(BaseModel):
    namespace: str
    uuid: str
    channel: str
    secret_shared_key: str
    hook_url: str
    pubsub_server: str
    mode: Optional[str] = "standalone" # standalone or hash    
    options: Optional[Dict[str, str]] = None # options can be filled for hash mode
    running_mode: Optional[str] = "readonly"
    
class AlephStorageInstance():
    def __init__(self, app):
        self.instance = {}
        self.db_instance = {}
        self.event = asyncio.Event()
        self.waiter_task = asyncio.create_task(self.on_ready())
        self.register_routes(app)
        self.db = plyvel.DB(config.db_folder + '/__aleph_application',
                                        create_if_missing=True)

    def register_routes(self, app):
        @app.post('/pubsub/initialize')
        async def initialize(data: SubscribeModel):
            return await self.initialize_handler(data)

        @app.post('/pubsub/hook')
        async def pubsub(message: EventModel):
            return await self.pubsub_handler(message)

        @app.post('/application/__force_exit')
        async def appilication_restart():
            os._exit(0)

    async def initialize_handler(self, data: SubscribeModel):
        self.load_instance()
        print("before", self.instance)
        self.update(data.dict())
        await self.subscribe(data)
        self.set_ready(ready=True)
        return {"status": "success"}

    async def pubsub_handler(self, event: MessageModel):
        #db = get_db(event.namespace, event.message.dbname)
        db = self.get_target_db(event.namespace, event.message.dbname)

        if event.message.operation == "put":
            key = base64.b64decode(event.message.key)
            data = base64.b64decode(event.message.data)
            db.put(key, data)
        if event.message.operation == "delete":
            key = base64.b64decode(event.message.key)
            db.delete(key)

    
    async def on_ready(self):
        await self.event.wait()
        return True

    # load default from env
    async def load_default_config(self):
        default = config.pubsub
        if default:
            print("load default config")
            logger.info("Load default config")
            await self.initialize_handler(SubscribeModel(**default))

    async def check(self, force=False):
        check_count = 0
        while self.is_ready() != True:
            await asyncio.sleep(3)
            self.load_instance()
            check_count += 1
            if check_count > 10:
                await self.load_default_config()

        self.event.set()

    def load_instance(self):
        instance = self.db.get('instance'.encode())
        if instance:
            self.instance = json.loads(instance)
        else:
            self.db.put('instance'.encode(), json.dumps({"app_ready": False}).encode())
            
    def update(self, props: dict):
        if not self.instance:
            self.load_instance()

        for k in props:
            self.instance[k] = props[k]

        self.db.put('instance'.encode(), json.dumps(self.instance).encode())

    def set_ready(self, ready=False):
        self.update({"app_ready": ready})
        print(self.is_ready(), ready)

    def is_ready(self):
        if not self.instance:
            self.load_instance()

        if "app_ready" in self.instance:
            return self.instance["app_ready"]

        return False


    def get_uuid(self):
        return self.instance["uuid"]


    def get_mode(self):
        if "running_mode" in self.instance:
            return self.instance["running_mode"]
        return "readonly"

    async def subscribe(self, data: SubscribeModel):
        if "http" not in self.instance["pubsub_server"]:
            print("no server to subscribe")

        options = data.dict(exclude_none=True)
        del options["pubsub_server"]
        del options["running_mode"]

        _opts = json.dumps(options, sort_keys=True)
        sid_str = f"{self.instance['uuid']}_{self.instance['pubsub_server']}_{_opts}"
        sid = hashlib.md5(sid_str.encode()).hexdigest()

        if "subscriptions" not in self.instance:
            self.instance["subscriptions"] = []

        if sid not in self.instance["subscriptions"]:
            r = requests.post(f"{self.instance['pubsub_server']}/subscribe", json=options)
            if r.status_code == 200:
                self.instance["subscriptions"].append(sid)
                self.update({"subscriptions": self.instance["subscriptions"]})
        else:
            print("already subscribed")    

    def subscribe_db(self, dbname, instance):
        self.db_instance[dbname] = instance

    def get_target_db(self, namespace, dbname):
        if dbname in self.db_instance:
            return self.db_instance[dbname]

    def on_db_event(self, dbname, event_name, *args, **kwargs):
        if event_name == "put":
           message = MessageModel(**{
               "dbname": dbname, "operation": event_name,
               "key": base64.b64encode(args[0]), "data": base64.b64encode(args[1])
           })

           event = {
               "secret_shared_key": self.instance["secret_shared_key"],
               "from_uuid": self.instance["uuid"],
               "namespace": self.instance["namespace"],
               "channel": self.instance["channel"],
               "message": message.dict(),
           }

           try:
               requests.post(f"{self.instance['pubsub_server']}/broadcast", json=event)
           except:
               # @todo => delayed, store event and retry
               logger.error("Unexpected error, event was delayed")

class Storage():
    def __init__(self, name, create_if_missing=False, event_driver=None, extra_options=dict):
        self.dbname = name.split('/').pop()
        self.db = plyvel.DB(name, create_if_missing=create_if_missing)
        if event_driver:
            self.event_driver = event_driver
        
            if "register" in extra_options:
                event_driver.subscribe_db(self.dbname, self.db)

    def __getattr__(self, name):
        def wrapper(*args, **kwargs):
            # @TODO unblock
            if self.event_driver.get_mode() == "server":
                self.event_driver.on_db_event(self.dbname, name, *args, **kwargs)
            return getattr(self.db, name)(*args, **kwargs)
        return wrapper

aleph_initialized = False
aleph_instance = None
async def initialize_aleph_event_storage(app):
    global aleph_initialized
    global aleph_instance
    if aleph_initialized:
        return aleph_instance

    aleph_instance = AlephStorageInstance(app)
    # reset
    #aleph_instance.set_ready(ready=False)
    asyncio.gather(*[aleph_instance.check()])
    aleph_initialized = True
    print("APP Ready")
    return aleph_instance
