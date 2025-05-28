from typing import Optional

from .utility import DictLikeObject, fix_whitespace


class Speech(DictLikeObject):

    @property
    def speech_id(self) -> Optional[str]:
        return self._data.get("speech_id")

    @property
    def speaker(self) -> Optional[str]:
        return self._data.get("name")

    @property
    def paragraphs(self) -> list[str]:
        return self._data.get("paragraphs", [])

    @property
    def text(self) -> str:
        text: str = fix_whitespace("\n".join(self.paragraphs))
        return text

    @property
    def error(self) -> Optional[str]:
        return self._data.get("error")

    @property
    def page_number(self) -> Optional[int]:
        try:
            return int(self._data.get("page_number", 1))
        except (ValueError, TypeError):
            return 1

    @property
    def protocol_name(self) -> Optional[str]:
        return self._data.get("protocol_name")

    @property
    def office_type(self) -> Optional[str]:
        return self._data.get("office_type")

    @property
    def sub_office_type(self) -> Optional[str]:
        return self._data.get("sub_office_type")

    @property
    def gender(self) -> Optional[str]:
        return self._data.get("gender")

    @property
    def gender_abbrev(self) -> Optional[str]:
        return self._data.get("gender_abbrev")

    @property
    def party_abbrev(self) -> Optional[str]:
        return self._data.get("party_abbrev")

    @property
    def speaker_note(self) -> str:
        if "speaker_note_id" not in self._data:
            return ""
        if self._data["speaker_note_id"] == "missing":
            return "Talet saknar notering"
        return self._data["speaker_note"]

    # def ccc():
    #     speech: dict = self.service.nth(metadata=metadata, utterances=utterances, n=speech_nr - 1)
    #     speech_info: dict = self.get_speech_info(speech_name)
    #     speech.update(**speech_info)

    #         speech = {"name": f"speech {speech_name} not found", "error": str(ex)}
    #     except Exception as ex:  # pylint: disable=bare-except
    #         speech = {"name": f"speech {speech_name}", "error": str(ex)}
