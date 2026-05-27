import base64
import datetime
from pathlib import Path
from typing import Optional, Type, Union

from loguru import logger
from pandas import DataFrame

from ..core.abstractions import Intent
from ..core.intent_result import IntentResult
from ..preferences.intent import PreferencesIntent
from ..preferences.model import PreferencesStorageKeys
from ..projects.intent import ProjectsIntent
from ...calendar import Calendar, ICSCalendar
from ...cloud import CloudConnector, CloudProvider
from ...eventkit_bridge import (
    fetch_events,
    is_available,
    list_calendars_with_status,
    open_calendar_privacy_settings,
)

from .aggregation import (
    build_calendar_data,
    build_summary,
    df_to_records,
    merge_dataframes,
)
from .data_source import (
    TimeTrackingCloudCalendarSource,
    TimeTrackingDataFrameSource,
    TimeTrackingFileCalendarSource,
    TimeTrackingSpreadsheetSource,
)


class TimeTrackingIntent(Intent):
    """Time-tracking data access, import, aggregation."""

    def __init__(self, client_storage=None):
        self._cloud_calendar_source = TimeTrackingCloudCalendarSource()
        self._file_calendar_source = TimeTrackingFileCalendarSource()
        self._spreadsheet_source = TimeTrackingSpreadsheetSource()
        self._timetracking_data_frame_source = TimeTrackingDataFrameSource()
        self._preferences_intent = PreferencesIntent()

    # -- RPC-facing methods ----------------------------------------------------

    def get_events(self, project_tag=None) -> IntentResult:
        df = self._timetracking_data_frame_source.get_data_frame()
        if df is None or df.empty:
            return IntentResult(was_intent_successful=True, data=[])
        if project_tag:
            df = df[df["tag"] == project_tag]
        return IntentResult(was_intent_successful=True, data=df_to_records(df))

    def get_calendar_data(
        self, year=None, month=None, project_tag=None
    ) -> IntentResult:
        df = self._timetracking_data_frame_source.get_data_frame()
        if df is None or df.empty:
            return IntentResult(
                was_intent_successful=True,
                data={
                    "events": [],
                    "projects": [],
                    "summary": {},
                },
            )
        if year is None:
            year = datetime.date.today().year
        if month is None:
            month = datetime.date.today().month
        proj_result = ProjectsIntent().get_all()
        tag_to_title = {}
        if proj_result.was_intent_successful and proj_result.data:
            tag_to_title = {p.tag: p.title for p in proj_result.data}
        return IntentResult(
            was_intent_successful=True,
            data=build_calendar_data(df, year, month, project_tag, tag_to_title),
        )

    def import_ics(self, content: str, name: str = "imported.ics") -> IntentResult:
        raw = base64.b64decode(content)
        cal = ICSCalendar(name=name, content=raw)
        new_df = cal.to_data()
        ds = self._timetracking_data_frame_source
        ds.store_data_frame(merge_dataframes(ds.get_data_frame(), new_df))
        ds.save_to_cache()
        ds.save_source_config("ics", calendar_name=name)
        records = df_to_records(new_df)
        return IntentResult(
            was_intent_successful=True,
            data={"imported_count": len(records), "events": records},
        )

    def clear(self) -> IntentResult:
        self._timetracking_data_frame_source.store_data_frame(None)
        self._timetracking_data_frame_source.clear_cache()
        self._timetracking_data_frame_source.clear_source_config()
        return IntentResult(was_intent_successful=True, data=None)

    def list_system_calendars(self, open_settings=False) -> IntentResult:
        if not is_available():
            return IntentResult(
                was_intent_successful=True,
                data={
                    "calendars": [],
                    "auth_status": "not_available",
                },
            )
        if open_settings:
            open_calendar_privacy_settings()
            return IntentResult(
                was_intent_successful=True,
                data={
                    "calendars": [],
                    "auth_status": "pending",
                },
            )
        try:
            return IntentResult(
                was_intent_successful=True,
                data=list_calendars_with_status(),
            )
        except Exception as ex:
            logger.exception(ex)
            return IntentResult(
                was_intent_successful=False,
                data={"calendars": [], "auth_status": "unknown"},
                error_msg=str(ex),
            )

    def import_system_calendar(
        self,
        calendar_id,
        from_date=None,
        to_date=None,
    ) -> IntentResult:
        if not is_available():
            return IntentResult(
                was_intent_successful=False,
                error_msg="System calendar access is only available on macOS",
            )
        if from_date is None:
            from_date = datetime.date.today() - datetime.timedelta(days=365)
        elif isinstance(from_date, str):
            from_date = datetime.date.fromisoformat(from_date)
        if to_date is None:
            to_date = datetime.date.today()
        elif isinstance(to_date, str):
            to_date = datetime.date.fromisoformat(to_date)
        try:
            new_df = fetch_events(calendar_id, from_date, to_date)
            if new_df.empty:
                return IntentResult(
                    was_intent_successful=True,
                    data={
                        "imported_count": 0,
                        "events": [],
                    },
                )
            ds = self._timetracking_data_frame_source
            ds.store_data_frame(merge_dataframes(ds.get_data_frame(), new_df))
            ds.save_to_cache()
            ds.save_source_config("system", calendar_id=str(calendar_id))
            records = df_to_records(new_df)
            return IntentResult(
                was_intent_successful=True,
                data={
                    "imported_count": len(records),
                    "events": records,
                },
            )
        except Exception as ex:
            logger.exception(ex)
            return IntentResult(
                was_intent_successful=False,
                error_msg=str(ex),
            )

    def get_source_config(self) -> IntentResult:
        config = self._timetracking_data_frame_source.get_source_config()
        return IntentResult(was_intent_successful=True, data=config)

    def restore(self) -> IntentResult:
        """Restore cached time-tracking data from disk (called on startup)."""
        ds = self._timetracking_data_frame_source
        if ds.get_data_frame() is not None:
            return IntentResult(
                was_intent_successful=True,
                data={"restored": False, "reason": "already_loaded"},
            )
        config = ds.get_source_config()
        source_type = config.get("source_type", "")
        if not source_type:
            return IntentResult(
                was_intent_successful=True,
                data={"restored": False, "reason": "no_config"},
            )
        if source_type == "system" and is_available():
            calendar_id = config.get("calendar_id", "")
            if calendar_id:
                try:
                    from_date = datetime.date.today() - datetime.timedelta(days=365)
                    to_date = datetime.date.today()
                    new_df = fetch_events(calendar_id, from_date, to_date)
                    if not new_df.empty:
                        ds.store_data_frame(new_df)
                        ds.save_to_cache()
                        logger.info(
                            f"Restored {len(new_df)} events from system calendar {calendar_id}"
                        )
                        return IntentResult(
                            was_intent_successful=True,
                            data={
                                "restored": True,
                                "source": "system",
                                "count": len(new_df),
                            },
                        )
                except Exception as ex:
                    logger.warning(f"Failed to restore from system calendar: {ex}")
        restored = ds.load_from_cache()
        return IntentResult(
            was_intent_successful=True,
            data={"restored": restored, "source": source_type if restored else "cache"},
        )

    def get_summary(self, project_tag: Optional[str] = None) -> IntentResult:
        df = self._timetracking_data_frame_source.get_data_frame()
        if df is None or df.empty:
            return IntentResult(
                was_intent_successful=True,
                data={
                    "total_events": 0,
                    "total_hours": 0,
                    "projects": [],
                },
            )
        proj_result = ProjectsIntent().get_all()
        tag_to_title = {}
        if proj_result.was_intent_successful and proj_result.data:
            tag_to_title = {p.tag: p.title for p in proj_result.data}
        return IntentResult(
            was_intent_successful=True,
            data=build_summary(df, tag_to_title, project_tag),
        )

    # -- Legacy internal methods -----------------------------------------------

    def get_preferred_cloud_account(self) -> IntentResult[Optional[list]]:
        """
        Returns:
            IntentResult
                data as [provider_name, account_name] list if successful else None"""
        provider_result = self._preferences_intent.get_preference_by_key(
            PreferencesStorageKeys.cloud_provider_key
        )
        acc_result = self._preferences_intent.get_preference_by_key(
            PreferencesStorageKeys.cloud_acc_id_key
        )
        if (
            not provider_result.was_intent_successful
            or not acc_result.was_intent_successful
        ):
            return IntentResult(
                was_intent_successful=False,
                error_msg="Failed to load account preferences",
            )
        return IntentResult(
            was_intent_successful=True, data=[provider_result.data, acc_result.data]
        )

    def process_timetracking_file(self, file_path: Path) -> IntentResult[DataFrame]:
        """processes a time tracking spreadsheet or ics file in the uploads folder

        Returns
        -------
            IntentResult
                data : time tracking data as a pandas DataFrame if intent successful else None
                error_msg  : text to display to the user if an error occurs else is empty
        """
        # check the file extension. file_path is a Path object
        is_calendar = file_path.suffix == ".ics"
        if is_calendar:
            timetracking_data: DataFrame = self._file_calendar_source.load_data(
                ics_file_path=file_path,
            )
            return IntentResult(
                was_intent_successful=True,
                data=timetracking_data,
            )
        else:
            timetracking_data: DataFrame = self._spreadsheet_source.load_data(
                file_path=file_path,
            )
            return IntentResult(
                was_intent_successful=True,
                data=timetracking_data,
            )

    def connect_to_cloud(
        self,
        provider: str,
        account_id: str,
        password: str,
    ) -> IntentResult[CloudConnector]:
        """"""
        try:
            # check cloud_calendar_info for the value of the cloud provider
            # if it is icloud, call the login_to_icloud method
            logger.info(
                f"Trying to connect to cloud provider {provider} with account {account_id}"
            )
            if provider == CloudProvider.ICloud.value:
                connector: CloudConnector = self._cloud_calendar_source.login_to_icloud(
                    apple_id=account_id,
                    password=password,
                )
                logger.info(
                    f"Successfully connected to iCloud with account {account_id}"
                )
                return IntentResult(
                    was_intent_successful=True,
                    data=connector,
                )
            else:
                return IntentResult(
                    was_intent_successful=False,
                    error_msg=f"Not implemented yet for cloud provider {provider}",
                )
        except Exception as ex:
            logger.exception(ex)
            return IntentResult(
                was_intent_successful=False,
                error_msg=f"Failed to connect to cloud provider {provider}",
                exception=ex,
            )

    def load_from_cloud_calendar(
        self,
        cloud_connector: CloudConnector,
        calendar_name: str,
    ) -> IntentResult[DataFrame]:
        """Loads time tracking data from a cloud calendar using a cloud connector"""
        try:
            calendar_data: DataFrame = self._cloud_calendar_source.load_data(
                cloud_connector=cloud_connector,
                calendar_name=calendar_name,
            )
            return IntentResult(
                was_intent_successful=True,
                data=calendar_data,
            )
        except Exception as ex:
            error_message = f"Failed to load data from cloud calendar {calendar_name}"
            logger.exception(ex)
            return IntentResult(
                was_intent_successful=False,
                error_msg=error_message,
                exception=ex,
            )

    def get_timetracking_data(self) -> IntentResult[Optional[DataFrame]]:
        try:
            data = self._timetracking_data_frame_source.get_data_frame()
            return IntentResult(
                was_intent_successful=True,
                data=data,
            )
        except Exception as ex:
            return IntentResult(
                was_intent_successful=False,
                error_msg="Failed to load time tracking data",
                exception=ex,
                data=None,
            )

    def set_timetracking_data(self, data: DataFrame) -> IntentResult[None]:
        try:
            self._timetracking_data_frame_source.store_data_frame(data=data)
            return IntentResult(
                was_intent_successful=True,
            )
        except Exception as ex:
            error_msg = "Failed to store time tracking data"
            logger.error(error_msg)
            logger.exception(ex)
            return IntentResult(
                was_intent_successful=False,
                error_msg=error_msg,
                exception=ex,
                data=None,
            )
