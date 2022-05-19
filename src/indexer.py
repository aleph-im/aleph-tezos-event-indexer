import asyncio
import aiohttp
import itertools
import time
from .utils.common import gather_with_concurrency

class Indexer:
    def __init__(self, client, storage, config):
        self.client = client
        self.storage = storage
        self.concurrent_job = config.concurrent_job
        self.batch_size = config.batch_size
        self.pending_blocks = 0
        self.current_head = None
        self.until_block = None
        self.fetcher_state = {"recent_block": None, "oldest_block": None}

    async def run(self):
        if self.fetcher_state["recent_block"] is None:
            self.fetcher_state = self.storage.get_fetcher_state()

        print("run", self.pending_blocks)

        if self.fetcher_state["recent_block"] is not None and self.pending_blocks == 0:
            head = await self.client.get_block('head')
            self.pending_blocks = head["header"]["level"] - self.fetcher_state["recent_block"]["header"]["level"]
            self.current_head = head

        # default pending blocks, when database is empty
        if self.fetcher_state["recent_block"] is None and self.pending_blocks == 0:
            head = await self.client.get_block('head')
            self.pending_blocks = self.concurrent_job*self.batch_size
            self.current_head = await self.client.get_block('head')


        # parallel forward and backward
        #tasks = []
        #if self.pending_blocks > 0:
        #    tasks.append(self.forward_run(self.current_head))

        #if self.fetcher_state["oldest_block"] is not None:
        #    tasks.append(self.backward_run(self.fetcher_state["oldest_block"]))

        #await asyncio.gather(*tasks)

        while self.pending_blocks > 0:
            await self.forward_run(self.current_head)

        self.pending_blocks = self.concurrent_job*self.batch_size
        await self.backward_run(self.fetcher_state["oldest_block"])



    async def batch_run(self, from_block):
        print("fetching", self.concurrent_job, "blocks starting from", from_block["hash"], "=>", from_block["header"]["level"])
        def _fetch_blocks(self, limit):
            if self.pending_blocks < limit:
                limit = self.pending_blocks

            print("limit", limit, self.pending_blocks)
            for index in range(1, limit):
                if self.pending_blocks == 0:
                    break

                #cursor_id = from_block["hash"] + "~" + str(self.pending_blocks - index)
                cursor_id = "{}~{}".format(from_block["hash"], index)
                print("fetching block", cursor_id)
                yield self.client.get_block(cursor_id)

            # reduce cursor
            self.pending_blocks -= limit

        return await gather_with_concurrency(self.concurrent_job, *_fetch_blocks(self, self.pending_blocks))

    async def fetch_blocks(self, from_block, direction="forward", until_block=None):
        blocks = await self.batch_run(from_block)
        if direction == "forward":
            blocks.insert(0, from_block)
        print(len(blocks), "fetched")
        if len(blocks) > 0:
            events = await gather_with_concurrency(len(blocks), *self.get_events(blocks))
            events = list(itertools.chain.from_iterable(events))
            print(len(events), "events found", events)
            await self.index(events)
        return blocks

    async def forward_run(self, from_block):
        print("forward_fetch")
        blocks = await self.fetch_blocks(from_block, until_block=self.fetcher_state["recent_block"])
        recent_block=blocks[0]

        # for first run
        oldest_block=None
        if self.fetcher_state["oldest_block"] is None:
            oldest_block=blocks[-1]
        self.update_fetcher_state(recent_block=recent_block, oldest_block=oldest_block)

    async def backward_run(self, from_block):
        print("backward_fetch")
        blocks = await self.fetch_blocks(from_block)
        self.update_fetcher_state(oldest_block=blocks[-1])

    def get_events(self, blocks):
        for block in blocks:
            yield self.client.get_events(block)

    async def index(self, events):
        if len(events) > 0:
            await gather_with_concurrency(len(events), *self.storage.save_events(events))
            print(len(events), "saved")

    def update_fetcher_state(self, recent_block = None, oldest_block = None):
        if recent_block is not None:
            self.fetcher_state["recent_block"] = recent_block
        if oldest_block is not None:
            self.fetcher_state["oldest_block"] = oldest_block

        self.storage.update_fetcher_state(recent_block=recent_block, oldest_block=oldest_block)
            
