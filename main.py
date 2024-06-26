
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api_swedeb.api import metadata_router, tool_router

app = FastAPI()

origins = ['http://localhost:8080',
           'http://localhost:9002']



app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=['GET', 'POST'],
    allow_headers=[],
    allow_credentials=True,
)



app.include_router(tool_router.router)
app.include_router(metadata_router.router)



# @app.get("/")
# def read_root():
#    data = {"Det finns inget här": "Inget alls, bara åäö"}
#    json_data = json.dumps(data, ensure_ascii=False).encode('utf8')  # Encode as UTF-8
#    return Response(content=json_data, media_type="application/json; charset=utf-8")

