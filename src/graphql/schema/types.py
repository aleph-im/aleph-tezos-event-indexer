from graphene import ObjectType, String, Int, Field, Boolean
from graphene.types.generic import GenericScalar


class Event(ObjectType):
    class Meta:
        description = "Events"

    block_hash = String()
    block_level = Int()
    operation_hash = String()
    source = String()
    format = String()
    verified = Boolean()
    nonce = Int()
    timestamp = String()
    type = String()
    payload = GenericScalar()
    _id = String(name="_id")

    def resolve_type(data):
        return data["_kind"]

    def resolve_payload(data):
        return data["_event"]


class IndexStatus(ObjectType):
    oldest_block = String()
    recent_block = String()
    status = String()


class Stats(ObjectType):
    class Meta:
        description = "Stats"

    first_event = Field(Event)
    last_event = Field(Event)
    total_events = Int()
