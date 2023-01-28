import asyncio
import aiohttp
import time
from pytezos.michelson.types import MichelsonType
from pytezos.michelson.parse import michelson_to_micheline
from pytezos.operation.group import OperationGroup
from pytezos.michelson.types.core import unit
from pytezos import pytezos
import json
from collections import defaultdict

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
                await asyncio.sleep(120)
                return await self.get_json(url, status_codes=status_codes, retry=retry)
            except Exception as err:
                print("got", err, "Cool down for 10s...")
                traceback.print_exc()
                await asyncio.sleep(10)
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
        if internal_op.get("type") == None or internal_op.get("payload") == None:
            return None

        event_parser = MichelsonType.match(internal_op["type"])
        event = event_parser.from_micheline_value(internal_op["payload"]).to_python_object()
        if isinstance(event, dict):
            event = self.decode_dict(event)

        if isinstance(event, bytes):
            try:
                event = json.loads(event)
            except:
                print("event decode failed =>", event)
                event = internal_op["payload"]
        return { "_kind": internal_op.get("tag"), "_event": event }

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
        for tx in operation["contents"]:
            if "metadata" in tx and "internal_operation_results" in tx["metadata"]:
                for internal_op in tx["metadata"]["internal_operation_results"]:
                    op = OperationGroup(protocol=operation["protocol"], branch=operation["branch"], chain_id=operation["chain_id"], contents=operation["contents"], signature=operation["signature"], context=pytezos)
                    if op.hash() != operation_hash:
                        return False
        return True

    def decode_dict(self, d):
        result = {}

        if isinstance(d, list):
            for list_id, list_value in enumerate(d):
                d[list_id] = self.decode_dict(list_value)
            return d
        elif not isinstance(d, dict):
            return d

        for key, value in d.items():
            if isinstance(key, bytes):
                key = key.decode()
            elif not isinstance(key, str):
                try:
                    key = repr(key)
                except:
                    pass
 
            if isinstance(value, bytes):
                value = value.decode()
            elif isinstance(value, dict):
                value = self.decode_dict(value)
            elif isinstance(value, list):
                for list_id, list_value in enumerate(value):
                    value[list_id] = self.decode_dict(list_value)
            elif not isinstance(value, str):
                # convert an unexpected custom type to a represented version
                try:
                    value = repr(value)
                except:
                    pass
 
            result.update({key: value})
        return result

    def decode_token_txs(self, token_cls, op):
        txs = {"transfer": [], "tokens": []}
        for tx in op["contents"]:
            if tx["kind"] == "transaction" and tx["destination"] == token_cls.address:
                if tx["parameters"]["entrypoint"] == "transfer":
                    txs["transfer"] += token_cls.transfer.decode(tx["parameters"]["value"])["transfer"]

            # mint or burn
            if "metadata" in tx and "internal_operation_results" in tx["metadata"]:
                for internal_op in tx["metadata"]["internal_operation_results"]:
                    if internal_op["kind"] == "transaction" and internal_op["destination"] == token_cls.address:
                        if internal_op["parameters"]["entrypoint"] == "tokens":
                            decoded = token_cls.tokens.decode(internal_op["parameters"]["value"])
                            if decoded.get("mint_tokens"):
                                txs["tokens"] += decoded.get("mint_tokens")
                            if decoded.get("burn_tokens"):
                                txs["tokens"] += decoded.get("burn_tokens")

        return txs

    def get_token_holders(self, token_cls, block):
        holders = defaultdict(list)

        for operationsArr in block["operations"]:
            for op in operationsArr:
                txs = self.decode_token_txs(token_cls, op)
                for transfer in txs["transfer"]:
                    for _transfer in transfer["txs"]:
                        holders[_transfer["token_id"]].append(_transfer["to_"])

                for burn_or_mint in txs["tokens"]:
                    holders[burn_or_mint["token_id"]].append(burn_or_mint["owner"])

        return holders

    async def get_balances(self, block, contract, token_ids):
        balances = []
        token_cls = pytezos.using(shell=self.endpoint).contract(contract)
        # @TODO token_cls._get_token_metadata(10) fail
        holders = self.get_token_holders(token_cls, block)

        for token_id in token_ids:
            token_holders = holders.get(token_id)
            if token_holders is None:
                continue

            current_block = await self.get_block("head")
            current_block_level = current_block["header"]["level"]
            
            for address in list(set(token_holders)):
                response = token_cls.balance_of(requests=[{"owner": address, "token_id": token_id}], callback=None).callback_view()[0]
                if type(response) is dict:
                    response = list(response.values())
                    balance = response[1]/10**18 # !Only for token_id 10
                    balances.append({"address": address, "balance": balance, "token_id": token_id, "block_level": current_block_level})
                
        return balances
