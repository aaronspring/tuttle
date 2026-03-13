"""Defines font related constants used in app.

Sizes tuned for macOS native feel — slightly larger body text
for readability, semi-bold headings for clear hierarchy.
"""

from flet import FontWeight

DEFAULT_FONT = "body"
HEADLINE_FONT = "headline"
MONOSPACE_FONT = "monospace"

APP_FONTS = {
    DEFAULT_FONT: "/fonts/SF-Pro-Display-Regular.otf",
    HEADLINE_FONT: "/fonts/SF-Pro-Display-Regular.otf",
    # MONOSPACE_FONT: "/fonts/SFMono-Regular.otf",  # add when available
}


# ── Font sizes ───────────────────────────────────────────────
HEADLINE_0_SIZE = 30  # hero / splash titles
HEADLING_1_SIZE = 26  # page titles
HEADLINE_2_SIZE = 20  # section titles
HEADLINE_3_SIZE = 17  # sub-section titles
HEADLINE_4_SIZE = 14  # card titles, toolbar headings
BODY_1_SIZE = 13  # primary body text
BODY_2_SIZE = 12  # secondary body text
SUBTITLE_1_SIZE = 14  # emphasized labels
SUBTITLE_2_SIZE = 12  # secondary labels
BUTTON_SIZE = 12  # button text
OVERLINE_SIZE = 11  # overline / section headers
CAPTION_SIZE = 11  # captions, helper text
STATUS_BAR_SIZE = 11  # status bar text

# ── Font weights ─────────────────────────────────────────────
BOLD_FONT = FontWeight.W_600  # semi-bold for crisper hierarchy
BOLDER_FONT = FontWeight.BOLD
