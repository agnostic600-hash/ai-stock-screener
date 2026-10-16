import pytest
from providers import DataError


@pytest.fixture(autouse=True)
def no_live_sec(monkeypatch):
    def unavailable(symbol):
        raise DataError('Test: externá sieť nie je dostupná.')
    monkeypatch.setattr('data.load_sec', unavailable)
