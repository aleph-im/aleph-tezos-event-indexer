import asyncio
import itertools
from .utils.common import gather_with_concurrency
from .utils.aleph_balance_tracker import monitor_process

class Indexer:
    def __init__(self, client, storage, config):
        self.client = client
        self.config = config
        self.well_contract = config.well_contract
        self.until_block = config.until_block
        self.storage = storage
        self.concurrent_job = config.concurrent_job
        self.batch_size = config.batch_size + 1
        self.pending_blocks = 0
        self.current_head = None
        self.fetcher_state = {"recent_block": None, "oldest_block": None}

    async def run(self):
        if self.fetcher_state["recent_block"] is None:
            self.fetcher_state = self.storage.get_fetcher_state()

        print("run", self.pending_blocks)

        head = await self.client.get_block('head')
        if self.fetcher_state["recent_block"] is not None and self.pending_blocks == 0:
            first_run = self.fetcher_state["oldest_block"] is None
            if first_run:
                self.pending_blocks = self.batch_size
            else:
                self.pending_blocks = head["header"]["level"] - self.fetcher_state["recent_block"]["header"]["level"]
            self.current_head = head

        # default pending blocks, when database is empty
        if self.fetcher_state["recent_block"] is None and self.pending_blocks == 0:
            self.pending_blocks = self.batch_size
            self.current_head = head


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
        self.pending_blocks = self.batch_size

        if self.fetcher_state["oldest_block"] is not None:
            oldest_level = self.fetcher_state["oldest_block"]["header"]["level"]
            if oldest_level <= self.until_block:
                # reset counter for next run
                self.pending_blocks = 0
                return

            if oldest_level < self.pending_blocks:
                self.pending_blocks = oldest_level

        
        if self.pending_blocks > 0:
            await self.backward_run(self.fetcher_state["oldest_block"])

        # reset counter for next run
        self.pending_blocks = 0

    async def batch_run(self, from_block, direction):
        print("fetching", self.pending_blocks, "blocks starting from", from_block["hash"], "=>", from_block["header"]["level"])
        def _fetch_blocks(self, limit):
            total_fetched = 0
            print("limit", limit, self.pending_blocks)
            if self.pending_blocks < limit:
                limit = self.pending_blocks

            if direction == "forward":
                """ avoid holes """
                range_list = reversed(range(1, limit))
            else:
                range_list = range(1, limit)

            for index in range_list:
                if self.pending_blocks == 0 or total_fetched > 10:
                    total_fetched = 0
                    break

                cursor_id = "{}".format(from_block["header"]["level"] - index)
                print("fetching block", cursor_id)
                yield self.client.get_block(cursor_id)
                self.pending_blocks -= 1
                total_fetched += 1

        while self.pending_blocks > 0:
            yield await gather_with_concurrency(self.concurrent_job, *_fetch_blocks(self, self.pending_blocks))

    async def execute(self, blocks):
        if len(blocks) > 0:
            if "events" in self.config.objects:
                events = await gather_with_concurrency(len(blocks), *self.get_events(blocks))
                events = list(itertools.chain.from_iterable(events))
                print(len(events), "events found")
                await self.index(events)
            if "balances" in self.config.objects:
                balances = await gather_with_concurrency(len(blocks), *self.get_balances(blocks))
                balances = list(itertools.chain.from_iterable(balances))
                print(len(balances), "balances found")
                await self.index_balances(balances)
        
    async def fetch_blocks(self, from_block, direction="forward"):
        _blocks = []
        async for blocks in self.batch_run(from_block, direction):
            if direction == "forward":
                blocks.insert(0, from_block)
            print(len(blocks), "fetched")
            await self.execute(blocks)
            if len(_blocks) == 0:
                _blocks.insert(0, blocks[0])
                _blocks.insert(1, blocks[-1])
            else:
                _blocks.insert(1, blocks[-1])
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
            #await gather_with_concurrency(len(events), *self.storage.save_events(events))
            await self.storage.save_events(events)
            print(len(events), "saved")
            task = asyncio.create_task(self.check_events(events))

    def get_balances(self, blocks):
        for block in blocks:
            yield self.client.get_balances(block, self.config.token_address, self.config.token_ids)

    async def index_balances(self, balances):
        if len(balances) > 0:
            await self.storage.save_balances(self.config.token_address, balances)
            await monitor_process()
            

    def update_fetcher_state(self, recent_block = None, oldest_block = None):
        if recent_block is not None:
            self.fetcher_state["recent_block"] = recent_block
        if oldest_block is not None:
            self.fetcher_state["oldest_block"] = oldest_block

        self.storage.update_fetcher_state(recent_block=recent_block, oldest_block=oldest_block)

    async def check_events(self, events):
        for event in events:
            verified = False
            operation = self.client.get_operation_from_block(event["block"], event["operation_hash"])
            # pass 1 internal check
            if operation is not None:
                is_valid = self.client.check_operation(operation, event["operation_hash"], self.well_contract)
                if is_valid == False:
                    self.storage.untrust_event(event)
                    continue

            # pass 2 compare and check with trusted endpoint
            trusted_operation = await self.client.get_operation(event["block_hash"], event["operation_hash"], endpoint=self.config.trusted_rpc_endpoint)
            if trusted_operation is not None:
                is_valid = self.client.check_operation(trusted_operation, event["operation_hash"], self.well_contract)
                if is_valid == False:
                    self.storage.untrust_event(event)
                    continue

            self.storage.trust_event(event)
