from dataclasses import dataclass
from enum import Enum


INVOICE_TEMPLATES = {
    "invoice-modern": "Modern",
    "invoice-minimal": "Minimal",
}

SUPPORTED_INVOICE_LANGUAGES = {
    "en": "English",
    "de": "Deutsch",
    "es": "Español",
}

DEFAULT_INVOICE_TEMPLATE = "invoice-modern"

INVOICE_NUMBER_SCHEMES = {
    "daily": "YYYY-MM-DD-NN (daily sequence)",
    "yearly": "YYYY-NN (yearly sequence)",
    "plain": "NN (plain auto-increment)",
}

DEFAULT_INVOICE_NUMBER_SCHEME = "daily"


@dataclass
class Preferences:
    theme_mode: str = ""
    cloud_acc_id: str = ""
    cloud_acc_provider: str = ""
    language: str = ""
    invoice_template: str = DEFAULT_INVOICE_TEMPLATE
    invoice_number_scheme: str = DEFAULT_INVOICE_NUMBER_SCHEME


class PreferencesStorageKeys(Enum):
    """defines the keys used in storing preferences as key-value pairs"""

    theme_mode_key = "preferred_theme_mode"
    cloud_acc_id_key = "preferred_cloud_acc_id"
    cloud_provider_key = "preferred_cloud_acc_provider"
    language_key = "preferred_language"
    invoice_template_key = "preferred_invoice_template"
    invoice_number_scheme_key = "preferred_invoice_number_scheme"

    def __str__(self) -> str:
        return str(self.value)
