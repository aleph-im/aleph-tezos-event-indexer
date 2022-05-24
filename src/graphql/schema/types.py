from graphene import ObjectType, String, Float, Int, List, JSONString, Field
from graphene.types.generic import GenericScalar
import json

class Events(ObjectType):
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

    # load block if requested
    def resolve_block(data, info):
        block = data["block"](data["block_hash"])
        if block:
            return json.loads(block)

class IndexStatus(ObjectType):
    oldest_block = String()
    recent_block = String()
