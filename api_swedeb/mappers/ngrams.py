import pandas as pd
from api_swedeb import schemas


def ngrams_to_ngram_result(ngrams: pd.DataFrame) -> schemas.NGramResult:
    """Convert ngrams ndataframe witg columns ngram and count inti sequence of NGramResultItems"""
    return schemas.NGramResult(
        ngram_list=[
            schemas.NGramResultItem(ngram="".join(x.ngram), count=x.count)
            for x in ngrams.itertuples(index=False)
        ]
    )
