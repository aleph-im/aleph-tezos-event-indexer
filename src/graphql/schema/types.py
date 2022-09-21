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
    destination = String()
    type = String()
    format = String()
    metadata = GenericScalar()
    block = GenericScalar()
    verified = Boolean()
    nonce = Int()
    timestamp = String()

    # load block if requested
    def resolve_block(data, info):
        block = data["block"](data["block_hash"])
        if block:
            return json.loads(block)

class IndexStatus(ObjectType):
    oldest_block = String()
    recent_block = String()

class Stats(ObjectType):
    class Meta:
        description = "Stats"

    first_event = Field(Event)
    last_event = Field(Event)
    total_events = Int()
