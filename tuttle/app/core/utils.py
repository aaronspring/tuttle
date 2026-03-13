import warnings
import base64

warnings.warn(
    "wastebasket module, content will be moved to other modules",
    DeprecationWarning,
    stacklevel=2,
)

from typing import List, Tuple

import base64
from enum import Enum

from flet import (
    BoxFit,
    ControlState,
    CrossAxisAlignment,
    Icons,
    KeyboardType,
    MainAxisAlignment,
    NavigationRailLabelType,
    ScrollMode,
    TextAlign,
)

import pycountry
from babel.numbers import format_currency as _babel_format_currency

from ...dev import deprecated


class AlertDialogControls(Enum):
    """Controls for the page's pop up dialog"""

    ADD_AND_OPEN = 1
    CLOSE = 2


# Layout Alignments — use the proper Flet enums.
# The *_ALIGNMENT names are kept for backward compat with existing call-sites
# that pass them to Column.alignment / Row.alignment (MainAxisAlignment)
# or Column.horizontal_alignment / Row.vertical_alignment (CrossAxisAlignment).
STRETCH_ALIGNMENT = CrossAxisAlignment.STRETCH
SPACE_BETWEEN_ALIGNMENT = MainAxisAlignment.SPACE_BETWEEN
START_ALIGNMENT = MainAxisAlignment.START
END_ALIGNMENT = MainAxisAlignment.END
CENTER_ALIGNMENT = MainAxisAlignment.CENTER

# Cross-axis specific aliases (use when assigning horizontal/vertical_alignment)
CROSS_STRETCH = CrossAxisAlignment.STRETCH
CROSS_START = CrossAxisAlignment.START
CROSS_CENTER = CrossAxisAlignment.CENTER
CROSS_END = CrossAxisAlignment.END

# Fit
CONTAIN = BoxFit.COVER

# Keyboard types
KEYBOARD_NAME = KeyboardType.NAME
KEYBOARD_PHONE = KeyboardType.PHONE
KEYBOARD_EMAIL = KeyboardType.EMAIL
KEYBOARD_TEXT = KeyboardType.TEXT
KEYBOARD_MULTILINE = KeyboardType.MULTILINE
KEYBOARD_NUMBER = KeyboardType.NUMBER
KEYBOARD_DATETIME = KeyboardType.DATETIME
KEYBOARD_URL = KeyboardType.URL
KEYBOARD_PASSWORD = KeyboardType.VISIBLE_PASSWORD
KEYBOARD_ADDRESS = KeyboardType.STREET_ADDRESS
KEYBOARD_NONE = KeyboardType.NONE

# Scrolling
AUTO_SCROLL = ScrollMode.AUTO
ADAPTIVE_SCROLL = ScrollMode.ADAPTIVE
HIDDEN_SCROLL = ScrollMode.HIDDEN
ALWAYS_SCROLL = ScrollMode.ALWAYS

# Text Alignment
TXT_ALIGN_RIGHT = TextAlign.RIGHT
TXT_ALIGN_CENTER = TextAlign.CENTER
TXT_ALIGN_JUSTIFY = TextAlign.JUSTIFY
TXT_ALIGN_START = TextAlign.START
TXT_ALIGN_END = TextAlign.END
TXT_ALIGN_LEFT = TextAlign.LEFT

# Navigation rail label style
ALWAYS_SHOW = NavigationRailLabelType.ALL
NEVER_SHOW = NavigationRailLabelType.NONE
ONLY_SELECTED = NavigationRailLabelType.SELECTED
# compact rail type (label is none)
COMPACT_RAIL_WIDTH = 56
# rail group_alignment
CENTER_RAIL = 0.0


# Control state
HOVERED = ControlState.HOVERED
FOCUSED = ControlState.FOCUSED
SELECTED = ControlState.SELECTED
PRESSED = ControlState.PRESSED
OTHER_CONTROL_STATES = ControlState.DEFAULT


@deprecated
def is_empty_str(txt: str) -> bool:
    # TODO: equivalent to txt.strip() == "", so remove function
    return len(txt.strip()) == 0


def truncate_str(txt: str, max_chars: int = 25) -> str:
    if not txt:
        return ""
    if len(txt) <= max_chars:
        return txt
    else:
        return f"{txt[0:max_chars]}..."


def image_to_base64(image_path):
    """Converts an image to a base64-encoded string."""
    with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
    return encoded_string


class TuttleComponentIcons(Enum):
    """ "Defines the icons used for different components throughout the app"""

    dashboard_icon = Icons.SPEED
    dashboard_selected_icon = Icons.SPEED_ROUNDED
    project_icon = Icons.WORK_OUTLINE
    project_selected_icon = Icons.WORK_ROUNDED
    contact_icon = Icons.CONTACT_MAIL_OUTLINED
    contact_selected_icon = Icons.CONTACT_MAIL_ROUNDED
    client_icon = Icons.CONTACTS_OUTLINED
    client_selected_icon = Icons.CONTACTS_ROUNDED
    contract_icon = Icons.HANDSHAKE_OUTLINED
    contract_selected_icon = Icons.HANDSHAKE_ROUNDED
    timetracking_icon = Icons.TIMER_OUTLINED
    timetracking_selected_icon = Icons.TIMER_ROUNDED
    invoicing_icon = Icons.RECEIPT_OUTLINED
    invoicing_selected_icon = Icons.RECEIPT_ROUNDED
    tax_icon = Icons.CALCULATE_OUTLINED
    tax_selected_icon = Icons.CALCULATE_ROUNDED
    datatable_icon = Icons.TABLE_CHART
    datatable_selected_icon = Icons.TABLE_CHART_ROUNDED
    profile_icon = Icons.PERSON_OUTLINE
    profile_selected_icon = Icons.PERSON_ROUNDED
    payment_icon = Icons.PAYMENT
    payment_selected_icon = Icons.PAYMENT_ROUNDED
    profile_photo_icon = Icons.PHOTO_OUTLINED
    profile_photo_selected_icon = Icons.PHOTO_ROUNDED

    def __str__(self) -> str:
        return str(self.value)


def get_currencies() -> List[Tuple[str, str, str]]:
    """Returns a list of available currencies sorted alphabetically"""
    currencies = []
    currency_list = list(pycountry.currencies)
    for currency in currency_list:
        abbreviation = currency.alpha_3
        symbol = currency.symbol if hasattr(currency, "symbol") else None
        currencies.append((currency.name, abbreviation, symbol))
    # sort alphabetically by abbreviation
    currencies.sort(key=lambda tup: tup[1])
    return currencies


def fmt_currency(value, currency: str = "EUR", locale: str = "en_US") -> str:
    """Format a numeric value as a currency string using babel.

    Args:
        value: Decimal, float, or int to format. None returns "---".
        currency: ISO 4217 code (e.g. "EUR", "USD", "SEK").
        locale: Babel locale for number formatting.
    """
    if value is None:
        return "—"
    return _babel_format_currency(float(value), currency, locale=locale)


def toBase64(
    image_path,
) -> str:
    """Returns base64 encoded image from the path"""

    # Read the image file as bytes
    with open(image_path, "rb") as image_file:
        image_bytes = image_file.read()
    # Convert the bytes to a base64
    stringbase64_string = base64.b64encode(image_bytes).decode("utf-8")

    return stringbase64_string
