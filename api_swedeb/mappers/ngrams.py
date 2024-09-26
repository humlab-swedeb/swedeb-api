import pandas as pd
from api_swedeb import schemas


def ngrams_to_ngram_result(ngrams: pd.DataFrame, sep=" ") -> schemas.NGramResult:
    """Convert ngrams ndataframe witg columns ngram and count inti sequence of NGramResultItems"""
    return schemas.NGramResult(
        ngram_list=[
            schemas.NGramResultItem(ngram=sep.join(x.ngram), count=x.count, documents=x.documents.split(","))
            for x in ngrams.itertuples(index=False)
        ]
    )
