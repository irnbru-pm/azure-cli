"""MSAL's in-memory cache with approved, compare-and-swap persistence."""
import json
from threading import RLock

from msal import SerializableTokenCache


class SessionCache(SerializableTokenCache):
    def __init__(self, request):
        super().__init__()
        self.guard = RLock()
        self.request = request
        self.original = request('use', None, None)
        self.deserialize(self.original)
        self.editing = False

    def transaction(self, operation, *args, **kwargs):
        with self.guard:
            if self.editing:
                return operation(*args, **kwargs)
            self.editing = True
            try:
                result = operation(*args, **kwargs)
                updated = self.serialize()
                # MSAL retains empty buckets after logout.
                if not any(values for kind, values in json.loads(updated).items() if kind != self.CredentialType.APP_METADATA):
                    updated = None
                if self.original != updated:
                    self.request('delete' if updated is None else 'save', updated, self.original)
                    self.original = updated
                return result
            except BaseException:
                self.deserialize(self.original)
                raise
            finally:
                self.editing = False

    def add(self, event, **kwargs):
        return self.transaction(super().add, event, **kwargs)

    def modify(self, credential_type, old_entry, new_key_value_pairs=None):
        return self.transaction(super().modify, credential_type, old_entry, new_key_value_pairs)

    def remove_account(self, account_item):
        return self.transaction(super().remove_account, account_item)
