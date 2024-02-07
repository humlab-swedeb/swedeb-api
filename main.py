
from fastapi import FastAPI, Depends # Response
from fastapi.middleware.cors import CORSMiddleware
from api_swedeb.api.utils.corpus import load_corpus
from api_swedeb.api.utils.kwic_corpus import KwicCorpus
#import json


from api_swedeb.api import metadata_router, tool_router


def get_corpus():
    return load_corpus('.env_1960')


kwic_corpus = KwicCorpus(env_file='.env_1960')



app = FastAPI(dependencies=[Depends(get_corpus)])


loaded_corpus = get_corpus()


origins = ['http://localhost:8080'] 

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=['GET'],
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


