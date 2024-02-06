from typing import List
from fastapi import Query

year_regex = r"^\d{4}$"


class SpeakerQueryParams:
    def __init__(
        self,
        office_types: List[str] = Query(
            None, description="List of selected office types"
        ),
        sub_office_types: List[str] = Query(
            None, description="List of selected suboffice types"
        ),
        parties: List[str] = Query(None, description="List of selected parties"),
        genders: List[str] = Query(None, description="List of selected genders"),
        chambers: List[str] = Query(None, description="List of selected chambers"),
    ):
        self.offiece_types = office_types
        self.sub_office_types = sub_office_types
        self.parties = parties
        self.genders = genders
        self.chambers = chambers

    def get_selection_dict(self):
        # Currently returns gender_id and party_id, to mimic
        # prototype. who (speaker_id), was also included in the prototype, but
        # not included here yet. key for genders is gender_id, key for parties is party_id
        # and key for speaker id is who
        # if no selections are made, return empty dict
        selections = {}
        if self.parties:
            selections.update({"party_id": self.parties})
        if self.genders:
            selections.update({"gender_id": self.genders})

        return selections


class CommonQueryParams(SpeakerQueryParams):
    def __init__(
        self,
        from_year: str = Query(
            None,
            description="The first year to be included",
            pattern=year_regex,
        ),
        to_year: str = Query(
            None,
            description="The last year to be included",
            pattern=year_regex,
        ),
        office_types: List[str] = Query(
            None, description="List of selected office types"
        ),
        sub_office_types: List[str] = Query(
            None, description="List of selected suboffice types"
        ),
        speaker_ids: List[str] = Query(
            None,
            description="List of selected speaker ids. With this parameter, other metadata filters are unnecessary",
        ),
        sort_by: str = Query("year_title", description="Column to sort by"),
        parties: List[str] = Query(None, description="List of selected parties"),
        genders: List[str] = Query(None, description="List of selected genders"),
        chambers: List[str] = Query(None, description="List of selected chambers"),
        limit: int = Query(None, description="The number of results per page"),
        offset: int = Query(None, description="Result offset"),
        sort_order: str = Query("asc", description="Sort order. Default is asc"),
    ):
        super().__init__(office_types, sub_office_types, parties, genders, chambers)
        self.from_year = from_year
        self.to_year = to_year
        self.speaker_ids = speaker_ids
        self.sort_by = sort_by
        self.limit = limit
        self.offset = offset
        self.sort_order = sort_order

    def get_selection_dict(self):
        # Currently returns gender_id and party_id, to mimic
        # prototype. who (speaker_id), was also included in the prototype, but
        # not included here yet. key for genders is gender_id, key for parties is party_id
        # and key for speaker id is who
        # if no selections are made, return empty dict
        selections = {}
        if self.parties:
            selections.update({"party_id": self.parties})
        if self.genders:
            selections.update({"gender_id": self.genders})
        if self.speaker_ids:
            selections.update({"who": self.speaker_ids})
        return selections
