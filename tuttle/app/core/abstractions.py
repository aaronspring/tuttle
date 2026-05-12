from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, List, Mapping, Optional, Type

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
import functools

import sqlalchemy
import sqlmodel
from sqlmodel import pool

from loguru import logger

from .intent_result import IntentResult

if TYPE_CHECKING:
    from flet import AlertDialog
    from .utils import AlertDialogControls


class DatabaseStorage(ABC):
    """Abstract class for database storage"""

    def __init__(
        self,
    ):
        super().__init__()

    @abstractmethod
    def create_model(self):
        """Creates database model"""
        pass

    @abstractmethod
    def ensure_database(self):
        """
        Ensure that the database exists and is up to date.
        """
        pass

    @abstractmethod
    def reset_database(self):
        """
        Delete the database and rebuild database model.
        """
        pass

    @abstractmethod
    def install_demo_data(
        self,
    ):
        """Install demo data into the database."""

    @abstractmethod
    def ensure_app_dir(self) -> Path:
        """Ensures that the user directory exists"""
        pass


class ClientStorage(ABC):
    """Abstract class for client storage"""

    def __init__(
        self,
    ):
        super().__init__()
        self.keys_prefix = "tuttle_app_"

    @abstractmethod
    def set_value(self, key: str, value: any):
        """appends an identifier prefix to the key and stores the key-value pair
        value can be a string, number, boolean or list
        """
        pass

    @abstractmethod
    def get_value(self, key: str) -> Optional[any]:
        """appends an identifier prefix to the key and gets the value if exists"""
        pass

    @abstractmethod
    def remove_value(self, key: str):
        """appends an identifier prefix to the key and removes associated key-value pair if exists"""
        pass

    @abstractmethod
    def clear_preferences(
        self,
    ):
        """Deletes all of preferences permanently"""
        pass


@dataclass
class TViewParams:
    """Parameters for TViews"""

    navigate_to_route: Callable
    show_snack: Callable
    dialog_controller: Callable
    pick_file_callback: Callable
    client_storage: ClientStorage
    keep_back_stack: bool = True
    on_navigate_back: Optional[Callable] = None
    vertical_alignment_in_parent: Any = None
    horizontal_alignment_in_parent: Any = None
    page_scroll_type: Any = None

    def __post_init__(self):
        from .utils import AUTO_SCROLL, START_ALIGNMENT, CROSS_START

        if self.vertical_alignment_in_parent is None:
            self.vertical_alignment_in_parent = START_ALIGNMENT
        if self.horizontal_alignment_in_parent is None:
            self.horizontal_alignment_in_parent = CROSS_START
        if self.page_scroll_type is None:
            self.page_scroll_type = AUTO_SCROLL


class TView(ABC):
    """Abstract class for all UI screens"""

    def __init__(self, params: TViewParams):
        super().__init__()
        self.navigate_to_route = params.navigate_to_route
        self.show_snack: Callable[[str, bool], None] = params.show_snack
        self.dialog_controller = params.dialog_controller
        self.vertical_alignment_in_parent = params.vertical_alignment_in_parent
        self.horizontal_alignment_in_parent = params.horizontal_alignment_in_parent
        self.keep_back_stack = params.keep_back_stack
        self.navigate_back = params.on_navigate_back
        self.page_scroll_type = params.page_scroll_type
        self.pick_file_callback = params.pick_file_callback
        self.client_storage = params.client_storage
        self.mounted = False

    def get_toolbar_items(self) -> list:
        """Return toolbar controls for this view (icon buttons, dropdowns, etc.).
        Override in subclasses. The shell renders these on the left side of the toolbar."""
        return []

    def parent_intent_listener(self, intent: str, data: any):
        """listens for an intent from parent view"""
        return

    def on_resume_after_back_pressed(
        self,
    ):
        """listener for when a view has been resumed after user pressed back from another view
        used by views whose self.keep_back_stack parameter is set to True
        """
        return

    def on_window_resized_listener(self, width, height):
        """sets the page width and height"""
        self.page_width = width
        self.page_height = height

    def update_self(
        self,
    ):
        """Triggers an update to the view only if the view is mounted"""
        try:
            if self.mounted:
                self.update()
        except Exception as e:
            logger.error(
                f"A view update caused an exception to be thrown {e.__class__.__name__}"
            )
            logger.exception(e)


class DialogHandler(ABC):
    """Used by views to set, open, and dismiss dialogs"""

    def __init__(
        self,
        dialog: AlertDialog,
        dialog_controller: Callable[[any, AlertDialogControls], None],
    ):
        super().__init__()
        self.dialog_controller = dialog_controller
        self.dialog = dialog

    def close_dialog(self, e: Optional[any] = None):
        from .utils import AlertDialogControls

        self.dialog_controller(self.dialog, AlertDialogControls.CLOSE)

    def open_dialog(self, e: Optional[any] = None):
        from .utils import AlertDialogControls

        self.dialog_controller(self.dialog, AlertDialogControls.ADD_AND_OPEN)

    def dimiss_open_dialogs(self):
        if self.dialog is not None and self.dialog.open:
            self.close_dialog()


# ---------------------------------------------------------------------------
# Active per-user database path (module-level state)
# ---------------------------------------------------------------------------

_active_db_path: Path = Path.home() / ".tuttle" / "tuttle.db"


def set_active_db(path: Path) -> None:
    """Switch all new data-source instances to use *path* as their SQLite DB."""
    global _active_db_path
    _active_db_path = path
    logger.info(f"Active user DB set to: {path}")


def get_active_db() -> Path:
    """Return the path to the currently active per-user database."""
    return _active_db_path


class SQLModelDataSourceMixin:
    """Implements common methods for data sources that interact with SQLModel"""

    def __init__(
        self,
    ):
        db_path = f"sqlite:///{_active_db_path}"
        logger.debug(f"Creating {self.__class__.__name__} with db_path: {db_path}")
        self.db_engine = sqlmodel.create_engine(
            db_path,
            echo=False,
            connect_args={"check_same_thread": False},
            poolclass=pool.StaticPool,
        )
        sqlalchemy.event.listen(
            self.db_engine,
            "connect",
            lambda dbapi_conn, _: dbapi_conn.execute("PRAGMA foreign_keys = ON"),
        )

    def create_session(self):
        return sqlmodel.Session(
            self.db_engine,
            expire_on_commit=False,
        )

    def query(self, entity_type: Type[sqlmodel.SQLModel]) -> List:
        """Queries the database for all instances of the given entity type"""
        logger.debug(f"querying {entity_type}")
        with self.create_session() as session:
            entities = session.exec(sqlmodel.select(entity_type)).all()
        if len(entities) == 0:
            logger.warning(f"No instances of {entity_type} found")
        else:
            logger.debug(f"Found {len(entities)} instances of {entity_type}")
        return entities

    def query_by_id(
        self,
        entity_type: Type[sqlmodel.SQLModel],
        entity_id: int,
    ) -> Optional[sqlmodel.SQLModel]:
        """Queries the database for an instance of the given entity type with the given id"""
        logger.debug(f"querying {entity_type} by id={entity_id}")
        with self.create_session() as session:
            entity = session.exec(
                sqlmodel.select(entity_type).where(entity_type.id == entity_id)
            ).one()
        if entity is None:
            logger.warning(f"No instance of {entity_type} found with id={entity_id}")
        else:
            logger.info(f"Found instance of {entity_type} with id={entity_id}")
        return entity

    def query_where(
        self,
        entity_type: Type[sqlmodel.SQLModel],
        field_name: str,
        field_value: Any,
    ) -> List:
        """Queries the database for all instances of the given entity type that have the given field value"""
        logger.debug(f"querying {entity_type} by {field_name}={field_value}")
        with self.create_session() as session:
            entities = session.exec(
                sqlmodel.select(entity_type).where(
                    getattr(entity_type, field_name) == field_value
                )
            ).all()
        if len(entities) == 0:
            logger.warning(f"No instances of {entity_type} found")
        else:
            logger.info(f"Found {len(entities)} instances of {entity_type}")
        return entities

    def query_the_only(self, entity_type: Type[sqlmodel.SQLModel]) -> sqlmodel.SQLModel:
        """Queries the database for the only instance of the given entity type. Raises an error if there are more than one"""
        entities = self.query(entity_type)
        if len(entities) > 1:
            raise Exception(f"More than one {entity_type} found")
        elif len(entities) == 1:
            return entities[0]
        else:
            return None

    def store(self, entity: sqlmodel.SQLModel):
        """Stores the given entity in the database"""
        # logger.debug(f"storing {entity}")
        with self.create_session() as session:
            session.add(entity)
            session.commit()
            session.refresh(entity)

    def delete_by_id(self, entity_type: Type[sqlmodel.SQLModel], entity_id: int):
        """Deletes the entity of the given type with the given id from the database.

        Uses ORM-level delete so that cascade relationships are honoured.
        Raises ``sqlalchemy.exc.IntegrityError`` when a foreign-key
        constraint prevents the deletion (e.g. entity is still referenced).
        """
        logger.debug(f"deleting {entity_type} with id={entity_id}")
        with self.create_session() as session:
            entity = session.get(entity_type, entity_id)
            if entity is None:
                raise ValueError(
                    f"{entity_type.__name__} with id={entity_id} not found"
                )
            session.delete(entity)
            session.commit()


class Intent(ABC):
    """Abstract base class for intent classes."""

    def __getattribute__(self, name):
        """Logs all calls to methods of this class""" ""
        attr = object.__getattribute__(self, name)
        if callable(attr) and not isinstance(attr, type):

            @functools.wraps(attr)
            def wrapped(*args, **kwargs):
                class_name = self.__class__.__name__
                # Mask password argument if exists
                kwargs = {
                    k: "******" if k == "password" else v for k, v in kwargs.items()
                }
                logger.debug(f"Intent: {class_name}:{name} called with: {kwargs}")
                return attr(*args, **kwargs)

            return wrapped
        return attr


class CrudIntent(SQLModelDataSourceMixin, Intent):
    """Generic CRUD intent that combines data access and business logic.

    Subclasses must set `entity_type` to the SQLModel class they manage.
    Optionally set `entity_name` for human-readable error messages.

    To prevent deletion when related records exist, set ``deletion_guards``
    to a list of ``(relationship_attr, label, display_func)`` tuples.
    *relationship_attr* is the attribute name on the entity that holds the
    referencing collection, *label* is a human-readable noun (plural) for
    the error message, and *display_func* extracts a short display string
    from each related object.
    """

    entity_type: Type[sqlmodel.SQLModel]
    entity_name: str = ""
    deletion_guards: List[tuple] = []

    def __init__(self):
        SQLModelDataSourceMixin.__init__(self)
        if not self.entity_name:
            self.entity_name = self.entity_type.__name__

    # -- Generic CRUD ----------------------------------------------------------

    def get_all(self) -> IntentResult:
        """Fetch all entities of this type."""
        try:
            entities = self.query(self.entity_type)
            return IntentResult(was_intent_successful=True, data=entities)
        except Exception as e:
            return IntentResult(
                was_intent_successful=False,
                error_msg=f"Failed to load {self.entity_name}s.",
                log_message=f"{self.__class__.__name__}.get_all: {e}",
                exception=e,
            )

    def get_all_as_map(self) -> Mapping[int, Any]:
        """Fetch all entities as {id: entity} dict."""
        result = self.get_all()
        if result.was_intent_successful:
            return {entity.id: entity for entity in result.data}
        result.log_message_if_any()
        return {}

    def get_by_id(self, entity_id) -> IntentResult:
        """Fetch a single entity by its id."""
        try:
            entity = self.query_by_id(self.entity_type, entity_id)
            return IntentResult(was_intent_successful=True, data=entity)
        except Exception as e:
            return IntentResult(
                was_intent_successful=False,
                error_msg=f"Failed to load {self.entity_name}.",
                log_message=f"{self.__class__.__name__}.get_by_id({entity_id}): {e}",
                exception=e,
            )

    def save(self, entity) -> IntentResult:
        """Create or update an entity."""
        try:
            self.store(entity)
            return IntentResult(was_intent_successful=True, data=entity)
        except Exception as e:
            return IntentResult(
                was_intent_successful=False,
                error_msg=f"Failed to save {self.entity_name}.",
                log_message=f"{self.__class__.__name__}.save: {e}",
                exception=e,
            )

    def delete(self, entity_id) -> IntentResult:
        """Delete an entity by its id.

        Checks ``deletion_guards`` first to produce a user-friendly message
        when related records still reference this entity.  Falls back to the
        database-level ``IntegrityError`` as a safety net.
        """
        if self.deletion_guards:
            result = self.get_by_id(entity_id)
            if not result.was_intent_successful:
                return result
            entity = result.data
            for attr, label, display_fn in self.deletion_guards:
                related = getattr(entity, attr, None) or []
                if related:
                    names = ", ".join(display_fn(r) for r in related)
                    entity_desc = getattr(entity, "name", None) or getattr(
                        entity, "title", f"#{entity_id}"
                    )
                    return IntentResult(
                        was_intent_successful=False,
                        error_msg=(
                            f"Cannot delete {self.entity_name} "
                            f"'{entity_desc}' because it is "
                            f"referenced by {label}: {names}"
                        ),
                    )
        try:
            self.delete_by_id(self.entity_type, entity_id)
            return IntentResult(was_intent_successful=True)
        except sqlalchemy.exc.IntegrityError as e:
            return IntentResult(
                was_intent_successful=False,
                error_msg=(
                    f"Cannot delete this {self.entity_name} because it is "
                    f"still referenced by other records."
                ),
                log_message=f"{self.__class__.__name__}.delete({entity_id}): {e}",
                exception=e,
            )
        except Exception as e:
            return IntentResult(
                was_intent_successful=False,
                error_msg=f"Failed to delete {self.entity_name}.",
                log_message=f"{self.__class__.__name__}.delete({entity_id}): {e}",
                exception=e,
            )

    # -- Filtered views (require is_completed / is_active / is_upcoming) -------

    def get_completed_as_map(self) -> Mapping[int, Any]:
        return {k: v for k, v in self.get_all_as_map().items() if v.is_completed}

    def get_active_as_map(self) -> Mapping[int, Any]:
        return {k: v for k, v in self.get_all_as_map().items() if v.is_active()}

    def get_upcoming_as_map(self) -> Mapping[int, Any]:
        return {k: v for k, v in self.get_all_as_map().items() if v.is_upcoming()}

    # -- Toggle helpers --------------------------------------------------------

    def toggle_completed(self, entity) -> IntentResult:
        """Toggle is_completed and save. Rolls back on failure."""
        entity.is_completed = not entity.is_completed
        result = self.save(entity)
        if not result.was_intent_successful:
            entity.is_completed = not entity.is_completed
        result.data = entity
        return result
