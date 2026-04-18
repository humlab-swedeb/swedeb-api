import os

from api_swedeb.app import create_app

app = create_app(static_dir=os.environ.get("STATIC_DIR"))
