"""Worker process for running Agent review tasks."""
import asyncio
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


async def main():
    print("Worker started. Waiting for review tasks...")
    while True:
        await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())
