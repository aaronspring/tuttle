from typing import Callable, Optional

from flet import (
    AlertDialog,
    FilePicker,
    FilePickerUploadFile,
    Page,
    SnackBar,
    TemplateRoute,
    ThemeMode,
    View,
    run,
)

from loguru import logger
from pandas import DataFrame


from tuttle.app.auth.view import ProfileScreen, SplashScreen
from tuttle.app.contracts.view import ContractEditorScreen, ViewContractScreen
from tuttle.app.core.abstractions import TView, TViewParams
from tuttle.app.core.client_storage_impl import ClientStorageImpl
from tuttle.app.core.database_storage_impl import DatabaseStorageImpl
from tuttle.app.core.models import RouteView
from tuttle.app.core.utils import AlertDialogControls
from tuttle.app.core.views import THeading
from tuttle.app.error_views.page_not_found_screen import Error404Screen
from tuttle.app.home.view import HomeScreen
from tuttle.app.preferences.intent import PreferencesIntent
from tuttle.app.preferences.model import PreferencesStorageKeys
from tuttle.app.preferences.view import PreferencesScreen
from tuttle.app.projects.view import ProjectEditorScreen, ViewProjectScreen
from tuttle.app.res.colors import (
    accent,
    bg,
    bg_surface,
    danger,
    text_inverse,
    text_primary,
    # backward-compat aliases still used elsewhere
    BLACK_COLOR_ALT,
    ERROR_COLOR,
    PRIMARY_COLOR,
    WHITE_COLOR,
)
from tuttle.app.res.dimens import MIN_WINDOW_HEIGHT, MIN_WINDOW_WIDTH
from tuttle.app.res.fonts import APP_FONTS, HEADLINE_4_SIZE, HEADLINE_FONT
from tuttle.app.res.res_utils import (
    CONTRACT_DETAILS_SCREEN_ROUTE,
    CONTRACT_EDITOR_SCREEN_ROUTE,
    HOME_SCREEN_ROUTE,
    PREFERENCES_SCREEN_ROUTE,
    PROFILE_SCREEN_ROUTE,
    PROJECT_DETAILS_SCREEN_ROUTE,
    PROJECT_EDITOR_SCREEN_ROUTE,
    SPLASH_SCREEN_ROUTE,
)
from tuttle.app.res.theme import APP_THEME, THEME_MODES, get_theme_mode_from_value
from tuttle.app.timetracking.intent import TimeTrackingIntent


class TuttleApp:
    """The main application class"""

    def __init__(
        self,
        page: Page,
        debug_mode: bool = False,
    ):
        """ """
        self.debug_mode = debug_mode
        self.page = page
        self.page.title = "Tuttle"
        self.page.fonts = APP_FONTS
        self.page.theme = APP_THEME
        self.page.theme_mode = ThemeMode.DARK
        self.page.window.bgcolor = bg
        self.client_storage = ClientStorageImpl(page=self.page)
        self.db = DatabaseStorageImpl(
            store_demo_timetracking_dataframe=self.store_demo_timetracking_dataframe,
            debug_mode=self.debug_mode,
        )
        self.page.window.min_width = MIN_WINDOW_WIDTH
        self.page.window.min_height = MIN_WINDOW_HEIGHT
        self.page.window.width = MIN_WINDOW_WIDTH + 400
        self.page.window.height = MIN_WINDOW_HEIGHT + 200
        self.file_picker = FilePicker()

        """holds the RouteView object associated with a route
        used in on route change"""
        self.route_to_route_view_cache = {}
        self.page.on_route_change = self.on_route_change
        self.page.on_view_pop = self.on_view_pop
        self.route_parser = TuttleRoutes(self)
        self.current_route_view: Optional[RouteView] = None
        self.page.on_resize = self.page_resize

    def page_resize(self, e):
        if self.current_route_view:
            self.current_route_view.on_window_resized(e.width, e.height)

    def pick_file_callback(
        self,
        on_file_picker_result,
        allowed_extensions,
        dialog_title,
        file_type,
    ):
        from types import SimpleNamespace
        from flet import FilePickerFileType

        file_type_map = {
            "any": FilePickerFileType.ANY,
            "custom": FilePickerFileType.CUSTOM,
            "image": FilePickerFileType.IMAGE,
            "media": FilePickerFileType.MEDIA,
            "video": FilePickerFileType.VIDEO,
            "audio": FilePickerFileType.AUDIO,
        }
        ft_file_type = (
            file_type_map.get(file_type, FilePickerFileType.ANY)
            if isinstance(file_type, str)
            else file_type
        )

        import sys

        if sys.platform == "darwin" and ft_file_type == FilePickerFileType.CUSTOM:
            ft_file_type = FilePickerFileType.ANY

        async def _pick_files():
            pick_kwargs = dict(
                allow_multiple=False,
                dialog_title=dialog_title,
                file_type=ft_file_type,
            )
            if ft_file_type == FilePickerFileType.CUSTOM and allowed_extensions:
                pick_kwargs["allowed_extensions"] = allowed_extensions
            files = await self.file_picker.pick_files(**pick_kwargs)
            if files and allowed_extensions:
                files = [
                    f
                    for f in files
                    if any(
                        f.name.lower().endswith(f".{ext.lower()}")
                        for ext in allowed_extensions
                    )
                ]
            result = SimpleNamespace(files=files)
            on_file_picker_result(result)

        self.page.run_task(_pick_files)

    def on_theme_mode_changed(self, selected_theme: str):
        """callback function used by views for changing app theme mode"""
        mode = get_theme_mode_from_value(selected_theme)
        self.page.theme_mode = ThemeMode.DARK
        self.page.update()

    def show_snack(
        self,
        message: str,
        is_error: bool = False,
        action_label: Optional[str] = None,
        action_callback: Optional[Callable] = None,
    ):
        """callback function used by views to display a snack bar message"""
        from flet import SnackBarAction

        action = None
        if action_label:
            action = SnackBarAction(
                label=action_label,
                text_color=accent,
                on_click=action_callback,
            )
        snack = SnackBar(
            content=THeading(
                title=message,
                size=HEADLINE_4_SIZE,
                color=danger if is_error else text_primary,
            ),
            bgcolor=bg_surface,
            action=action,
            open=True,
        )
        self.page.show_dialog(snack)

    def control_alert_dialog(
        self,
        dialog: Optional[AlertDialog] = None,
        control: AlertDialogControls = AlertDialogControls.CLOSE,
    ):
        """handles adding, opening and closing of page alert dialogs"""
        if control.value == AlertDialogControls.ADD_AND_OPEN.value:
            if dialog:
                dialog.open = True
                self.page.show_dialog(dialog)

        if control.value == AlertDialogControls.CLOSE.value:
            if dialog:
                dialog.open = False
                self.page.pop_dialog()

    def change_route(self, to_route: str, data: Optional[any] = None):
        """navigates to a new route"""
        newRoute = to_route if data is None else f"{to_route}/{data}"
        self.page.run_task(self.page.push_route, newRoute)

    def on_view_pop(self, e=None):
        """invoked on back pressed"""
        if len(self.page.views) == 1:
            return
        if e is not None and hasattr(e, "view") and e.view is not None:
            self.page.views.remove(e.view)
        else:
            self.page.views.pop()
        current_page_view: View = self.page.views[-1]
        self.page.run_task(self.page.push_route, current_page_view.route)
        if current_page_view.controls:
            try:
                tuttle_view: TView = current_page_view.controls[0]
                tuttle_view.on_resume_after_back_pressed()
            except Exception as ex:
                logger.error(
                    f"Exception raised @TuttleApp.on_view_pop {ex.__class__.__name__}"
                )
                logger.exception(ex)

    def on_route_change(self, e=None):
        """auto invoked when the route changes

        parses the new destination route
        then appends the new page to page views
        """
        current_route = self.page.route

        if current_route in self.route_to_route_view_cache:
            # route already visited: reuse cached view
            self.current_route_view = self.route_to_route_view_cache[current_route]
            self.page.update()
            self.current_route_view.on_window_resized(
                self.page.window.width, self.page.window.height
            )
            return

        # build a new view for this route
        route_view_wrapper = self.route_parser.parse_route(pageRoute=current_route)
        if not route_view_wrapper.keep_back_stack:
            self.route_to_route_view_cache.clear()
            self.page.views.clear()
        self.route_to_route_view_cache[current_route] = route_view_wrapper
        self.page.views.append(route_view_wrapper.view)
        self.current_route_view = route_view_wrapper
        self.page.update()
        self.current_route_view.on_window_resized(
            self.page.window.width, self.page.window.height
        )

    def store_demo_timetracking_dataframe(self, time_tracking_data: DataFrame):
        """Caches the time tracking dataframe created from a demo installation"""
        self.timetracking_intent = TimeTrackingIntent(
            client_storage=self.client_storage
        )
        self.timetracking_intent.set_timetracking_data(data=time_tracking_data)

    def build(self):
        self.on_route_change()

    def close(self):
        """Closes the application."""
        self.page.window.close()

    def reset_and_quit(self):
        """Resets the application and quits."""
        self.db.reset_database()
        self.close()


class TuttleRoutes:
    """Utility class for parsing of routes to destination views"""

    def __init__(self, app: TuttleApp):
        # init callbacks for some views
        self.on_theme_changed = app.on_theme_mode_changed
        self.on_reset_and_quit = app.reset_and_quit
        self.on_install_demo_data = app.db.install_demo_data
        self.file_picker = app.file_picker
        # init common params for views
        self.tuttle_view_params = TViewParams(
            navigate_to_route=app.change_route,
            show_snack=app.show_snack,
            dialog_controller=app.control_alert_dialog,
            on_navigate_back=app.on_view_pop,
            client_storage=app.client_storage,
            pick_file_callback=app.pick_file_callback,
        )

    def get_page_route_view(
        self,
        routeName: str,
        view: TView,
    ) -> RouteView:
        """Constructs the view with a given route"""
        view_container = View(
            padding=0,
            spacing=0,
            route=routeName,
            scroll=view.page_scroll_type,
            controls=[view],
            vertical_alignment=view.vertical_alignment_in_parent,
            horizontal_alignment=view.horizontal_alignment_in_parent,
            bgcolor=bg,
            services=[self.file_picker],
        )

        return RouteView(
            view=view_container,
            on_window_resized=view.on_window_resized_listener,
            keep_back_stack=view.keep_back_stack,
        )

    def parse_route(self, pageRoute: str):
        """parses a given route path and returns it's view"""

        routePath = TemplateRoute(pageRoute)
        screen = None
        if routePath.match(SPLASH_SCREEN_ROUTE):
            screen = SplashScreen(
                params=self.tuttle_view_params,
                on_install_demo_data=self.on_install_demo_data,
            )
        elif routePath.match(HOME_SCREEN_ROUTE):
            screen = HomeScreen(
                params=self.tuttle_view_params,
            )
        elif routePath.match(PROFILE_SCREEN_ROUTE):
            screen = ProfileScreen(
                params=self.tuttle_view_params,
            )
        elif routePath.match(CONTRACT_EDITOR_SCREEN_ROUTE):
            screen = ContractEditorScreen(params=self.tuttle_view_params)
        elif routePath.match(f"{CONTRACT_DETAILS_SCREEN_ROUTE}/:contractId"):
            screen = ViewContractScreen(
                params=self.tuttle_view_params, contract_id=routePath.contractId
            )
        elif routePath.match(f"{CONTRACT_EDITOR_SCREEN_ROUTE}/:contractId"):
            contractId = None
            if hasattr(routePath, "contractId"):
                contractId = routePath.contractId
            screen = ContractEditorScreen(
                params=self.tuttle_view_params, contract_id_if_editing=contractId
            )
        elif routePath.match(PREFERENCES_SCREEN_ROUTE):
            screen = PreferencesScreen(
                params=self.tuttle_view_params,
                on_theme_changed_callback=self.on_theme_changed,
                on_reset_app_callback=self.on_reset_and_quit,
            )
        elif routePath.match(PROJECT_EDITOR_SCREEN_ROUTE):
            screen = ProjectEditorScreen(params=self.tuttle_view_params)
        elif routePath.match(f"{PROJECT_DETAILS_SCREEN_ROUTE}/:projectId"):
            screen = ViewProjectScreen(
                params=self.tuttle_view_params, project_id=routePath.projectId
            )
        elif routePath.match(PROJECT_EDITOR_SCREEN_ROUTE) or routePath.match(
            f"{PROJECT_EDITOR_SCREEN_ROUTE}/:projectId"
        ):
            projectId = None
            if hasattr(routePath, "projectId"):
                projectId = routePath.projectId
            screen = ProjectEditorScreen(
                params=self.tuttle_view_params, project_id_if_editing=projectId
            )
        else:
            screen = Error404Screen(params=self.tuttle_view_params)

        return self.get_page_route_view(routePath.route, view=screen)


def get_assets_uploads_url(with_parent_dir: bool = False):
    uploads_parent_dir = "assets"
    uploads_dir = "uploads"
    if with_parent_dir:
        return f"{uploads_parent_dir}/{uploads_dir}"
    return uploads_dir


async def main(page: Page):
    """Entry point of the app"""
    app = TuttleApp(page)

    # if database does not exist, create it
    app.db.ensure_database()

    # pre-load shared preferences cache (async in Flet 0.80+)
    await app.client_storage.load_cache()

    app.build()


if __name__ == "__main__":
    run(
        name="Tuttle",
        main=main,
        assets_dir="assets",
        upload_dir=get_assets_uploads_url(with_parent_dir=True),
    )
