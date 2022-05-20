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
    events = graphene.List(types.Events, limit=graphene.Int(default_value=100),
                           reverse=graphene.Boolean(default_value=True),
                           skip=graphene.Int(default_value=0),
                           address=graphene.String(default_value=None))
    async def resolve_events(self, info, limit, reverse, skip, address):
        max_limit = 1000
        if limit > max_limit:
            limit = max_limit

        return eventStorage.get_events(reverse=reverse, limit=limit, skip=skip, index_address=address)

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
