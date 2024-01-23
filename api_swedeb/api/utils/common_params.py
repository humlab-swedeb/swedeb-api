from typing import List
from fastapi import Query

year_regex = r"^\d{4}$"

class CommonQueryParams:
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
        self.from_year = from_year
        self.to_year = to_year
        self.office_types = office_types
        self.sub_office_types = sub_office_types
        self.speaker_ids = speaker_ids
        self.sort_by = sort_by
        self.parties = parties
        self.genders = genders
        self.chambers = chambers
        self.limit = limit
        self.offset = offset
        self.sort_order = sort_order