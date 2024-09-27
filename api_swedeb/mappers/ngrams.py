import pandas as pd
from api_swedeb import schemas


def ngrams_to_ngram_result(ngrams: pd.DataFrame, sep=" ") -> schemas.NGramResult:
    """Convert ngrams dataframe with column `ngram` and `window_count` into sequence of NGramResultItems"""
    return schemas.NGramResult(
        ngram_list=[
            schemas.NGramResultItem(ngram=x.Index, count=x.window_count, documents=x.documents.split(","))
            for x in ngrams.itertuples(index=True)
        ]
    )
