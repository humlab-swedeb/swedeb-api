"""Compatibility shim for the archived legacy speech lookup backend.

The implementation now lives under ``api_swedeb.legacy``. Keep this module as a
thin re-export layer until remaining imports are simplified or removed.
"""

from api_swedeb.legacy.load import Loader, ZipLoader
from api_swedeb.legacy.speech_lookup import SpeechTextRepository, SpeechTextService

__all__ = [
    "Loader",
    "ZipLoader",
    "SpeechTextRepository",
    "SpeechTextService",
]
