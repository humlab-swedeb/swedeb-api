"""Unit tests for tool_router misc endpoints (topics, year_range, protocol page_range)."""

import asyncio
from unittest.mock import MagicMock

from api_swedeb.api.v1.endpoints.tool_router import get_year_range


class TestToolRouterMiscEndpoints:

    def test_get_year_range_returns_loader_year_range(self):
        corpus_loader = MagicMock()
        corpus_loader.year_range = (1867, 2024)

        result = asyncio.run(get_year_range(corpus_loader=corpus_loader))

        assert result == (1867, 2024)
