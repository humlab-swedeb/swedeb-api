from api_swedeb.api.params import CommonQueryParams


def test_get_filter_opts():
    args: CommonQueryParams = CommonQueryParams(
        from_year=1970, to_year=1975, who=None, party_id=None, office_types=None, sub_office_types=None, gender_id=None
    )

    opts = args.get_filter_opts(True)
    assert opts.get('year') == {'low': 1970, 'high': 1975}

    opts = args.get_filter_opts(False)
    assert opts.get('year') is None


def test_resolve_opts():
    args: CommonQueryParams = CommonQueryParams(from_year=1970, to_year=1975).resolve()

    assert args.get_filter_opts(True) == {'year': {'low': 1970, 'high': 1975}}
