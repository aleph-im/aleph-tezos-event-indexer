import aiohttp
from pytezos.michelson.types import MichelsonType
from pytezos.michelson.parse import michelson_to_micheline


class TezosClient:
    def __init__(self, config):
        self.endpoint = config.rpc_endpoint
        self.event_parser = MichelsonType.match(michelson_to_micheline('pair (string %_kind) (pair (string %_type) (bytes %_event))'))

    async def get_block(self, block_id):
        async with  aiohttp.ClientSession() as session:
            url = self.endpoint + "/chains/main/blocks/{}".format(block_id)
            async with session.get(url) as resp:
                return await resp.json()

    def parse_event(self, event_bytes):
        # First unpacking to get the kind, the type and the data bytes of the event
        event = self.event_parser.unpack(bytes.fromhex(event_bytes)).to_python_object()

        # Second unpacking to get the data from the bytes
        data_parser = MichelsonType.match(michelson_to_micheline(event['_type']))
        event['_event'] = data_parser.unpack(event['_event']).to_python_object()
        return event

    async def get_events(self, block):
        events = []
        for operationsArr in block["operations"]:
            for operation in operationsArr:
                for tx in operation['contents']:
                    if 'internal_operation_results' in tx['metadata']:
                        for internal_tx in tx['metadata']['internal_operation_results']:
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
                                "event": _event
                            })

        return events
