"""Smoke tests: the package imports and its bundled data ships with the wheel."""

from trapi import TRApi
from trapi.api import TrBlockingApi


def test_public_class_is_importable() -> None:
    assert TRApi.url == "https://api.traderepublic.com"
    assert issubclass(TrBlockingApi, TRApi)


def test_all_isins_loads_bundled_data() -> None:
    isins = TRApi.all_isins()
    assert isinstance(isins, list)
    assert len(isins) > 0
