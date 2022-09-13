import asyncio
import plyvel
import json
import itertools
from copy import deepcopy
from ..config import config
from .common import Storage

async def initialize_db(alephStorageInstance):
    global eventDB
    eventDB = Storage(config.db_folder + '/event', create_if_missing=True,
                             event_driver=alephStorageInstance, extra_options={"register": True})
    global blockDB
    blockDB = Storage(config.db_folder + '/block', create_if_missing=True,
                             event_driver=alephStorageInstance, extra_options={"register": True})
    global eventIndexDB
    eventIndexDB = Storage(config.db_folder + '/event_index', create_if_missing=True,
                             event_driver=alephStorageInstance, extra_options={"register": True})
    global fetcherStateDB
    fetcherStateDB = Storage(config.db_folder + '/fetcher_state', create_if_missing=True,
                             event_driver=alephStorageInstance, extra_options={"register": True})

    global indexingStatsDB
    indexingStatsDB = Storage(config.db_folder + '/indexing_stats', create_if_missing=True,
                             event_driver=alephStorageInstance, extra_options={"register": True})

class eventStorage:
    @staticmethod
    def build_event_key(event):
        return f"{str(event['block_level']).zfill(11)}_{event['block_hash']}_{event['operation_hash']}_{event['nonce']}"

    @staticmethod
    def search_event(q):
        pass

    @staticmethod
    def save(event):
        """
        event: {block_hash, block_level, operation_hash, source, destination, event}
        """
        key = eventStorage.build_event_key(event)
        print(key)
        eventDB.put(key.encode(), json.dumps(event).encode())
        eventStorage.write_index(key, event)

    @staticmethod
    async def write_batch(events):
        events_copy = deepcopy(events)
        blocks=[]
        with eventDB.write_batch() as wb:
            for event in events_copy:
                blocks.append(event["block"])
                del event["block"]
                key = eventStorage.build_event_key(event)
                wb.put(key.encode(), json.dumps(event).encode())
                eventStorage.write_index(key, event)
        wb.write()
        await eventStorage.write_blocks(blocks)

    @staticmethod
    async def write_blocks(blocks):
        with blockDB.write_batch() as wb:
            for block in blocks:
                key = block["hash"]
                wb.put(key.encode(), json.dumps(block).encode())
        wb.write()

    @staticmethod
    async def save_events(events):
        await eventStorage.write_batch(events)
        task = asyncio.create_task(eventStorage.do_stats(events))

    @staticmethod
    def write_index(key, event):
        with eventIndexDB.write_batch() as wb:
            for index_key in [event[index] for index in ["source", "destination", "operation_hash", "block_hash"]]:
                wb.put(f"{index_key}_{key}".encode(), key.encode())
            wb.write()
            

    @staticmethod
    def get_events(reverse=True, limit=100, skip=0, index_address=None):
        events = []
        start = None
        stop = None

        if index_address is not None:
            start = "{}_{}".format(index_address, "0")
            stop = "{}_{}".format(index_address, "~")
            items = eventIndexDB.iterator(include_key=False, start=start.encode(), stop=stop.encode(), include_start=True, include_stop=True)
            for item in enumerate(itertools.islice(items, skip, (limit+skip))):
                events.append(json.loads(eventDB.get(item[1]).decode()))

            #@TODO fix reverse
            return events

        items = eventDB.iterator(include_key=False, reverse=reverse)
        for item in enumerate(itertools.islice(items, skip, (limit+skip))):
            event = json.loads(item[1].decode())
            event["block"] = lambda block_hash: blockDB.get(block_hash.encode())
            #if with_block:
            #    block = blockDB.get(event["hash"])
            #    event["block"] = json.loads(block)
            events.append(event)

        return events

    @staticmethod
    def get_recent_block():
        try:
            event = next(eventDB.iterator(include_key=False, reverse=True))
            return json.loads(event.decode())
        except StopIteration:
            return None

    @staticmethod
    def get_oldest_block():
        try:
            event = next(eventDB.iterator(include_key=False, reverse=False))
            return json.loads(event.decode())
        except StopIteration:
            return None

    @staticmethod
    def get_fetcher_state():
        state = fetcherStateDB.get('fetcher_state'.encode())
        if state is not None:
            return json.loads(state.decode())
        else:
            return {"recent_block": None, "oldest_block": None}

    @staticmethod
    def update_fetcher_state(recent_block = None, oldest_block = None):
        fetcher_state = eventStorage.get_fetcher_state()
        if fetcher_state is None:
            fetcher_state = {"recent_block": None, "oldest_block": None}

        if recent_block is not None:
            fetcher_state["recent_block"] = recent_block
        if oldest_block is not None:
            fetcher_state["oldest_block"] = oldest_block

        fetcherStateDB.put('fetcher_state'.encode(), json.dumps(fetcher_state).encode())

    @staticmethod
    def unstrust_event(event):
        key = eventStorage.build_event_key(event)
        ev = eventDB.get(key.encode())
        if ev:
            ev = json.loads(ev.decode())
            ev["metadata"] = {"msg": "untrusted event"}
            eventDB.put(key.encode(), json.dumps(ev).encode())

    @staticmethod
    def trust_event(event):
        key = eventStorage.build_event_key(event)
        ev = eventDB.get(key.encode())
        if ev:
            ev = json.loads(ev.decode())
            ev["verified"] = True
            eventDB.put(key.encode(), json.dumps(ev).encode())

    @staticmethod
    async def do_stats(events):
        count = len(events)
        gc = indexingStatsDB.get("global_counter".encode())
        if gc is None:
            gc = "0".encode()
        indexingStatsDB.put("global_counter".encode(), str(int(gc.decode()) + count).encode())

        accounts = {}
        for event in events:
            if event["destination"] not in accounts:
                accounts[event["destination"]] = 0

            accounts[event["destination"]] += 1

            if event["source"] not in accounts:
                accounts[event["source"]] = 0

            accounts[event["source"]] += 1

        for account in accounts:
            ac = indexingStatsDB.get("{}_counter".format(account).encode())
            if ac is None:
                ac = "0".encode()
            indexingStatsDB.put("{}_counter".format(account).encode(), str(int(ac.decode()) + accounts[account]).encode())
