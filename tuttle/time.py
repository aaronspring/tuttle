import enum
import datetime
from typing import Optional


class Cycle(enum.Enum):
    hourly = "hourly"
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    quarterly = "quarterly"
    yearly = "yearly"

    def __str__(self):
        return str(self.value)


class TimeUnit(enum.Enum):
    # minute = "minute"
    hour = "hour"
    day = "day"

    def to_timedelta(self):
        if self == TimeUnit.hour:
            return datetime.timedelta(hours=1)
        elif self == TimeUnit.day:
            return datetime.timedelta(days=1)

    @property
    def abbrev(self) -> str:
        """Short display label, e.g. 'h' or 'd'."""
        _abbrevs = {TimeUnit.hour: "h", TimeUnit.day: "d"}
        return _abbrevs.get(self, self.value)

    def __str__(self):
        return str(self.value)
