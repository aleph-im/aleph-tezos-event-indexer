import requests
from pytezos.michelson.types import MichelsonType
from pytezos.michelson.parse import michelson_to_micheline

# Test event can be found between block number 545848 and 545853
well_contract = "KT1HWM5bNaTPvDjj1f8GxV3F6AXFj9mBFePt"

endpoint = "https://rpc.tzkt.io/ghostnet"
block_id = "head"

# Events type as defined by Archetype, cf https://github.com/completium/event-well-crank/blob/main/src/crank.ts#L23
parser = MichelsonType.match(
    michelson_to_micheline(
        "pair (string %_kind) (pair (string %_type) (bytes %_event))"
    )
)


def parse_event(event_bytes):
    # First unpacking to get the kind, the type and the data bytes of the event
    event = parser.unpack(bytes.fromhex(event_bytes)).to_python_object()

    # Second unpacking to get the data from the bytes
    parser2 = MichelsonType.match(michelson_to_micheline(event["_type"]))

    event["_event"] = parser2.unpack(event["_event"]).to_python_object()
    return event


def get_event_of(res, contract):
    for operationsArr in res["operations"]:
        for operation in operationsArr:
            for tx in operation["contents"]:
                if "internal_operation_results" in tx["metadata"]:
                    for internal_tx in tx["metadata"]["internal_operation_results"]:
                        print("have internal... for", internal_tx["destination"])
                        # if internal_tx['destination'] == contract:
                        if internal_tx["source"] == contract:
                            print("\n\n")
                            print("\n\n")
                            print(
                                "     Sender: {}, Parameters: {}".format(
                                    internal_tx["source"], internal_tx["parameters"]
                                )
                            )
                            event_bytes = internal_tx["parameters"]["value"]["bytes"]
                            print(parse_event(event_bytes))
                            break


def fetch_blocks(block_id="head", limit=10, until_block_level=545000):
    if limit == 0:
        print("Limit reached, exit...")
        return

    response = requests.get(endpoint + "/chains/main/blocks/{}".format(block_id))
    res = response.json()
    block_level = res["header"]["level"]
    print("fetch block", block_level, block_id)
    get_event_of(res, well_contract)

    if block_level < until_block_level:
        print("max block reached")
        return

    limit = limit - 1
    fetch_blocks(res["hash"] + "~1", limit, until_block_level)


fetch_blocks("BMMLTBM71hFduyCrgvztrpJFVdTw35MkXRjxEwEEa7GM81Ps64q~1", 5000, 545848)
