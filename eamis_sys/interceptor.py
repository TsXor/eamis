from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse
import requests, time
from requests.auth import AuthBase as RequestsAuthBase


class ConcatenateAuth(RequestsAuthBase):
    children: list[RequestsAuthBase]

    def __init__(self, *args: RequestsAuthBase):
        self.children = [*args]

    def __call__(self, req: requests.PreparedRequest):
        for child in self.children:
            req = child(req)
        return req


class PathRateLimit(RequestsAuthBase):
    @dataclass
    class Rule:
        associated: dict[str, int | float]

    _domain: str
    _rules: dict[str, Rule]
    _last_time: dict[str, float]

    @property
    def domain(self): return self._domain

    def __init__(self, domain: str):
        self._domain = domain
        self._rules = {}
        self._last_time = {}

    @property
    def rules(self): return self._rules

    def __call__(self, req: requests.PreparedRequest):
        assert req.url is not None
        parsed_url = urlparse(req.url)
        if parsed_url.hostname == self._domain:
            rule = self.rules.get(parsed_url.path)
            if rule is not None:
                limit = max(self._last_time.get(path, 0.0) + interval
                            for path, interval in rule.associated.items())
                t = time.time()
                if t < limit: time.sleep(limit - t)
                def update_time(resp: requests.Response, **kwargs):
                    self._last_time[parsed_url.path] = time.time()
                req.register_hook("response", update_time)
        return req
