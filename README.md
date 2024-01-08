### Outline of an API for Swedeb


Run:  ```uvicorn main:app --reload```     



```
├── README.md
├── api_swedeb
│   ├── __init__.py
│   ├── api
```
#### RETURNS MINIMAL DUMMY DATA FOR ENDPOINTS
```
│   │   ├── dummy_data
│   │   │   ├── dummy_kwic.py
│   │   │   ├── dummy_meta.py
│   │   │   ├── dummy_ngrams.py
│   │   │   ├── dummy_speech.py
│   │   │   ├── dummy_topics.py
│   │   │   └── dummy_wt.py
```
#### ENDPOINTS FOR METDATA AND TOOLS (KWIC, WORD TRENDS ETC.)
```
│   │   ├── metadata.py
│   │   ├── tools.py
```
#### PLACEHOLDER FOR ACTUAL DATA (TO REPLACE DUMMY)
```
│   │   └── utils 
│   │       ├── kwic.py
│   │       ├── metadata.py
│   │       ├── ngrams.py
│   │       ├── speech.py
│   │       ├── topics.py
│   │       └── word_trends.py
```
#### PYDANDIC SCHEMAS FOR RESPONSE MODELS
```
│   └── schemas 
│       ├── __init__.py
│       ├── kwic_schema.py
│       ├── metadata_schema.py
│       ├── ngrams_schema.py
│       ├── sort_order.py
│       ├── speech_text_schema.py
│       ├── speeches_schema.py
│       ├── topics_schema.py
│       └── word_trends_schema.py
```
### MAIN
```
├── main.py
├── poetry.lock
├── pyproject.toml
```
### TESTS
```
└── tests 
    ├── __init__.py
    └── test_endpoints.py

```