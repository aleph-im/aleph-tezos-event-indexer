import aiohttp
import time
from pytezos.michelson.types import MichelsonType
from pytezos.michelson.parse import michelson_to_micheline
from pytezos.operation.group import OperationGroup
from pytezos.michelson.types.core import unit
from pytezos import pytezos

import traceback

class TezosClient:
    def __init__(self, config):
        self.endpoint = config.rpc_endpoint
        self.event_parser = MichelsonType.match(michelson_to_micheline('pair (string %type) (pair (string %format) (bytes %metadata))'))

    async def get_json(self, url: str, status_codes=[200], retry = 10):
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

    def parse_event(self, event_bytes):
        # First unpacking to get the kind, the type and the data bytes of the event
        event = self.event_parser.unpack(bytes.fromhex(event_bytes)).to_python_object()

        # Second unpacking to get the data from the bytes
        data_parser = MichelsonType.match(michelson_to_micheline(event['format']))
        event['metadata'] = data_parser.unpack(event['metadata']).to_python_object()
        if isinstance(event["metadata"], unit):
            event['metadata'] = None
        return event

    async def get_events(self, block, well_contract):
        events = []
        for operationsArr in block["operations"]:
            for operation in operationsArr:
                for tx in operation['contents']:
                    if 'metadata' in tx and 'internal_operation_results' in tx['metadata']:
                        for internal_tx in tx['metadata']['internal_operation_results']:
                            if 'destination' in internal_tx and internal_tx['destination'] != well_contract:
                                continue
                            if 'parameters' not in internal_tx:
                                continue
                            if internal_tx['parameters']['entrypoint'] != 'event':
                                continue
                            if 'bytes' not in internal_tx['parameters']['value']:
                                continue

                            event_bytes = internal_tx['parameters']['value']['bytes']
                            _event = self.parse_event(event_bytes)
                            events.append({**{
                                "nonce": internal_tx["nonce"],
                                "timestamp": block["header"]["timestamp"],
                                "block_hash": block['hash'],
                                "block_level": block["header"]["level"],
                                "operation_hash": operation["hash"],
                                "source": internal_tx["source"],
                                "destination": internal_tx["destination"],
                                "block": block,
                                "verified": False
                            },**_event})

        return events

    def check_operation(self, operation, operation_hash, trusted_contract):
        for tx in operation['contents']:
            if 'metadata' in tx and 'internal_operation_results' in tx['metadata']:
                for internal_tx in tx['metadata']['internal_operation_results']:
                    if 'destination' in internal_tx and internal_tx['destination'] != trusted_contract:
                        continue
                    else:
                        op = OperationGroup(protocol=operation["protocol"], branch=operation["branch"], chain_id=operation["chain_id"], contents=operation["contents"], signature=operation["signature"], context=pytezos)
                        return op.hash() == operation_hash
        return False
