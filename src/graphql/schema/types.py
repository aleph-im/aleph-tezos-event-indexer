from graphene import ObjectType, String, Float, Int, List, JSONString, Field, Boolean
from graphene.types.generic import GenericScalar
import json

class Event(ObjectType):
    class Meta:
        description = "Events"

    block_hash = String()
    block_level = Int()
    operation_hash = String()
    source = String()
    format = String()
    block = GenericScalar()
    verified = Boolean()
    nonce = Int()
    timestamp = String()
    _tag = String()
    _event = GenericScalar()

    # load block if requested
    def resolve_block(data, info):
        block = data["block"](data["block_hash"])
        if block:
            return json.loads(block)

    def resolve_tag(data, info):
        return data["_kind"]

class IndexStatus(ObjectType):
    oldest_block = String()
    recent_block = String()

class Stats(ObjectType):
    class Meta:
        description = "Stats"

    first_event = Field(Event)
    last_event = Field(Event)
    total_events = Int()
