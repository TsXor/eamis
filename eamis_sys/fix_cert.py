import sys, importlib
from urllib3.exceptions import InsecureRequestWarning
from .utils import supress_warning

try:
    import pip_system_certs.wrapt_requests
    REQUESTS_CERTS_PATCHED = True
except ImportError: 
    REQUESTS_CERTS_PATCHED = False

if REQUESTS_CERTS_PATCHED:
    if 'requests' in sys.modules:
        importlib.reload(sys.modules['requests'])
else:
    import requests
    falsy = property(lambda self: False, lambda self, val: None)
    requests.Session.verify = falsy # type: ignore
    suppress_insecure = supress_warning(InsecureRequestWarning)
    requests.Session.request = suppress_insecure(requests.Session.request)

__all__ = ['REQUESTS_CERTS_PATCHED']
