import graphene
from graphene.types.generic import GenericScalar
#@TODO to fix
#from graphql.execution.executors.asyncio import AsyncioExecutor
import json
import itertools
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette_graphene3 import GraphQLApp, make_graphiql_handler, make_playground_handler
from .schema import types
from ..storage.event import eventStorage

class Query(graphene.ObjectType):
    events = graphene.List(types.Events, limit=graphene.Int(default_value=100, description="max value = 1000"),
                           reverse=graphene.Boolean(default_value=True),
                           skip=graphene.Int(default_value=0),
                           **{"type": graphene.String(default_value=None, description="Event type, ex: burn_event. The multi match % joker can be used.")},
                           source=graphene.String(default_value=None, description="Source address"),
                           destination=graphene.String(default_value=None, description="Destination address"),
                           operation_hash=graphene.String(default_value=None, description="Operation hash"),
                           block_hash=graphene.String(default_value=None, description="Block hash"))
    async def resolve_events(self, info, **kwargs):
        limit = kwargs["limit"]
        reverse = kwargs["reverse"]
        skip = kwargs["skip"]
        target_type = kwargs["type"]
        source = kwargs["source"]
        destination = kwargs["destination"]
        operation_hash = kwargs["operation_hash"]
        block_hash = kwargs["block_hash"]
        
        max_limit = 1000
        if limit > max_limit:
            limit = max_limit

        address = None
        index_list_len = len(list(filter(None, [source, destination, operation_hash, block_hash])))

        if index_list_len > 0:
            # keep block_hash, operation_hash, source, destination order to reduce unnecessary reading
            address = block_hash or operation_hash or source or destination

        events = eventStorage.get_events(reverse=reverse, limit=limit, skip=skip, index_address=address)
        if index_list_len < 2 and target_type is None:
            return events

        # soft filter
        #res_len = len(events)
        # @TODO continue ieteration until reach limit
        
        search_from_start = False
        search_from_end = False
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
            if target_type is not None:
                if target_type.find("%") == 0:
                    target_type = target_type[1::]
                    search_from_end = True
                if target_type.find("%") > 0:
                    target_type = target_type[:-1:]
                    search_from_start = True

                if search_from_end and search_from_start:
                    if event["type"].find(target_type) == -1:
                        idx_to_delete.append(idx)
                    continue
                elif search_from_end:
                    if event["type"].endswith(target_type) is False:
                        idx_to_delete.append(idx)
                    continue
                elif search_from_start:
                    if event["type"].startswith(target_type) is False:
                        idx_to_delete.append(idx)
                    continue
                elif target_type != event["type"]:
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

    app.add_middleware(GZipMiddleware, minimum_size=1000)
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
