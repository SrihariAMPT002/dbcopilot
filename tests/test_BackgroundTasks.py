# from fastapi import FastAPI, BackgroundTasks

# app = FastAPI()

# @app.get("/test-bg")
# async def test_bg(background_tasks: BackgroundTasks):
#     def ping():
#         print("ping")

#     background_tasks.add_task(ping)
#     return {"ok": True}


import asyncio
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.semantics import generate_semantics
from app.db import get_db  # however you normally create a session

async def main():
    db: AsyncSession = await an_async_way_to_get_db_session()  # or your own factory
    bt = BackgroundTasks()

    resp = await generate_semantics(
        source_id=1,
        background_tasks=bt,
        db=db,
    )

    # Run the queued background tasks immediately for testing:
    await bt()  # important: this actually executes the tasks

    print(resp)

asyncio.run(main())