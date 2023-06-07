import json
import itertools
from copy import deepcopy
from ..config import config
from .common import Storage
import time
import hashlib

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
    global eventWildcardIndexDB
    eventWildcardIndexDB = Storage(config.db_folder + '/event_wildcard_index', create_if_missing=True,
                             event_driver=alephStorageInstance, extra_options={"register": True})
    global fetcherStateDB
    fetcherStateDB = Storage(config.db_folder + '/fetcher_state', create_if_missing=True,
                             event_driver=alephStorageInstance, extra_options={"register": True})
    global indexingStatsDB
    indexingStatsDB = Storage(config.db_folder + '/indexing_stats', create_if_missing=True,
                             event_driver=alephStorageInstance, extra_options={"register": True})
    global tokenHolderDB
    tokenHolderDB = Storage(config.db_folder + '/token_holder', create_if_missing=True, event_driver=alephStorageInstance, extra_options={"register": True})

    global tokenHolderChangedDB
    tokenHolderChangedDB = Storage(config.db_folder + '/token_holder_changed', create_if_missing=True, event_driver=alephStorageInstance, extra_options={"register": True})

class eventStorage:
    @staticmethod
    def build_event_key(event):
        return f"{str(event['block_level']).zfill(11)}_{event['operation_hash']}_{event['source']}_{event['nonce']}"

    @staticmethod
    def search_event(q):
        pass

    @staticmethod
    def save(event):
        """
        event: {block_hash, block_level, operation_hash, source, destination, event, metadata...}
        """
        key = eventStorage.build_event_key(event)
        event["_id"] = hashlib.sha256(key.encode()).hexdigest()
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
                event["_id"] = hashlib.sha256(key.encode()).hexdigest()                
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
        #task = asyncio.create_task(eventStorage.do_stats(events))
        await eventStorage.do_stats(events)

    @staticmethod
    def write_index(key, event):
        # main index
        with eventIndexDB.write_batch() as wb:
            for index_key in [event[index] for index in ["source", "operation_hash", "block_hash"]]:
                wb.put(f"{index_key}_{key}".encode(), key.encode())
            wb.write()

        # wildcard index
        with eventWildcardIndexDB.write_batch() as wb:
            wb.put(event["_id"].encode(), key.encode())
            wildcard_index = ["pkh", "from", "to", "owner", "address", "sender", "addr"]
            for allowed_key in wildcard_index:
                if not isinstance(event["_event"], dict):
                    continue

                if allowed_key in event["_event"]:
                    index_key = event["_event"][allowed_key]
                    if isinstance(index_key, str):
                        print("write extra index", allowed_key, f"{index_key}_{key}")
                        wb.put(f"{index_key}_{key}".encode(), key.encode())
                        #wb.delete(f"{index_key}_{key}".encode())
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
            events.append(event)

        return events

    @staticmethod
    def get_events_iterator(reverse=True, index_address=None, index_name="main"):
        start = None
        stop = None

        indexDB = eventIndexDB
        if index_name == "wildcard":
            indexDB = eventWildcardIndexDB

        if index_address is not None:
            start = "{}_{}".format(index_address, "0")
            stop = "{}_{}".format(index_address, "~")
            return indexDB.iterator(include_key=False, start=start.encode(), stop=stop.encode(), include_start=True, include_stop=True)


        return eventDB.iterator(include_key=False, reverse=reverse)

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
    def untrust_event(event):
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
            if event["source"] not in accounts:
                accounts[event["source"]] = 0

            accounts[event["source"]] += 1

        for account in accounts:
            ac = indexingStatsDB.get("{}_counter".format(account).encode())
            if ac is None:
                ac = "0".encode()
            indexingStatsDB.put("{}_counter".format(account).encode(), str(int(ac.decode()) + accounts[account]).encode())

    @staticmethod
    async def get_stats(address=None):
        if address is not None:
            gc = indexingStatsDB.get("{}_counter".format(address).encode())
        else:
            gc = indexingStatsDB.get("global_counter".encode())

        if gc is None:
            gc = "0".encode()

        first_event = eventStorage.get_events(False, 1, 0, address)
        last_event = eventStorage.get_events(True, 1, 0, address)

        return {
            "total_events": gc.decode(),
            "first_event": first_event[0] if len(first_event) > 0 else None,
            "last_event": last_event[0] if len(last_event) > 0 else None
        }

    @staticmethod
    def get_block(block_hash):
        return blockDB.get(block_hash.encode())

    @staticmethod
    def get_event(key):
        return eventDB.get(key.encode())

    @staticmethod
    def get_event_by_id(_id):
        event_key = eventWildcardIndexDB.get(_id.encode())
        if event_key:
            return json.loads(eventDB.get(event_key))

    @staticmethod
    async def save_balances(contract, balances):
        changed_balances = []
        with tokenHolderDB.write_batch() as wb:
            for balance in balances:
                key = f"{contract}_{balance.get('token_id')}_{balance.get('address')}"
                _holder = tokenHolderDB.get(key.encode())
                old_balance = None
                if _holder is not None:
                    old_balance = json.loads(_holder.decode())["balance"]

                if old_balance is None and balance.get("balance") == 0:
                    continue
                if old_balance is not None and balance.get("balance") == old_balance:
                    continue
                
                wb.put(key.encode(), json.dumps({"ts": int(time.time()), "balance": balance.get("balance"), "block_level": balance.get("block_level")}).encode())
                changed_balances.append({"key": key, "balance": balance})
        wb.write()

        if len(changed_balances) > 0:
            await eventStorage.save_changed_balances(changed_balances)

    @staticmethod
    async def save_changed_balances(balances):
        with tokenHolderChangedDB.write_batch() as wb:
            for changed in balances:
                wb.put(changed.get("key").encode(), json.dumps({"ts": int(time.time()), "account": changed.get("balance")}).encode())

    @staticmethod
    def get_changed_balances():
        return tokenHolderChangedDB.iterator()

    @staticmethod
    def delete_balance(key):
        return tokenHolderChangedDB.delete(key)

    @staticmethod
    def get_token_holders():
        return tokenHolderDB.iterator(include_key=False)

    @staticmethod
    def get_block_iterator():
        return blockDB.iterator(include_key=False)
    
    @staticmethod
    async def recreate_events_index():
        events = []
        inter_counter = 0
        for items in eventDB.iterator():
            key = items[0].decode()
            event = json.loads(items[1].decode())
            event["block"] = json.loads(eventStorage.get_block(event["block_hash"]))
            events.append(event)
            inter_counter += 1
            print("recreate index for event", key)
            eventDB.delete(key.encode())
            eventIndexDB.delete(key.encode())
            if inter_counter > 50:
                await eventStorage.save_events(events)
                events = []

        if len(events) > 0:
            await eventStorage.save_events(events)            

"""
    @staticmethod
    async def check_duplicated_events_operation_hash():
        operation_hash = []
        event_op = {}
        for items in eventDB.iterator():
            event = json.loads(items[1].decode())
            if event["operation_hash"] in operation_hash:
                print("Founded", event, "\n")
                print(event_op[event["operation_hash"]])
                exit()
            else:
                operation_hash.append(event["operation_hash"])
                event_op[event["operation_hash"]] = event
"""
