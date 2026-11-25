"""Use pinned CPython and the packaged MSAL implementation with a memory-only broker."""
import json
from pathlib import Path
import sys

resources = Path(sys.argv[1]).resolve()
sys.path[:0] = [str(resources), str(resources / 'sdk')]
from store import SessionCache

stored = None
changes = []


def request(op, value, expected):
    global stored
    if op == 'use':
        return stored
    if expected != stored:
        raise ValueError('stale')
    stored = value
    changes.append(op)


first = SessionCache(request)
stale = SessionCache(request)
event = dict(client_id='fixture', scope=['fixture'], token_endpoint='https://login.microsoftonline.com/tenant/oauth2/v2.0/token',
             response=dict(access_token='synthetic-access', refresh_token='synthetic-refresh'))
first.add(event)
assert changes == ['save'] and 'synthetic-access' in stored and 'synthetic-refresh' in stored
try:
    stale.add(event)
except ValueError:
    assert json.loads(stale.serialize()) == {} and changes == ['save']
else:
    raise AssertionError('stale save succeeded')
restored = SessionCache(request)
assert json.loads(restored.serialize()) == json.loads(stored)
print('MSAL nested cache mutation, reload and stale rollback OK')
