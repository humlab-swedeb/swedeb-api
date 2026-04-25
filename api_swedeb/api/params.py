"""Query parameter classes for FastAPI endpoints."""

from typing import Any, List, Self

import fastapi.params
from fastapi import Query

year_regex = r"^\d{4}$"

# pylint: disable=too-many-arguments


def build_filter_opts(
    *,
    from_year: int | None = None,
    to_year: int | None = None,
    who: list[str] | None = None,
    party_id: list[int] | None = None,
    gender_id: list[int] | None = None,
    chamber_abbrev: list[str] | None = None,
    speech_id: list[str] | None = None,
    include_year: bool = True,
) -> dict[str, Any]:
    year_opts: dict[str, dict[str, int]] = {}
    if include_year and (from_year or to_year):
        year_opts = {"year": {"low": from_year or 0, "high": to_year or 3000}}

    return {
        **({"party_id": party_id} if party_id else {}),
        **({"gender_id": gender_id} if gender_id else {}),
        **({"chamber_abbrev": chamber_abbrev} if chamber_abbrev else {}),
        **({"person_id": who} if who else {}),
        **({"speech_id": speech_id} if speech_id else {}),
        **year_opts,
    }


class SpeakerQueryParams:
    def __init__(
        self,
        office_types: List[str] | None = Query(None, description="List of selected office types"),
        sub_office_types: List[str] | None = Query(None, description="List of selected suboffice types"),
        party_id: List[int] | None = Query(None, description="List of selected parties"),
        gender_id: List[int] | None = Query(None, description="List of selected genders"),
        chamber_abbrev: List[str] | None = Query(None, description="List of selected chambers"),
    ):
        self.office_types: List[str] | None = office_types
        self.sub_office_types: List[str] | None = sub_office_types
        self.party_id: List[int] | None = party_id
        self.gender_id: List[int] | None = gender_id
        self.chamber_abbrev: List[str] | None = chamber_abbrev

    def get_filter_opts(
        self, include_year: bool = True
    ) -> dict[str, Any]:
        return build_filter_opts(
            party_id=self.party_id,
            gender_id=self.gender_id,
            chamber_abbrev=self.chamber_abbrev,
            include_year=include_year,
        )


class CommonQueryParams(SpeakerQueryParams):
    def __init__(
        self,
        from_year: int | None = Query(None, description="The first year to be included"),
        to_year: int | None = Query(None, description="The last year to be included"),
        office_types: List[str] | None = Query(None, description="List of selected office types"),
        sub_office_types: List[str] | None = Query(None, description="List of selected suboffice types"),
        who: List[str] | None = Query(
            None,
            description="List of selected speaker ids. With this parameter, other metadata filters are unnecessary",
        ),
        sort_by: str = Query("year_title", description="Column to sort by"),
        party_id: List[int] | None = Query(None, description="List of selected parties"),
        gender_id: List[int] | None = Query(None, description="List of selected genders"),
        chamber_abbrev: List[str] | None = Query(None, description="List of selected chambers"),
        speech_id: List[str] | None = Query(None, description="List of speech ids to filter by"),
        limit: int | None = Query(None, description="The number of results per page"),
        offset: int | None = Query(None, description="Result offset"),
        sort_order: str = Query("asc", description="Sort order. Default is asc"),
    ):
        super().__init__(office_types, sub_office_types, party_id, gender_id, chamber_abbrev)
        self.from_year: int | None = from_year
        self.to_year: int | None = to_year
        self.speech_id: List[str] | None = speech_id
        self.who: List[str] | None = who
        self.sort_by: str = sort_by
        self.limit: int | None = limit
        self.offset: int | None = offset
        self.sort_order: str = sort_order

    def get_filter_opts(self, include_year: bool = True) -> dict[str, dict[str, int]]:
        return build_filter_opts(
            from_year=self.from_year,
            to_year=self.to_year,
            who=self.who,
            party_id=self.party_id,
            gender_id=self.gender_id,
            chamber_abbrev=self.chamber_abbrev,
            speech_id=self.speech_id,
            include_year=include_year,
        )

    def resolve(self) -> Self:
        """Replaces all Query instances with their default values."""
        for key, value in self.__dict__.items():
            if isinstance(value, fastapi.params.Query):
                setattr(self, key, value.default)
        return self


def build_common_query_params(
    *,
    from_year: int | None = None,
    to_year: int | None = None,
    who: list[str] | None = None,
    party_id: list[int] | None = None,
    gender_id: list[int] | None = None,
    chamber_abbrev: list[str] | None = None,
    speech_id: list[str] | None = None,
    sort_by: str = "year_title",
    sort_order: str = "asc",
    limit: int | None = None,
    offset: int | None = None,
) -> CommonQueryParams:
    return CommonQueryParams(
        from_year=from_year,
        to_year=to_year,
        who=who,
        sort_by=sort_by,
        party_id=party_id,
        gender_id=gender_id,
        chamber_abbrev=chamber_abbrev,
        speech_id=speech_id,
        limit=limit,
        offset=offset,
        sort_order=sort_order,
    ).resolve()
