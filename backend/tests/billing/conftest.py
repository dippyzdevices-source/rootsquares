"""Billing tests never touch the network: Stripe's HTTP library (requests) and httpx are blocked unless a test replaces them with a fake."""

import httpx
import pytest
import requests


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def blocked(*_a, **_k):
        raise AssertionError("a billing test tried to use the network; mock the Stripe service or the e-mail client")

    monkeypatch.setattr(requests.Session, "request", blocked)
    monkeypatch.setattr(httpx, "post", blocked)
    monkeypatch.setattr(httpx, "get", blocked)
