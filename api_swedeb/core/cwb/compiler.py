from typing import Any, Literal


def _to_value_expr(value: str | list[str] | tuple[int, int]) -> str:
    """Create a rsh CQP expression out of a single value, a range (tuple), or list of values"""
    if isinstance(value, tuple):
        return _to_interval_expr(*value)
    if isinstance(value, list):
        return "|".join(map(str, value))
    return str(value)


def _to_interval_expr(low: int, high: int, *_) -> str:
    """Create a CQP integer interval filter expression

    Year values are strings in the CWB database, so we can't use integer range operators.
    Instead we need to use string patterns, whilst reducing the number of patterns to match
    by matching decade intervals as much as possible.

    Example:
        to_cqp_interval_expr(2020, 2020) => "2020"'
        to_cqp_interval_expr(2022, 2024) => "202[2-4]"'
        to_cqp_interval_expr(1992, 2013) => "199[2-9]|200[0-9]|201[0-3]"'
    )

    """
    low, high = int(low), int(high)
    if high < low:
        raise ValueError("High year must be greater than low year")

    values: list[str] = []
    low_decade, high_decade = low // 10 * 10, high // 10 * 10

    if low == high:
        return f"{low}"

    if low_decade == high_decade:
        return f"{low_decade//10}[{low%10}-{high%10}]"

    for decade in range(low_decade, high_decade + 10, 10):
        if decade == low_decade:
            values.append(f"{decade//10}[{low%10}-9]")
            continue
        if decade == high_decade:
            if decade == high:
                values.append(f"{decade}")
            else:
                values.append(f"{decade//10}[0-{high%10}]")
            continue
        values.append(f"{decade//10}[0-9]")

    return f'{"|".join(values)}'


def to_cqp_pattern(**opts) -> str:
    """Compile a CQP query from a list of tokens and a dictionary of criterias.

    Args:
        Keyword args with CQP pattern options:
            prefix (str | list, optional): _description_. Defaults to None.
            target (str, optional): _description_. Defaults to None.
            value (str | list[str], optional): _description_. Defaults to None.
            ignore_case (bool, optional): _description_. Defaults to True.

    Raises:
        ValueError: _description_

    Returns:
        str: _description_

    Examples:

        Match a literal:
            {"target": "apa"}
                => '"apa"%c'

        Match a word:
            {"target": "word", "value": "information", "ignore_case": False}
                => '[word="information"]'

        Match a word (ignore case):
            {"target": "word", "value": "information", "ignore_case": True}
                => '[word="information"%c]'

        Match a word (ignore case default):
            {"target": "word", "value": "information"}
                => '[word="information"%c]'

        Use a prefix:
            {"prefix": "a", "target": "word", "value": "information"}
                => 'a:[word="information"%c]'

        Match a word with multiple values:
            {"target": "word", "value": ["information", "propaganda"]}
                => '[word="information|propaganda"%c]'

        Match a word with multiple values and and PoS criterias:
            {
                "prefix": "a",
                "target": "word",
                "value": ["information", "propaganda"],
                "criterias": {"key": "a.pos", "values": ["NN", "PM"]},
            }
                => 'a:[word="information|propaganda"%c] :: (a.pos="NN|PM"%c)'

        Match a word with single pattern and multiple criterias:
             {
                "prefix": "a",
                "target": "word",
                "value": "propaganda",
                "criterias": [
                    {"key": "a.speech_who", "values": ["Q1807154", "Q4973765"]},
                    {"key": "a.speech_party_id", "values": ["7"]},
                    {"key": "a.pos", "values": ["NN", "PM"]},
                ],
            }
                => 'a:[word="propaganda"%c] :: (a.speech_who="Q1807154|Q4973765"%c)&(a.speech_party_id="7"%c)&(a.pos="NN|PM"%c)'


        Match a word with multiple patterns:
            [
                {"target": "word", "value": "information", "ignore_case": False},
                {"target": "och", "value": None, "ignore_case": False},
                {"target": "word", "value": "propaganda", "ignore_case": False},
            ]
                => '[word="information"] "och" [word="propaganda"]'

        Match a word with multiple patterns and criterias:
            [
                {
                    "prefix": "a",
                    "target": "word",
                    "value": "information",
                    "ignore_case": False,
                    "criterias": [
                        {"key": "a.speech_who", "values": ["Q1807154", "Q4973765"]},
                    ],
                },
                {"target": "och", "value": None, "ignore_case": False},
                {"target": "word", "value": "propaganda", "ignore_case": False},
            ]
            'a:[word="information"] "och" [word="propaganda"] :: (a.speech_who="Q1807154|Q4973765")'

    """  # noqa: E501

    if isinstance(opts, str):
        return f'"{opts}"' % opts

    prefix: str | list = opts.get("prefix")
    target: str = opts.get("target")
    value: str | list[str] = opts.get("value")
    ignore_case: bool = opts.get("ignore_case", True)

    if target is None:
        raise ValueError("Target must be provided")

    caseless: bool = "%c" if ignore_case else ""
    namespace: str = f"{prefix}:" if prefix else ""
    pattern: str = f'[{target}="{_to_value_expr(value)}"{caseless}]' if value is not None else f'"{target}"{caseless}'

    return f"{namespace}{pattern}"


def to_cqp_patterns(args: list[dict[str, Any]]) -> str:
    """Compile a CQP query from a list of tokens and a dictionary of criterias.

    Args:
        args (list[dict[str, Any]]): List of transform options.
            Each option is a dictionary with the following data:
                prefix (str | list, optional): CQP prefix. Defaults to None.
                target (str, optional): CQP target. Defaults to None.
                value (str | list[str], optional): CQP value. Defaults to None.
                ignore_case (bool, optional): Flag for caseless search. Defaults to True.
                not used: criterias (dict[str, list[Any]], optional): Filter. Defaults to None.

    Raises:
        ValueError: if any target is missing

    Returns:
        str: compiled CQP query with a CQP pattern for each item in args

    Examples:

        Match a word with multiple patterns:
            [
                {"target": "word", "value": "information", "ignore_case": False},
                {"target": "och", "value": None, "ignore_case": False},
                {"target": "word", "value": "propaganda", "ignore_case": False},
            ]
                => '[word="information"] "och" [word="propaganda"]'

        Match a word with multiple patterns and criterias:
            [
                {
                    "prefix": "a",
                    "target": "word",
                    "value": "information",
                    "ignore_case": False,
                    "criterias": [
                        {"key": "a.speech_who", "values": ["Q1807154", "Q4973765"]},
                    ],
                },
                {"target": "och", "value": None, "ignore_case": False},
                {"target": "word", "value": "propaganda", "ignore_case": False},
            ]
            'a:[word="information"] "och" [word="propaganda"] :: (a.speech_who="Q1807154|Q4973765")'

    """  # noqa: E501
    if isinstance(args, dict):
        args = [args]
    return " ".join(to_cqp_pattern(**arg) for arg in args)


def to_cqp_criteria_expr(criterias: list[dict[str, Any]]) -> str:

    if criterias is None:
        criterias = []

    if isinstance(criterias, dict):
        criterias = [criterias]

    def fx_case(x) -> Literal["%c"] | Literal[""]:
        return "%c" if x.get("ignore_case", False) else ""

    expr: str = "&".join(
        [
            f"({expr})"
            for expr in [
                f'{criteria.get("key")}="{_to_value_expr(criteria.get("values"))}"{fx_case(criteria)}'
                for criteria in criterias
            ]
            if expr
        ]
    )
    return expr


def get_criteria_opts(args: list[dict[str, Any]]) -> list[str]:
    """Get a list of criteria expressions from a list of pattern options."""
    items: list[Any | None] = [arg.get("criterias") for arg in args if arg.get("criterias")]
    if len(items) > 0 and isinstance(items[0], list):
        items = [item for row in items for item in row]
    return items


def to_cqp_exprs(args: list[dict[str, Any]], within: str = None) -> str:
    """Compile a CQP sequence query from a list of pattern options."""
    if not args:
        return ""

    if isinstance(args, dict):
        args = [args]

    if isinstance(args, str):
        args = [{"target": args}]

    criteria_opts: list[Any] = get_criteria_opts(args)

    expr: str = to_cqp_patterns(args)

    if criteria_opts:
        criteria_expr: str = to_cqp_criteria_expr(criteria_opts)
        if criteria_expr:
            expr = f"{expr} :: {criteria_expr}"

    if within:
        expr = f"{expr} within {within}"

    return expr
