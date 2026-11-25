import json
import os
from pathlib import Path
import runpy
import struct
import sys
from threading import Lock

resources = Path(__file__).parent
sys.path[:0] = [str(resources), str(resources / 'sdk')]
os.set_inheritable(3, False)
channel = os.fdopen(3, 'r+b', buffering=0)
lock = Lock()


def read_exact(count):
    data = bytearray()
    while len(data) < count:
        chunk = channel.read(count - len(data))
        if not chunk:
            raise RuntimeError('IrnBru credential service disconnected')
        data.extend(chunk)
    return data


def request(op, value, expected):
    data = json.dumps(dict(op=op, profile='AzureCloud', value=value, expected=expected)).encode()
    with lock:
        channel.write(struct.pack('!I', len(data)) + data)
        size, = struct.unpack('!I', read_exact(4))
        if not 0 < size <= 262144:
            raise RuntimeError('Invalid IrnBru credential response')
        reply = json.loads(read_exact(size))
    if reply.get('ok') is not True:
        raise RuntimeError(reply.get('error', 'IrnBru credential request failed'))
    return reply['value']


os.environ.update(AZURE_CONFIG_DIR=str(Path.home() / '.azure-irnbru'),
                  AZURE_EXTENSION_DIR=str(resources / 'extensions'),
                  AZURE_EXTENSION_SYS_DIR=str(resources / 'extensions'),
                  AZURE_EXTENSION_USE_DYNAMIC_INSTALL='no', AZURE_AUTO_UPGRADE_ENABLE='no',
                  AZURE_CORE_USE_COMMAND_INDEX='no', AZURE_CORE_COLLECT_TELEMETRY='no', AZURE_LOGGING_ENABLE_LOG_FILE='no',
                  AZURE_CORE_ENABLE_BROKER_ON_MAC='false')

from azure.cli.core import cloud, _profile
from azure.cli.core.auth import identity
from store import SessionCache


def unsupported(*args, **kwargs):
    raise RuntimeError('The managed az login supports Azure public-cloud user accounts')


class EmptyPrincipalStore:
    def load(self):
        return []

    def save(self, value):
        if value:
            unsupported()


def cache(instance):
    if instance.authority.rstrip('/') != 'https://login.microsoftonline.com':
        unsupported()
    return SessionCache(request)


def clear_accounts(profile):
    saved = SessionCache(request)
    if saved.original is not None:
        request('delete', None, saved.original)
    profile._storage[_profile._SUBSCRIPTIONS] = []


logout_user = identity.Identity.logout_user


def logout_one(instance, username):
    app = instance._msal_app
    app.token_cache.transaction(logout_user, instance, username)


_profile.Profile.logout_all = clear_accounts
_profile.Profile.login_with_managed_identity = unsupported
identity.Identity.logout_user = logout_one
identity.Identity.logout_service_principal = lambda self, username: None
identity.Identity._load_msal_token_cache = cache
identity.Identity._load_msal_http_cache = lambda self: {}
identity.load_secret_store = lambda *args: EmptyPrincipalStore()
identity.Identity.login_with_service_principal = unsupported
identity.Identity.login_with_username_password = unsupported
cloud.AZURE_PUBLIC_CLOUD.profile = "latest"
cloud.get_active_cloud = lambda cli_ctx=None: cloud.AZURE_PUBLIC_CLOUD

if sys.argv[1:2] in (['extension'], ['upgrade'], ['interactive'], ['cloud']) or '--debug' in sys.argv:
    raise SystemExit('This runtime-management or diagnostic mode is unavailable in the signed az installation')
runpy.run_module('azure.cli', run_name='__main__', alter_sys=False)
