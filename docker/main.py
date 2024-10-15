import multiprocessing
import os

from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api_swedeb.api import metadata_router, tool_router
from api_swedeb.core.configuration import ConfigStore

ConfigStore.configure_context(source=os.environ.get("CONFIG_FILENAME", "config/config.yml"))

# https://stackoverflow.com/questions/65686318/sharing-python-objects-across-multiple-workers

shared_data: dict = multiprocessing.Manager().dict()

@asynccontextmanager
async def lifespan(app: FastAPI):
    shared_data["tools-payload"] = None
    yield
    shared_data.clear()

app = FastAPI(lifespan=lifespan)

app.mount("/public", StaticFiles(directory="public"), name="public")

app.add_middleware(
    CORSMiddleware,
    allow_methods=["GET", "POST"],
    allow_headers=[],
    allow_credentials=True,
)

app.include_router(tool_router.router)
app.include_router(metadata_router.router)
