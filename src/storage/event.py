import asyncio
import plyvel
import json
import itertools
from ..config import config

eventDB = plyvel.DB(config.db_folder + '/event', create_if_missing=True)
blockDB = plyvel.DB(config.db_folder + '/block', create_if_missing=True)
eventIndexDB = plyvel.DB(config.db_folder + '/event_index', create_if_missing=True)
fetcherStateDB = plyvel.DB(config.db_folder + '/fetcher_state', create_if_missing=True)

class eventStorage:
    @staticmethod
    def build_event_key(event):
        return f"{str(event['block_level']).zfill(11)}_{event['block_hash']}_{event['operation_hash']}"

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
        blocks=[]
        with eventDB.write_batch() as wb:
            for event in events:
                blocks.append(event["block"])
                del event["block"]
                key = eventStorage.build_event_key(event)
                wb.put(key.encode(), json.dumps(event).encode())
                eventStorage.write_index(key, event)
        wb.write()
        eventStorage.write_blocks(blocks)

    @staticmethod
    async def write_blocks(blocks):
        with blockDB.write_batch() as wb:
            for block in blocks:
                key = block["hash"]
                wb.put(key.encode(), json.dumps(block).encode())
        wb.write()

    @staticmethod
    def save_events(events):
        loop = asyncio.get_event_loop()
        write_task = loop.create_task(eventStorage.write_batch(events))
        yield asyncio.wait([write_task])

    @staticmethod
    def write_index(key, event):
        with eventIndexDB.write_batch() as wb:
            for index_key in [event[index] for index in ["source", "destination", "operation_hash"]]:
                wb.put(f"{index_key}_{key}".encode(), key.encode())
            wb.write()
            

    @staticmethod
    def get_events(reverse=True, limit=100, skip=0, index_address=None):
        events = []
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
            
