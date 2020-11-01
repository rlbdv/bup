
from time import tzset
import pytest, sys

sys.path[:0] = ['lib']

from bup import helpers
from bup.compat import environ

@pytest.fixture(autouse=True)
def ephemeral_env_changes():
    orig_env = environ.copy()
    yield None
    for k, orig_v in orig_env.items():
        v = environ.get(k)
        if v is not orig_v:
            environ[k] = orig_v
            if k == b'TZ':
                tzset()
    for k in environ:
        if k not in orig_env:
            del environ[k]
            if k == b'TZ':
                tzset()
