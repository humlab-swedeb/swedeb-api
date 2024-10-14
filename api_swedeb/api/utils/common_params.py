from typing import List

from fastapi import Query

year_regex = r"^\d{4}$"

# pylint: disable=too-many-arguments


class SpeakerQueryParams:
    def __init__(
        self,
        office_types: List[str] = Query(None, description="List of selected office types"),
        sub_office_types: List[str] = Query(None, description="List of selected suboffice types"),
        party_id: List[int] = Query(None, description="List of selected parties"),
        gender_id: List[int] = Query(None, description="List of selected genders"),
        chambers: List[str] = Query(None, description="List of selected chambers"),
    ):
        self.office_types: List[str] = office_types
        self.sub_office_types: List[str] = sub_office_types
        self.party_id: List[int] = party_id
        self.gender_id: List[int] = gender_id
        self.chambers: List[str] = chambers

    def get_filter_opts(self, include_year: bool = True) -> dict[str, list[int]]:  # pylint: disable=unused-argument
        opts: dict[str, list[int]] = {
            # **({"office_id": self.office_types} if self.office_types else {}),
            # **({"sub_office_type_id": self.sub_office_types} if self.sub_office_types else {}),
            **({"party_id": self.party_id} if self.party_id else {}),
            **({"gender_id": self.gender_id} if self.gender_id else {}),
            **({"chamber_abbrev": self.chambers} if self.chambers else {}),
        }
        return opts


class CommonQueryParams(SpeakerQueryParams):
    def __init__(
        self,
        from_year: int = Query(None, description="The first year to be included"),
        to_year: int = Query(None, description="The last year to be included"),
        office_types: List[str] = Query(None, description="List of selected office types"),
        sub_office_types: List[str] = Query(None, description="List of selected suboffice types"),
        who: List[str] = Query(
            None,
            description="List of selected speaker ids. With this parameter, other metadata filters are unnecessary",
        ),
        sort_by: str = Query("year_title", description="Column to sort by"),
        party_id: List[int] = Query(None, description="List of selected parties"),
        gender_id: List[int] = Query(None, description="List of selected genders"),
        chambers: List[str] = Query(None, description="List of selected chambers"),
        speech_id: List[str] = Query(None, description="List of speech ids to filter by"),
        limit: int = Query(None, description="The number of results per page"),
        offset: int = Query(None, description="Result offset"),
        sort_order: str = Query("asc", description="Sort order. Default is asc"),
    ):
        super().__init__(office_types, sub_office_types, party_id, gender_id, chambers)
        self.from_year: int = from_year
        self.to_year: int = to_year
        self.speech_id: List[str] = speech_id
        self.who: List[str] = who
        self.sort_by: str = sort_by
        self.limit: int = limit
        self.offset: int = offset
        self.sort_order: str = sort_order

    def get_filter_opts(self, include_year: bool = True) -> dict[str, list[int]]:
        year_opts: dict = {}
        if include_year and (self.from_year or self.to_year):
            year_opts = {'year': (self.from_year or 0, self.to_year or 3000)}
        opts: dict[str, list[int]] = {
            **super().get_filter_opts(include_year),
            **({"person_id": self.who} if self.who else {}),
            **({"speech_id": self.speech_id} if self.speech_id else {}),
            **year_opts,
        }
        return opts
