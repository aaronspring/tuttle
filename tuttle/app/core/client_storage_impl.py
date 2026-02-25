from typing import Optional, Any

from flet import Page

from ..core.abstractions import ClientStorage
from loguru import logger


class ClientStorageImpl(ClientStorage):
    """Flet's client storage API allows storing key-value data on a client side in a persistent storage.

    In Flet 0.80+, shared_preferences methods are async. This implementation
    maintains a sync in-memory cache that is pre-loaded at startup via
    load_cache(), then serves reads from cache and writes through to
    shared_preferences asynchronously via page.run_task().
    """

    def __init__(self, page: Page):
        super().__init__()
        self.__page = page
        self.__cache: dict[str, Any] = {}

    async def load_cache(self):
        """Pre-load all preferences with our key prefix into the in-memory cache.
        Must be awaited once at startup (from an async main)."""
        try:
            keys = await self.__page.shared_preferences.get_keys(self.keys_prefix)
            for key in keys or []:
                value = await self.__page.shared_preferences.get(key)
                self.__cache[key] = value
        except Exception as e:
            logger.error(f"Error loading preferences cache: {e.__class__.__name__}")
            logger.exception(e)

    def set_value(self, key: str, value: Any):
        full_key = self.keys_prefix + key
        self.__cache[full_key] = value
        try:
            self.__page.run_task(self.__page.shared_preferences.set, full_key, value)
        except Exception as e:
            logger.error(
                f"Error while setting client storage value {key} {value}: {e.__class__.__name__}"
            )
            logger.exception(e)

    def get_value(self, key: str) -> Optional[Any]:
        full_key = self.keys_prefix + key
        return self.__cache.get(full_key)

    def remove_value(self, key: str):
        full_key = self.keys_prefix + key
        self.__cache.pop(full_key, None)
        try:
            self.__page.run_task(self.__page.shared_preferences.remove, full_key)
        except Exception as e:
            logger.error(
                f"Error while removing client storage value {key}: {e.__class__.__name__}"
            )
            logger.exception(e)

    def clear_preferences(self):
        self.__cache.clear()
        try:
            self.__page.run_task(self.__page.shared_preferences.clear)
        except Exception as e:
            logger.error(f"Error while clearing client storage: {e.__class__.__name__}")
            logger.exception(e)
