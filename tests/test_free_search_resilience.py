import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mecos import free_search as fs


def test_ddg_403_enters_cooldown(monkeypatch):
    monkeypatch.setattr(fs, "_ddg_disabled_until", 0.0)
    monkeypatch.setattr(fs, "DDG_COOLDOWN_SECONDS", 120)

    calls = {"count": 0}

    def fake_request(*args, **kwargs):
        calls["count"] += 1
        response = requests.Response()
        response.status_code = 403
        response.url = "https://lite.duckduckgo.com/lite/"
        raise requests.exceptions.HTTPError(response=response)

    monkeypatch.setattr(fs.requests, "request", fake_request)

    assert fs.search_duckduckgo("electromagnetism", max_results=3) == []
    assert fs.search_duckduckgo("electromagnetism", max_results=3) == []
    assert calls["count"] == 1


def test_ddg_fallback_to_html_endpoint(monkeypatch):
    monkeypatch.setattr(fs, "_ddg_disabled_until", 0.0)

    calls = {"count": 0}

    class FakeResponse:
        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self):
            return None

    html = """
    <html><body>
      <div class="result">
        <a class="result__a" href="https://example.com/article">Electromagnetism basics</a>
        <a class="result__snippet">Electric and magnetic fields are coupled.</a>
      </div>
    </body></html>
    """

    def fake_request(method, url, **kwargs):
        calls["count"] += 1
        if "lite.duckduckgo.com" in url:
            raise requests.exceptions.ConnectTimeout("timeout")
        return FakeResponse(html)

    monkeypatch.setattr(fs.requests, "request", fake_request)

    out = fs.search_duckduckgo("electromagnetism", max_results=2)
    assert len(out) == 1
    assert out[0].title == "Electromagnetism basics"
    assert out[0].url == "https://example.com/article"
    assert calls["count"] >= 2
