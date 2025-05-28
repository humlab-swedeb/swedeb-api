from pydantic import BaseModel, Field


class SpeechesTextResultItem(BaseModel):
    speaker_note: str = Field(None, description="Speaker note")
    speech_text: str = Field(None, description="Speech text")
    page_number: int = Field(None, description="Page number")
