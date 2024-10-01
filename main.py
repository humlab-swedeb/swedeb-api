from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api_swedeb.api import metadata_router, tool_router
from api_swedeb.core.configuration import ConfigStore, ConfigValue

ConfigStore.configure_context(source='config/config.yml')

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=ConfigValue("fastapi.origins").resolve(),
    allow_methods=['GET', 'POST'],
    allow_headers=[],
    allow_credentials=True,
)

app.include_router(tool_router.router)
app.include_router(metadata_router.router)
