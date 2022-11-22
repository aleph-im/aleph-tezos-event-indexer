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
from src.config import config

class Query(graphene.ObjectType):
    events = graphene.List(types.Event, limit=graphene.Int(default_value=100, description="max value = 1000"),
                           reverse=graphene.Boolean(default_value=True),
                           skip=graphene.Int(default_value=0),
                           **{"type": graphene.String(default_value=None, description="Event type, ex: burn_event. The multi match % joker can be used.")},
                           source=graphene.String(default_value=None, description="Source address"),
                           wildcard_address=graphene.String(default_value=None, description="WILDCARD address, this can be any address, source or a supported event metadata address (pkh, owner, from, to, address)"),
                           operation_hash=graphene.String(default_value=None, description="Operation hash"),
                           block_hash=graphene.String(default_value=None, description="Block hash"))
    async def resolve_events(self, info, **kwargs):
        limit = kwargs["limit"]
        reverse = kwargs["reverse"]
        skip = kwargs["skip"]
        target_type = kwargs["type"]
        source = kwargs["source"]
        wildcard_address = kwargs["wildcard_address"]
        operation_hash = kwargs["operation_hash"]
        block_hash = kwargs["block_hash"]
        
        max_limit = 1000
        if limit > max_limit:
            limit = max_limit

        address = None
        index_list_len = len(list(filter(None, [source, wildcard_address, operation_hash, block_hash])))

        if index_list_len > 0:
            # keep block_hash, operation_hash, source, order to reduce unnecessary reading
            address = block_hash or operation_hash or wildcard_address or source

        #events = eventStorage.get_events(reverse=reverse, limit=limit, skip=skip, index_address=address)
        events_iterator = eventStorage.get_events_iterator(reverse=reverse, index_address=address)
        if index_list_len < 2 and target_type is None:
            events = list(itertools.islice(events_iterator, skip, (limit+skip)))
            return [json.loads(event.decode()) for event in events]

        # soft filter
        #res_len = len(events)
        # @TODO continue ieteration until reach limit
        
        search_from_start = False
        search_from_end = False
        # filter if more than one criteria are provided
        idx_to_delete = []
        data  = []
        continue_iteration = True
        while continue_iteration:
            continue_iteration = False
            events = list(itertools.islice(events_iterator, 0, limit))
            for idx, event in enumerate(events):
                event = json.loads(event.decode())
                events[idx] = event

                if source is not None and source != event["source"]:
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
                        if event["_kind"].find(target_type) == -1:
                            idx_to_delete.append(idx)
                        continue
                    elif search_from_end:
                        if event["_kind"].endswith(target_type) is False:
                            idx_to_delete.append(idx)
                        continue
                    elif search_from_start:
                        if event["_kind"].startswith(target_type) is False:
                            idx_to_delete.append(idx)
                        continue
                    elif target_type != event["_kind"]:
                        idx_to_delete.append(idx)
                        continue

            for idx in sorted(idx_to_delete, reverse=True):
                del events[idx]
            idx_to_delete = []
            data = data + events
            if len(data) >= limit+skip:
                continue_iteration = False
            else:
                continue_iteration = True

        return data[skip:(limit+skip)]

    index_status = graphene.Field(types.IndexStatus)
    async def resolve_index_status(self, info):
        fetcher_state = eventStorage.get_fetcher_state()
        oldest_block_level = fetcher_state["oldest_block"]["header"]["level"]
        status = "in_progress"
        if oldest_block_level <= config.until_block or oldest_block_level == 0:
            status = "synced"

        return {
            "oldest_block": fetcher_state["oldest_block"]["header"]["level"],
            "recent_block": fetcher_state["recent_block"]["header"]["level"],
            "status": status
        }

    stats = graphene.Field(types.Stats, address=graphene.String(default_value=None, description="Account address"))
    async def resolve_stats(self, info, address):
        return await eventStorage.get_stats(address)

def startGraphQLServer():
    app = FastAPI(docs_url="/__aleph_api_doc")

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
