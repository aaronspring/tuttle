"""Time-tracking data aggregation and serialization.

Converts pandas DataFrames (the in-memory time-tracking store) into
JSON-safe dicts suitable for the frontend calendar view, event lists,
and summary panels.
"""

import calendar as cal_mod
import datetime
from typing import Optional

from pandas import DataFrame


def df_to_records(df: DataFrame) -> list:
    """Convert a time-tracking DataFrame to a list of JSON-safe dicts."""
    if df is None or df.empty:
        return []
    records = []
    for idx, row in df.iterrows():
        begin = idx
        if hasattr(begin, "isoformat"):
            begin = begin.isoformat()
        end = row.get("end")
        if hasattr(end, "isoformat"):
            end = end.isoformat()
        dur = row.get("duration")
        dur_hours = dur.total_seconds() / 3600 if hasattr(dur, "total_seconds") else 0
        records.append(
            {
                "begin": str(begin),
                "end": str(end) if end is not None else None,
                "duration_hours": round(dur_hours, 2),
                "title": str(row.get("title", "")),
                "tag": str(row.get("tag", "")),
                "description": str(row.get("description", "") or ""),
                "all_day": bool(row.get("all_day", False)),
                "date": str(begin)[:10],
            }
        )
    return records


def build_calendar_data(
    df: DataFrame,
    year: int,
    month: int,
    project_tag: Optional[str] = None,
    tag_to_title: Optional[dict] = None,
) -> dict:
    """Build a month-view calendar payload from a time-tracking DataFrame.

    Returns a dict with ``events``, ``projects`` (unique tags with hours),
    ``days`` (per-day aggregation), and ``summary`` (totals).
    """
    tag_to_title = tag_to_title or {}
    start = datetime.date(year, month, 1)
    _, last_day = cal_mod.monthrange(year, month)
    end = datetime.date(year, month, last_day)

    mask = (df.index.date >= start) & (df.index.date <= end)
    month_df = df[mask]
    if project_tag:
        month_df = month_df[month_df["tag"] == project_tag]

    events = df_to_records(month_df)

    by_tag = (
        month_df.groupby("tag")["duration"]
        .sum()
        .apply(lambda td: round(td.total_seconds() / 3600, 1))
        .to_dict()
    )
    count_by_tag = month_df.groupby("tag").size().to_dict()
    projects = [
        {
            "tag": t,
            "title": tag_to_title.get(t, t),
            "hours": h,
            "event_count": int(count_by_tag.get(t, 0)),
        }
        for t, h in sorted(by_tag.items(), key=lambda x: -x[1])
    ]

    days: dict = {}
    for idx, row in month_df.iterrows():
        d = str(idx.date()) if hasattr(idx, "date") else str(idx)[:10]
        if d not in days:
            days[d] = {
                "date": d,
                "hours": 0.0,
                "all_day_count": 0,
                "tags": [],
                "count": 0,
            }
        is_all_day = bool(row.get("all_day", False))
        if is_all_day:
            days[d]["all_day_count"] += 1
        else:
            dur = row.get("duration")
            h = dur.total_seconds() / 3600 if hasattr(dur, "total_seconds") else 0
            days[d]["hours"] = round(days[d]["hours"] + h, 2)
        days[d]["count"] += 1
        tag = str(row.get("tag", ""))
        if tag and tag not in days[d]["tags"]:
            days[d]["tags"].append(tag)

    total_hours = (
        round(month_df["duration"].sum().total_seconds() / 3600, 1)
        if len(month_df)
        else 0
    )

    return {
        "year": year,
        "month": month,
        "first_weekday": start.weekday(),
        "days_in_month": last_day,
        "events": events,
        "projects": projects,
        "days": days,
        "summary": {
            "total_events": len(month_df),
            "total_hours": total_hours,
        },
    }


def build_summary(
    df: DataFrame, tag_to_title: dict, project_tag: Optional[str] = None
) -> dict:
    """Build a time-tracking summary: totals and per-project breakdown.

    *tag_to_title* maps project tags to human-readable titles.
    When *project_tag* is provided, totals and project list are filtered to
    that tag only.
    """
    if df is None or df.empty:
        return {"total_events": 0, "total_hours": 0, "projects": []}

    if project_tag:
        df = df[df["tag"] == project_tag]
        if df.empty:
            return {"total_events": 0, "total_hours": 0, "projects": []}

    total_hours = df["duration"].sum().total_seconds() / 3600
    by_tag = (
        df.groupby("tag")["duration"]
        .sum()
        .apply(lambda td: round(td.total_seconds() / 3600, 1))
        .to_dict()
    )
    project_summaries = []
    for tag, hours in sorted(by_tag.items(), key=lambda x: -x[1]):
        project_summaries.append(
            {
                "tag": tag,
                "title": tag_to_title.get(tag, tag),
                "hours": hours,
                "event_count": int((df["tag"] == tag).sum()),
            }
        )
    return {
        "total_events": len(df),
        "total_hours": round(total_hours, 1),
        "projects": project_summaries,
    }


def merge_dataframes(existing: Optional[DataFrame], new_df: DataFrame) -> DataFrame:
    """Merge *new_df* into *existing*, deduplicating by index."""
    if existing is not None and not existing.empty:
        import pandas

        combined = pandas.concat([existing, new_df])
        combined = combined[~combined.index.duplicated(keep="last")]
        return combined
    return new_df
