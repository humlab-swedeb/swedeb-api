
from fastapi import FastAPI # Response
from fastapi.middleware.cors import CORSMiddleware
from api_swedeb.api.utils.corpus import load_corpus
#import json


from api_swedeb.api import tools, metadata





app = FastAPI()


loaded_corpus = load_corpus()


origins = ['http://localhost:8080'] # http://localhost:8080

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=['GET'],
    allow_headers=[],
    allow_credentials=True,
)



app.include_router(tools.router)
app.include_router(metadata.router)



# @app.get("/")
# def read_root():
#    data = {"Det finns inget här": "Inget alls, bara åäö"}
#    json_data = json.dumps(data, ensure_ascii=False).encode('utf8')  # Encode as UTF-8
#    return Response(content=json_data, media_type="application/json; charset=utf-8")


