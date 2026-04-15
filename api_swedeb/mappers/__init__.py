# type: ignore

from .cqp_opts import query_params_to_CQP_criterias, query_params_to_CQP_opts
from .kwic import kwic_to_api_model
from .ngrams import ngrams_to_ngram_result
from .speeches import speeches_to_api_frame, speeches_to_api_model
from .word_trends import (
    search_hits_to_api_model,
    word_trend_speeches_to_api_model,
    word_trends_to_api_model,
)
