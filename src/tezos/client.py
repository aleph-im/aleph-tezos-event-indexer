import aiohttp
import time
from pytezos.michelson.types import MichelsonType
from pytezos.michelson.parse import michelson_to_micheline
from pytezos.operation.group import OperationGroup
from pytezos.michelson.types.core import unit
from pytezos import pytezos
import json

import traceback

class TezosClient:
    def __init__(self, config):
        self.endpoint = config.rpc_endpoint
        self.event_parser = MichelsonType.match(michelson_to_micheline('pair (string %type) (pair (string %format) (bytes %metadata))'))

    async def get_json(self, url: str, status_codes=[200], retry = 10):
        print("fetch...", url)
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as resp:
                    if resp.status not in status_codes:
                        raise Exception("Error: {}".format(resp.status))
                    return await resp.json()
            except aiohttp.ClientConnectorError as err:
                print("got", err, "Cool down for 120s...")
                time.sleep(120)
                return await self.get_json(url, status_codes=status_codes, retry=retry)
            except Exception as err:
                print("got", err, "Cool down for 10s...")
                traceback.print_exc()
                time.sleep(10)
                retry -= 1
                if retry == 0:
                    print("Max retry reached")
                    raise Exception(err)
                return await self.get_json(url, status_codes=status_codes, retry=retry)

    async def get_block(self, block_id, endpoint=None):
        endpoint = endpoint or self.endpoint
        url = endpoint + "/chains/main/blocks/{}".format(block_id)
        return await self.get_json(url)

    def get_operation_from_block(self, block, operation_hash):
        for operationsArr in block["operations"]:
            for operation in operationsArr:
                if operation["hash"] == operation_hash:
                    return operation
        return None

    async def get_operation(self, block_id, operation_hash, endpoint=None):
        endpoint = endpoint or self.endpoint
        url = endpoint + "/chains/main/blocks/{}".format(block_id)
        block = await self.get_json(url)
        return self.get_operation_from_block(block, operation_hash)

    # @DEPRECATED
    def parse_event(self, event_bytes):
        # First unpacking to get the kind, the type and the data bytes of the event
        event = self.event_parser.unpack(bytes.fromhex(event_bytes)).to_python_object()

        # Second unpacking to get the data from the bytes
        data_parser = MichelsonType.match(michelson_to_micheline(event['format']))
        event['metadata'] = data_parser.unpack(event['metadata']).to_python_object()
        if isinstance(event["metadata"], unit):
            event['metadata'] = None
        return event

    def create_event(self, internal_op):
        if internal_op.get("type") == None or internal_op.get("payload") == None or internal_op.get("tag") == None:
            return None

        event_parser = MichelsonType.match(internal_op["type"])
        event = event_parser.from_micheline_value(internal_op["payload"]).to_python_object()
        event = self.decode_dict(event)
        if isinstance(event, bytes):
            try:
                event = json.loads(event)
            except:
                print("event decode failed =>", event)
                event = internal_op["payload"]
        return { "_kind": internal_op["tag"], "_event": event }

    async def get_events(self, block, well_contract):
        events = []
        for operationsArr in block["operations"]:
            for operation in operationsArr:
                for tx in operation['contents']:
                    if 'metadata' in tx and 'internal_operation_results' in tx['metadata']:
                        for internal_op in tx['metadata']['internal_operation_results']:
                            if internal_op["kind"] != "event" or internal_op['result']['status'] != 'applied':
                                continue
                            #if internal_op['source'] !== __FILTER_BY_SOURCE__

                            _event = self.create_event(internal_op)
                            if _event is None:
                                continue
                            events.append({**{
                                "nonce": internal_op["nonce"],
                                "timestamp": block["header"]["timestamp"],
                                "block_hash": block['hash'],
                                "block_level": block["header"]["level"],
                                "operation_hash": operation["hash"],
                                "source": internal_op["source"],
                                "block": block,
                                "verified": False
                            },**_event})

        return events

    def check_operation(self, operation, operation_hash, trusted_contract):
        for tx in operation['contents']:
            if 'metadata' in tx and 'internal_operation_results' in tx['metadata']:
                for internal_op in tx['metadata']['internal_operation_results']:
                    op = OperationGroup(protocol=operation["protocol"], branch=operation["branch"], chain_id=operation["chain_id"], contents=operation["contents"], signature=operation["signature"], context=pytezos)
                    if op.hash() != operation_hash:
                        return False
        return True

    def decode_dict(self, d):
        result = {}
        for key, value in d.items():
            if isinstance(key, bytes):
                key = key.decode()
            if isinstance(value, bytes):
                value = value.decode()
            elif isinstance(value, dict):
                value = decode_dict(value)
            result.update({key: value})
        return result
