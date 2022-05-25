import graphene
from graphene.types.generic import GenericScalar
#@TODO to fix
#from graphql.execution.executors.asyncio import AsyncioExecutor
import json
import itertools
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette_graphene3 import GraphQLApp, make_graphiql_handler, make_playground_handler
from .schema import types
from ..storage.event import eventStorage

class Query(graphene.ObjectType):
    events = graphene.List(types.Events, limit=graphene.Int(default_value=100, description="max value = 1000"),
                           reverse=graphene.Boolean(default_value=True),
                           skip=graphene.Int(default_value=0),
                           source=graphene.String(default_value=None, description="Source address"),
                           destination=graphene.String(default_value=None, description="Destination address"),
                           operation_hash=graphene.String(default_value=None, description="Operation hash"),
                           block_hash=graphene.String(default_value=None, description="Block hash"))
    async def resolve_events(self, info, limit, reverse, skip, source, destination, operation_hash, block_hash):
        max_limit = 1000
        if limit > max_limit:
            limit = max_limit

        address = None
        index_list_len = len(list(filter(None, [source, destination, operation_hash, block_hash])))

        if index_list_len > 0:
            # keep block_hash, operation_hash, source, destination order to reduce unnecessary reading
            address = block_hash or operation_hash or source or destination

        events = eventStorage.get_events(reverse=reverse, limit=limit, skip=skip, index_address=address)
        if index_list_len < 2:
            return events

        # filter if more than one criteria are provided
        idx_to_delete = []
        for idx, event in enumerate(events):
            if source is not None and source != event["source"]:
                idx_to_delete.append(idx)
                continue
            if destination is not None and destination != event["destination"]:
                idx_to_delete.append(idx)
                continue
            if operation_hash is not None and operation_hash != event["operation_hash"]:
                idx_to_delete.append(idx)
                continue
            if block_hash is not None and block_hash != event["block_hash"]:
                idx_to_delete.append(idx)
                continue

        for idx in sorted(idx_to_delete, reverse=True):
            del events[idx]
        return events

    index_status = graphene.Field(types.IndexStatus)
    async def resolve_index_status(self, info):
        fetcher_state = eventStorage.get_fetcher_state()
        return {
            "oldest_block": fetcher_state["oldest_block"]["header"]["level"],
            "recent_block": fetcher_state["recent_block"]["header"]["level"]
        }


def startGraphQLServer():
    app = FastAPI()

    @app.get('/ping')
    async def ping():
        return 'OK'

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # @TODO to fix
    #app.add_route("/", GraphQLApp(schema=schema, executor_class=AsyncioExecutor))
    schema = graphene.Schema(query=Query)
    app.add_route("/", GraphQLApp(schema=schema, on_get=make_playground_handler()))
    return app

app = startGraphQLServer()
