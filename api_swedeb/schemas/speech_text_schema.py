from pydantic import BaseModel, Field


class SpeechesTextResultItem(BaseModel):
    speaker_note: str | None = Field(None, description="Speaker note")
    speech_text: str | None = Field(None, description="Speech text")
    page_number: int | None = Field(None, description="Page number")
