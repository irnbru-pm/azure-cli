import os
from pathlib import Path
import runpy
import sys

resources = Path(__file__).parent
sys.path[:0] = [str(resources), str(resources / 'sdk')]
os.environ.update(AZURE_CONFIG_DIR=str(Path.home() / '.azure-irnbru'),
                  AZURE_EXTENSION_DIR=str(resources / 'extensions'),
                  AZURE_EXTENSION_SYS_DIR=str(resources / 'extensions'),
                  AZURE_EXTENSION_USE_DYNAMIC_INSTALL='no', AZURE_AUTO_UPGRADE_ENABLE='no',
                  AZURE_CORE_USE_COMMAND_INDEX='no', AZURE_CORE_COLLECT_TELEMETRY='no', AZURE_LOGGING_ENABLE_LOG_FILE='no',
                  AZURE_CORE_ENABLE_BROKER_ON_MAC='false')

from azure.cli.core import cloud, _profile
from azure.cli.core.auth.irnbru_broker import request
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
identity.load_secret_store = lambda *args: EmptyPrincipalStore()
identity.Identity.login_with_service_principal = unsupported
identity.Identity.login_with_username_password = unsupported
cloud.AZURE_PUBLIC_CLOUD.profile = "latest"
cloud.get_active_cloud = lambda cli_ctx=None: cloud.AZURE_PUBLIC_CLOUD

if sys.argv[1:2] in (['extension'], ['upgrade'], ['interactive'], ['cloud']) or '--debug' in sys.argv:
    raise SystemExit('This runtime-management or diagnostic mode is unavailable in the signed az installation')
runpy.run_module('azure.cli', run_name='__main__', alter_sys=False)
