import asyncio
import aiohttp
import itertools
import time
from .utils.common import gather_with_concurrency

class Indexer:
    def __init__(self, client, storage, config):
        self.client = client
        self.well_contract = config.well_contract
        self.storage = storage
        self.concurrent_job = config.concurrent_job
        self.batch_size = config.batch_size
        self.pending_blocks = 0
        self.current_head = None
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

        if self.pending_blocks > 0:
            await self.forward_run(self.current_head)

        # retore blocks count to fetch for backward
        self.pending_blocks = self.concurrent_job*self.batch_size

        if self.fetcher_state["oldest_block"] is not None:
            oldest_level = self.fetcher_state["oldest_block"]["header"]["level"]
            if oldest_level < self.pending_blocks:
                self.pending_blocks = oldest_level

        
        if self.pending_blocks > 0:
            await self.backward_run(self.fetcher_state["oldest_block"])



    async def batch_run(self, from_block):
        print("fetching", self.pending_blocks, "blocks starting from", from_block["hash"], "=>", from_block["header"]["level"])
        def _fetch_blocks(self, limit):
            print("limit", limit, self.pending_blocks)
            if self.pending_blocks < limit:
                limit = self.pending_blocks

            for index in range(1, limit):
                if self.pending_blocks == 0:
                    break

                cursor_id = "{}~{}".format(from_block["hash"], index)
                print("fetching block", cursor_id)
                yield self.client.get_block(cursor_id)

            # reduce cursor
            self.pending_blocks -= limit

        return await gather_with_concurrency(self.concurrent_job, *_fetch_blocks(self, self.pending_blocks))

    async def fetch_blocks(self, from_block, direction="forward"):
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
        blocks = await self.fetch_blocks(from_block)
        recent_block=blocks[0]

        # for first run
        oldest_block=None
        if self.fetcher_state["oldest_block"] is None:
            oldest_block=blocks[-1]
        self.update_fetcher_state(recent_block=recent_block, oldest_block=oldest_block)

    async def backward_run(self, from_block):
        print("backward_fetch")
        blocks = await self.fetch_blocks(from_block, "backward")
        if len(blocks) > 0:
            self.update_fetcher_state(oldest_block=blocks[-1])

    def get_events(self, blocks):
        for block in blocks:
            yield self.client.get_events(block, self.well_contract)

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
            
