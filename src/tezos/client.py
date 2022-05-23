import aiohttp
import time
from pytezos.michelson.types import MichelsonType
from pytezos.michelson.parse import michelson_to_micheline


class TezosClient:
    def __init__(self, config):
        self.endpoint = config.rpc_endpoint
        self.event_parser = MichelsonType.match(michelson_to_micheline('pair (string %_kind) (pair (string %_type) (bytes %_event))'))

    async def get_json(self, url: str, status_codes=(200), retry = 10):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as resp:
                    if resp.status not in status_codes:
                        raise Exception("Error: {}".format(resp.status))
                    return await resp.json()
            except Exception as err:
                print("got", err, "Cool down for 10s...")
                time.sleep(10)
                retry -= 1
                if retry == 0:
                    print("Max retry reached")
                    raise Exception(err)
                return await self.get_json(url, status_codes=status_codes, retry=retry)

    async def get_block(self, block_id):
            url = self.endpoint + "/chains/main/blocks/{}".format(block_id)
            return await self.get_json(url)

    def parse_event(self, event_bytes):
        # First unpacking to get the kind, the type and the data bytes of the event
        event = self.event_parser.unpack(bytes.fromhex(event_bytes)).to_python_object()

        # Second unpacking to get the data from the bytes
        data_parser = MichelsonType.match(michelson_to_micheline(event['_type']))
        event['_event'] = data_parser.unpack(event['_event']).to_python_object()
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
                            print(block["hash"], operation["hash"], event_bytes)
                            _event = self.parse_event(event_bytes)
                            events.append({
                                "block_hash": block['hash'],
                                "block_level": block["header"]["level"],
                                "operation_hash": operation["hash"],
                                "source": internal_tx["source"],
                                "destination": internal_tx["destination"],
                                "event": _event,
                                "block": block
                            })

        return events
