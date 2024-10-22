from api_swedeb.api.utils.common_params import CommonQueryParams


def test_get_filter_opts():

    args: CommonQueryParams = CommonQueryParams(
        from_year=1970, to_year=1975, who=None, party_id=None, office_types=None, sub_office_types=None, gender_id=None
    )

    opts: dict[str, list[int]] = args.get_filter_opts(True)
    assert opts.get('year') == (1970, 1975)

    opts: dict[str, list[int]] = args.get_filter_opts(False)
    assert opts.get('year') is None


def test_resolve_opts():

    args: CommonQueryParams = CommonQueryParams(from_year=1970, to_year=1975).resolve()

    assert args.get_filter_opts(True) == {'year': (1970, 1975)}
