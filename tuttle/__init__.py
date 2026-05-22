"""Top-level package for tuttle."""

__authors__ = [
    "Christian Staudt",
    "Vladimir Peter",
]
__version__ = "3.1.1a1"

try:
    from . import app
except ImportError:
    pass

from . import (
    banking,
    calendar,
    cloud,
    invoicing,
    model,
    tax,
    timetracking,
    dataviz,
    time,
    rendering,
    os_functions,
    mail,
)
