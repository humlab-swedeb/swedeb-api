from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api_swedeb.api import metadata_router, tool_router
from api_swedeb.core.configuration import ConfigStore

ConfigStore.configure_context(source="config/config.yml")

app = FastAPI()

# origins = [f"http://localhost:{os.environ.get('SWEDEB_PORT', '8080')}"]

app.mount("/public", StaticFiles(directory="public"), name="public")

app.add_middleware(
    CORSMiddleware,
    # allow_origins=origins,
    allow_methods=["GET", "POST"],
    allow_headers=[],
    allow_credentials=True,
)

app.include_router(tool_router.router)
app.include_router(metadata_router.router)
