"""Preferences backed by the app-level database.

Replaces the legacy ClientStorage-based implementation.  Both the
RPC-facing methods (``get`` / ``save``) and the internal API used by
other intents (``get_preference_by_key``, ``get_preferred_invoice_template``)
read from the same ``AppDatabase`` backend.
"""

from ..core.intent_result import IntentResult
from ...app_db import AppDatabase
from .model import (
    DEFAULT_INVOICE_NUMBER_SCHEME,
    DEFAULT_INVOICE_TEMPLATE,
    PreferencesStorageKeys,
)


class PreferencesIntent:
    def __init__(self, client_storage=None):
        self._app_db = AppDatabase()

    # -- RPC-facing ------------------------------------------------------------

    def get(self) -> IntentResult:
        return IntentResult(
            was_intent_successful=True,
            data={
                "invoice_template": self._app_db.get_setting(
                    PreferencesStorageKeys.invoice_template_key.value,
                )
                or DEFAULT_INVOICE_TEMPLATE,
                "language": self._app_db.get_setting(
                    PreferencesStorageKeys.language_key.value,
                )
                or "en",
                "invoice_number_scheme": self._app_db.get_setting(
                    PreferencesStorageKeys.invoice_number_scheme_key.value,
                )
                or DEFAULT_INVOICE_NUMBER_SCHEME,
            },
        )

    def save(
        self, invoice_template=None, language=None, invoice_number_scheme=None
    ) -> IntentResult:
        if invoice_template is not None:
            self._app_db.set_setting(
                PreferencesStorageKeys.invoice_template_key.value,
                invoice_template,
            )
        if language is not None:
            self._app_db.set_setting(
                PreferencesStorageKeys.language_key.value,
                language,
            )
        if invoice_number_scheme is not None:
            self._app_db.set_setting(
                PreferencesStorageKeys.invoice_number_scheme_key.value,
                invoice_number_scheme,
            )
        return IntentResult(was_intent_successful=True, data=None)

    # -- Internal API (used by other intents) ----------------------------------

    def get_preference_by_key(self, key) -> IntentResult:
        k = key.value if hasattr(key, "value") else key
        return IntentResult(
            was_intent_successful=True,
            data=self._app_db.get_setting(k),
        )

    def get_preferred_invoice_template(self) -> IntentResult:
        tmpl = (
            self._app_db.get_setting(
                PreferencesStorageKeys.invoice_template_key.value,
            )
            or DEFAULT_INVOICE_TEMPLATE
        )
        return IntentResult(was_intent_successful=True, data=tmpl)
