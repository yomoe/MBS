import logging

from fastapi import FastAPI

from app.routers import routers
from app.setup_logging import setup_logging

app = FastAPI()

for router in routers:
    app.include_router(router)

setup_logging()

logger = logging.getLogger(__name__)


@app.get("/")
async def root():
    logger.info("Запрошена главная страница.")
    return {"message": "Hello World"}


@app.get("/hell/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}
