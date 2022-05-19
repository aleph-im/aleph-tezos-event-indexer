import asyncio

async def setInterval(interval, func):
    while True:
        await asyncio.gather(
            asyncio.sleep(interval),
            func()
        )

async def gather_with_concurrency(n, *tasks):
    semaphore = asyncio.Semaphore(n)

    async def sem_task(task):
        async with semaphore:
            return await task
    return await asyncio.gather(*(sem_task(task) for task in tasks))
