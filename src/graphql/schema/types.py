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
    event = GenericScalar()
