from typing import Callable, Optional
from pathlib import Path
from flet import (
    BorderRadius,
    ButtonStyle,
    Column,
    Container,
    CrossAxisAlignment,
    Icon,
    IconButton,
    Icons,
    MainAxisAlignment,
    Padding,
    ResponsiveRow,
    Row,
    ScrollMode,
    Text,
    TextButton,
)

from ..auth.intent import AuthIntent
from ..core import utils, views
from ..core.abstractions import TView, TViewParams
from ..core.intent_result import IntentResult
from ..res import dimens, fonts, image_paths, res_utils, colors
from ...model import User, BankAccount
from ...tax import supported_countries


class PaymentDataForm(Column):
    """Form view for setting the user's payment info"""

    def __init__(
        self,
        on_form_submit: Callable[[User], None],
    ):
        super().__init__()
        self.on_form_submit = on_form_submit
        self.user: User = None

    def set_form_data(self):
        """Sets the form data to the user's current data"""
        if not self.user.bank_account:
            # Create a new bank account if none exists
            self.user.bank_account = BankAccount(name="", BIC="", IBAN="")
        self.bank_bic_field.value = self.user.bank_account.BIC
        self.bank_name_field.value = self.user.bank_account.name
        self.bank_iban_field.value = self.user.bank_account.IBAN
        self.vat_number_field.value = self.user.VAT_number

    def update_form_data(self, user: User):
        """Updates the user's data with the form data"""
        self.user = user
        if not hasattr(self, "bank_bic_field"):
            return
        self.set_form_data()
        self.update()

    def on_click_save(self, e):
        """Called when the save button is clicked"""
        self.user.VAT_number = self.vat_number_field.value
        self.user.bank_account.BIC = self.bank_bic_field.value
        self.user.bank_account.IBAN = self.bank_iban_field.value
        self.user.bank_account.name = self.bank_name_field.value
        self.on_form_submit(self.user)

    def build(self):
        """Called when form is built"""
        self.vat_number_field = views.TTextField(
            label="VAT Number",
            hint="Value Added Tax number of the user, legally required for invoices.",
        )
        self.bank_name_field = views.TTextField(
            label="Name",
            hint="Name of account",
        )
        self.bank_iban_field = views.TTextField(
            label="IBAN",
            hint="International Bank Account Number",
        )
        self.bank_bic_field = views.TTextField(
            label="BIC",
            hint="Bank Identifier Code",
        )
        if self.user is not None:
            self.set_form_data()
        self.spacing = dimens.SPACE_MD
        self.controls = [
            self.vat_number_field,
            views.Spacer(xs_space=True),
            views.TSubHeading("Bank Account"),
            self.bank_name_field,
            self.bank_iban_field,
            self.bank_bic_field,
            views.Spacer(),
            views.TPrimaryButton(
                label="Save",
                on_click=self.on_click_save,
            ),
        ]


class UserDataForm(Column):
    """Form view for setting the user info"""

    def __init__(
        self,
        on_submit_success: Callable,
        on_form_submit: Callable,
        submit_btn_label: str,
    ):
        super().__init__()
        """
        Parameters
        ----------
        on_submit_success : Callable
            Callback function to handle when the form submission is successful
        on_form_submit : Callable
            Callback function to handle when the form's submit button  is clicked
        submit_btn_label : str
            The label to display on the submit button
        """
        self.on_form_submit = on_form_submit
        self.on_submit_success = on_submit_success
        self.submit_btn_label = submit_btn_label

    def toggle_form_err(self, error: str = ""):
        """hides or displays the form error

        *a form error is not tied to a single specific field
        """
        self.form_err_control.value = error
        self.form_err_control.visible = error != ""
        self.update()

    def on_field_focus(self, e):
        for field in [
            self.name_field,
            self.email_field,
            self.phone_field,
            self.subtitle_field,
        ]:
            field.error = ""
        self.toggle_form_err()
        self.update()

    def on_submit_btn_clicked(self, e):
        # prevent multiple clicking
        self.submit_btn.disabled = True

        # hide any errors
        self.toggle_form_err()

        missing_required_data_err = ""

        # get the form data
        subtitle = self.subtitle_field.value
        name = self.name_field.value
        email = self.email_field.value
        phone_number = self.phone_field.value
        address_street = self.street_field.value
        address_postal_code = self.postal_code_field.value
        address_number = self.street_number_field.value
        address_city = self.city_field.value
        address_country = self.country_field.value
        operating_country = self.operating_country_field.value or ""
        website = self.website_field.value

        # validate the form data
        if utils.is_empty_str(subtitle):
            missing_required_data_err = "Please specify your job title. e.g. freelancer"
            self.subtitle_field.error = missing_required_data_err

        elif utils.is_empty_str(name):
            missing_required_data_err = "Your name is required."
            self.name_field.error = missing_required_data_err

        elif utils.is_empty_str(email):
            missing_required_data_err = "Your email is required."
            self.email_field.error = missing_required_data_err

        elif (
            utils.is_empty_str(address_street)
            or utils.is_empty_str(address_number)
            or utils.is_empty_str(address_postal_code)
            or utils.is_empty_str(address_country)
            or utils.is_empty_str(address_city)
        ):
            missing_required_data_err = "Please provide your full address"
            self.toggle_form_err(missing_required_data_err)

        elif utils.is_empty_str(operating_country):
            missing_required_data_err = "Please select your operating country"
            self.toggle_form_err(missing_required_data_err)

        if not missing_required_data_err:
            result: IntentResult = self.on_form_submit(
                title=subtitle,
                name=name,
                email=email,
                phone=phone_number,
                street=address_street,
                street_num=address_number,
                postal_code=address_postal_code,
                city=address_city,
                country=address_country,
                website=website,
                operating_country=operating_country,
            )
            if not result.was_intent_successful:
                self.toggle_form_err(result.error_msg)
                self.update()
            else:
                # user is authenticated
                self.on_submit_success(result.data)
        self.submit_btn.disabled = False
        self.update()

    def build(self):
        """Called when form is built"""
        self.name_field = views.TTextField(
            label="Name",
            hint="your name",
            on_focus=self.on_field_focus,
            keyboard_type=utils.KEYBOARD_NAME,
        )
        self.email_field = views.TTextField(
            label="Email",
            hint="your email address",
            on_focus=self.on_field_focus,
            keyboard_type=utils.KEYBOARD_EMAIL,
        )
        self.phone_field = views.TTextField(
            label="Phone (optional)",
            hint="your phone number",
            on_focus=self.on_field_focus,
            keyboard_type=utils.KEYBOARD_PHONE,
        )
        self.subtitle_field = views.TTextField(
            label="Job Title",
            hint="What is your role as a freelancer?",
            on_focus=self.on_field_focus,
            keyboard_type=utils.KEYBOARD_TEXT,
        )
        self.website_field = views.TTextField(
            label="Website (optional)",
            hint="URL of your website.",
        )
        self.street_field = views.TTextField(
            label="Street Name",
            expand=1,
        )
        self.street_number_field = views.TTextField(
            label="Street Number",
            keyboard_type=utils.KEYBOARD_NUMBER,
            expand=1,
        )
        self.postal_code_field = views.TTextField(
            label="Postal Code",
            keyboard_type=utils.KEYBOARD_NUMBER,
            expand=1,
        )

        self.city_field = views.TTextField(
            label="City",
            expand=1,
        )
        self.country_field = views.TTextField(
            label="Country",
        )
        self.operating_country_field = views.TDropDown(
            label="Operating Country (tax jurisdiction)",
            items=supported_countries(),
            hint="Select the country you freelance under",
        )
        self.form_err_control = views.TErrorText("")
        self.submit_btn = views.TPrimaryButton(
            on_click=self.on_submit_btn_clicked,
            label=self.submit_btn_label,
        )
        if hasattr(self, "_pending_user") and self._pending_user is not None:
            self._apply_user_info(self._pending_user)
        self.spacing = dimens.SPACE_MD
        self.controls = [
            self.subtitle_field,
            self.name_field,
            self.email_field,
            self.phone_field,
            self.website_field,
            Row(
                vertical_alignment=utils.CENTER_ALIGNMENT,
                controls=[
                    self.street_field,
                    self.street_number_field,
                ],
            ),
            Row(
                vertical_alignment=utils.CENTER_ALIGNMENT,
                controls=[
                    self.postal_code_field,
                    self.city_field,
                ],
            ),
            self.country_field,
            self.operating_country_field,
            self.form_err_control,
            self.submit_btn,
        ]

    def refresh_user_info(self, user: User):
        if user is None:
            return
        self._pending_user = user
        if not hasattr(self, "name_field"):
            return
        self._apply_user_info(user)

    def _apply_user_info(self, user: User):
        self.name_field.value = user.name
        self.email_field.value = user.email
        self.phone_field.value = user.phone_number
        self.subtitle_field.value = user.subtitle
        self.street_field.value = user.address.street
        self.postal_code_field.value = user.address.postal_code
        self.street_number_field.value = user.address.number
        self.city_field.value = user.address.city
        self.country_field.value = user.address.country
        if user.operating_country:
            self.operating_country_field.update_value(user.operating_country)
        self.website_field.value = user.website
        self.update()


class SplashScreen(TView, Column):
    """Displayed the first time the app loads

    Checks if user has been created
    If created, redirects user to the homepage
    If not created, displays a create user form
    """

    def __init__(
        self,
        params: TViewParams,
        on_install_demo_data: Callable,
    ):
        super().__init__(params=params)
        self.keep_back_stack = False  # User cannot go back from this screen
        self.intent = AuthIntent()
        self.client_storage = params.client_storage
        self.on_install_demo_data = on_install_demo_data

    def show_login_if_signed_out_else_redirect(self):
        result = self.intent.get_user_if_exists()
        if result.was_intent_successful:
            if result.data is not None:
                self.navigate_to_route(res_utils.HOME_SCREEN_ROUTE)
            else:
                # clear preferences if any
                self.client_storage.clear_preferences()
                self.set_login_form()
        else:
            self.show_snack(result.error_msg)

    def set_login_form(self):
        form = UserDataForm(
            on_submit_success=lambda _: self.navigate_to_route(
                res_utils.HOME_SCREEN_ROUTE
            ),
            on_form_submit=lambda title, name, email, phone, street, street_num, postal_code, city, country, website, operating_country="Germany": self.intent.create_user(
                title=title,
                name=name,
                email=email,
                phone=phone,
                street=street,
                street_num=street_num,
                postal_code=postal_code,
                city=city,
                country=country,
                website=website,
                operating_country=operating_country,
            ),
            submit_btn_label="Save Profile",
        )
        self.form_container.controls.remove(self.loading_indicator)
        self.form_container.controls.append(form)
        self.update_self()

    def on_proceed_with_demo_data_clicked(self, e):
        """when the user clicks on the proceed with demo data button"""
        self.on_install_demo_data()  # install demo data
        self.navigate_to_route(res_utils.HOME_SCREEN_ROUTE)  # navigate to home screen

    def did_mount(self):
        self.mounted = True
        self.show_login_if_signed_out_else_redirect()

    def build(self):
        self.loading_indicator = views.TProgressBar()
        self.form_container = Column(
            controls=[
                # views.TAppLogoWithLabel(),
                views.THeadingWithSubheading(
                    "Welcome to Tuttle",
                    "Let's get you started: Please enter your details below. Your data will be stored locally and will not be sent to a server.",
                ),
                self.loading_indicator,
                views.Spacer(),
            ]
        )
        page_view = ResponsiveRow(
            spacing=0,
            run_spacing=0,
            alignment=utils.CENTER_ALIGNMENT,
            vertical_alignment=utils.CENTER_ALIGNMENT,
            controls=[
                Container(
                    col={"xs": 12, "sm": 5},
                    padding=Padding.all(dimens.SPACE_XS),
                    content=Column(
                        alignment=utils.START_ALIGNMENT,
                        horizontal_alignment=utils.CENTER_ALIGNMENT,
                        expand=True,
                        controls=[
                            views.Spacer(md_space=True),
                            views.TImage(
                                image_paths.splashImgPath,
                                "welcome screen image",
                                width=300,
                            ),
                            views.THeadingWithSubheading(
                                "Tuttle",
                                "Time and money management for freelancers",
                                alignment_in_container=utils.CENTER_ALIGNMENT,
                                txt_alignment=utils.TXT_ALIGN_CENTER,
                                title_size=fonts.HEADLINE_3_SIZE,
                                subtitle_size=fonts.HEADLINE_4_SIZE,
                            ),
                        ],
                    ),
                ),
                Container(
                    col={"xs": 12, "sm": 7},
                    padding=Padding.all(dimens.SPACE_XL),
                    content=Column(
                        [
                            self.form_container,
                            views.TSecondaryButton(
                                on_click=self.on_proceed_with_demo_data_clicked,
                                label="Proceed with demo",
                                icon="TOYS",
                            ),
                        ]
                    ),
                ),
            ],
        )
        self.controls = [page_view]

    def will_unmount(self):
        self.mounted = False


class ProfileScreen(TView, Column):
    """User profile screen — single-page layout with back button."""

    def __init__(self, params: TViewParams):
        super().__init__(params=params)
        self._profile_content = ProfileContent(params=params)

    def build(self):
        self.controls = [
            Container(
                padding=Padding.symmetric(
                    horizontal=dimens.SPACE_XL,
                    vertical=dimens.SPACE_MD,
                ),
                expand=True,
                content=Column(
                    controls=[
                        IconButton(
                            icon=Icons.KEYBOARD_ARROW_LEFT,
                            on_click=self.navigate_back,
                            icon_size=dimens.MD_ICON_SIZE,
                        ),
                        self._profile_content,
                    ],
                    expand=True,
                ),
            ),
        ]

    def did_mount(self):
        self.mounted = True

    def will_unmount(self):
        self.mounted = False


class ProfileContent(TView, Column):
    """Display-first profile page with flat settings-style layout and inline editing."""

    _LABEL_WIDTH = 140

    def __init__(self, params: TViewParams):
        super().__init__(params=params)
        self.intent = AuthIntent()
        self.user_profile: User = None
        self.uploaded_photo_path = ""

    # ── Layout helpers ────────────────────────────────────────

    @staticmethod
    def _profile_row(label: str, value: str) -> Row:
        """Label-value row: muted fixed-width label + primary-color value."""
        return Row(
            controls=[
                Text(
                    label,
                    size=fonts.BODY_1_SIZE,
                    color=colors.text_muted,
                    width=ProfileContent._LABEL_WIDTH,
                ),
                Text(
                    value if value else "\u2014",
                    size=fonts.BODY_1_SIZE,
                    color=colors.text_primary if value else colors.text_muted,
                    expand=True,
                ),
            ],
            spacing=dimens.SPACE_MD,
        )

    @staticmethod
    def _section_divider() -> Container:
        """Subtle 1px hairline divider."""
        return Container(height=1, bgcolor=colors.border)

    @staticmethod
    def _section_header(title: str, on_edit=None) -> Row:
        """Section heading with optional right-aligned Edit text button."""
        controls = [
            Text(
                title,
                size=fonts.HEADLINE_3_SIZE,
                color=colors.text_primary,
                weight=fonts.BOLD_FONT,
                expand=True,
            ),
        ]
        if on_edit:
            controls.append(
                TextButton(
                    "Edit",
                    on_click=on_edit,
                    style=ButtonStyle(color=colors.accent),
                )
            )
        return Row(controls=controls)

    @staticmethod
    def _format_address(address) -> str:
        if not address or address.is_empty:
            return ""
        lines = []
        street_line = f"{address.street} {address.number}".strip()
        if street_line:
            lines.append(street_line)
        city_line = f"{address.postal_code} {address.city}".strip()
        if city_line:
            lines.append(city_line)
        if address.country:
            lines.append(address.country)
        return "\n".join(lines)

    def _edit_cancel_row(self, on_save) -> Row:
        return Row(
            controls=[
                views.TPrimaryButton(label="Save", on_click=on_save),
                TextButton(
                    "Cancel",
                    on_click=self._cancel_edit,
                    style=ButtonStyle(color=colors.text_muted),
                ),
            ],
            spacing=dimens.SPACE_SM,
        )

    # ── Photo callbacks ───────────────────────────────────────

    def _on_update_photo_clicked(self, e):
        self.pick_file_callback(
            on_file_picker_result=self._on_profile_photo_picked,
            allowed_extensions=["png", "jpeg", "jpg"],
            dialog_title="Tuttle profile photo",
            file_type="custom",
        )

    def _on_profile_photo_picked(self, e):
        if e.files and len(e.files) > 0:
            file = e.files[0]
            upload_url = Path(file.path)
            if upload_url:
                self.uploaded_photo_path = str(upload_url)
                self._save_profile_pic()

    def _save_profile_pic(self):
        if not self.uploaded_photo_path:
            return
        result = self.intent.update_user_photo_path(
            self.user_profile,
            self.uploaded_photo_path,
        )
        msg = result.error_msg
        is_err = True
        if result.was_intent_successful:
            self._photo_img.src_base64 = utils.toBase64(self.uploaded_photo_path)
            self._show_photo(True)
            msg = "Profile photo updated"
            is_err = False
        self.show_snack(msg, is_err)
        if is_err:
            self.user_profile.profile_photo_path = ""
            self._show_photo(False)
        self.uploaded_photo_path = None
        self.update_self()

    # ── Save helper for personal info sections ────────────────

    def _save_user_info(self, **overrides):
        """Save user info, merging overrides with existing user_profile values."""
        user = self.user_profile
        addr = user.address
        kwargs = dict(
            title=user.subtitle,
            name=user.name,
            email=user.email,
            phone=user.phone_number or "",
            street=addr.street if addr else "",
            street_num=addr.number if addr else "",
            postal_code=addr.postal_code if addr else "",
            city=addr.city if addr else "",
            country=addr.country if addr else "",
            website=user.website or "",
            operating_country=user.operating_country or "",
            user=user,
        )
        kwargs.update(overrides)
        result: IntentResult = self.intent.update_user_with_info(**kwargs)
        if result.was_intent_successful:
            self.user_profile = result.data
            self.show_snack("Profile updated")
            self._rebuild_display()
        else:
            self.show_snack(result.error_msg, True)
        self.update_self()

    # ── Edit mode handlers ────────────────────────────────────

    def _edit_contact(self, e):
        user = self.user_profile
        name_f = views.TTextField(label="Name", initial_value=user.name)
        title_f = views.TTextField(label="Job Title", initial_value=user.subtitle)
        email_f = views.TTextField(label="Email", initial_value=user.email)
        phone_f = views.TTextField(label="Phone", initial_value=user.phone_number or "")
        website_f = views.TTextField(label="Website", initial_value=user.website or "")

        def save(e):
            self._save_user_info(
                name=name_f.value,
                title=title_f.value,
                email=email_f.value,
                phone=phone_f.value,
                website=website_f.value,
            )

        self._contact_body.content = Column(
            spacing=dimens.SPACE_SM,
            controls=[
                name_f,
                title_f,
                email_f,
                phone_f,
                website_f,
                views.Spacer(xs_space=True),
                self._edit_cancel_row(save),
            ],
        )
        self.update_self()

    def _edit_address(self, e):
        addr = self.user_profile.address
        street_f = views.TTextField(
            label="Street", initial_value=addr.street if addr else "", expand=1
        )
        number_f = views.TTextField(
            label="Number", initial_value=addr.number if addr else "", expand=1
        )
        postal_f = views.TTextField(
            label="Postal Code",
            initial_value=addr.postal_code if addr else "",
            expand=1,
        )
        city_f = views.TTextField(
            label="City", initial_value=addr.city if addr else "", expand=1
        )
        country_f = views.TTextField(
            label="Country", initial_value=addr.country if addr else ""
        )

        def save(e):
            self._save_user_info(
                street=street_f.value,
                street_num=number_f.value,
                postal_code=postal_f.value,
                city=city_f.value,
                country=country_f.value,
            )

        self._address_body.content = Column(
            spacing=dimens.SPACE_SM,
            controls=[
                Row(controls=[street_f, number_f], spacing=dimens.SPACE_SM),
                Row(controls=[postal_f, city_f], spacing=dimens.SPACE_SM),
                country_f,
                views.Spacer(xs_space=True),
                self._edit_cancel_row(save),
            ],
        )
        self.update_self()

    def _edit_business(self, e):
        country_dd = views.TDropDown(
            label="Operating Country (tax jurisdiction)",
            items=supported_countries(),
            hint="Select country",
        )
        if self.user_profile.operating_country:
            country_dd.update_value(self.user_profile.operating_country)

        def save(e):
            self._save_user_info(
                operating_country=country_dd.value or "",
            )

        self._business_body.content = Column(
            spacing=dimens.SPACE_SM,
            controls=[
                country_dd,
                views.Spacer(xs_space=True),
                self._edit_cancel_row(save),
            ],
        )
        self.update_self()

    def _edit_payment(self, e):
        user = self.user_profile
        ba = user.bank_account
        vat_f = views.TTextField(
            label="VAT Number", initial_value=user.VAT_number or ""
        )
        bank_f = views.TTextField(
            label="Bank Name", initial_value=ba.name if ba else ""
        )
        iban_f = views.TTextField(label="IBAN", initial_value=ba.IBAN if ba else "")
        bic_f = views.TTextField(label="BIC", initial_value=ba.BIC if ba else "")

        def save(e):
            if not user.bank_account:
                user.bank_account = BankAccount(name="", BIC="", IBAN="")
            user.VAT_number = vat_f.value
            user.bank_account.name = bank_f.value
            user.bank_account.IBAN = iban_f.value
            user.bank_account.BIC = bic_f.value
            result: IntentResult = self.intent.update_user(user)
            if result.was_intent_successful:
                self.user_profile = result.data
                self.show_snack("Payment information updated")
                self._rebuild_display()
            else:
                self.show_snack(result.error_msg, True)
            self.update_self()

        self._payment_body.content = Column(
            spacing=dimens.SPACE_SM,
            controls=[
                vat_f,
                views.Spacer(xs_space=True),
                views.TSubHeading("Bank Account"),
                bank_f,
                iban_f,
                bic_f,
                views.Spacer(xs_space=True),
                self._edit_cancel_row(save),
            ],
        )
        self.update_self()

    def _cancel_edit(self, e):
        self._rebuild_display()
        self.update_self()

    # ── Display rebuild ───────────────────────────────────────

    def _rebuild_display(self):
        """Populate all section bodies with read-only content from user_profile."""
        user = self.user_profile
        if not user:
            return

        self._header_name.value = user.name
        self._header_subtitle.value = user.subtitle

        self._contact_body.content = Column(
            spacing=dimens.SPACE_XS,
            controls=[
                self._profile_row("Email", user.email),
                self._profile_row("Phone", user.phone_number),
                self._profile_row("Website", user.website),
            ],
        )

        addr_text = self._format_address(user.address)
        self._address_body.content = Text(
            addr_text or "No address set",
            size=fonts.BODY_1_SIZE,
            color=colors.text_primary if addr_text else colors.text_muted,
        )

        self._business_body.content = Column(
            spacing=dimens.SPACE_XS,
            controls=[
                self._profile_row("Operating Country", user.operating_country),
            ],
        )

        ba = user.bank_account
        self._payment_body.content = Column(
            spacing=dimens.SPACE_XS,
            controls=[
                self._profile_row("VAT Number", user.VAT_number),
                self._profile_row("Bank", ba.name if ba else ""),
                self._profile_row("IBAN", ba.IBAN if ba else ""),
                self._profile_row("BIC", ba.BIC if ba else ""),
            ],
        )

    # ── Build / lifecycle ─────────────────────────────────────

    def _build_avatar(self) -> Container:
        """80px circular avatar with icon fallback when no photo is set."""
        self._photo_img = views.TProfilePhotoImg()
        self._photo_img.width = 80
        self._photo_img.height = 80
        self._photo_img.border_radius = BorderRadius.all(40)
        self._photo_img.visible = False

        self._avatar_placeholder = Container(
            width=80,
            height=80,
            border_radius=BorderRadius.all(40),
            bgcolor=colors.bg_surface,
            content=Column(
                controls=[Icon(Icons.PERSON, size=36, color=colors.text_muted)],
                alignment=MainAxisAlignment.CENTER,
                horizontal_alignment=CrossAxisAlignment.CENTER,
                expand=True,
            ),
        )

        self._avatar_stack = Container(
            width=80,
            height=80,
            content=self._avatar_placeholder,
        )
        return self._avatar_stack

    def _show_photo(self, has_photo: bool):
        """Toggle between photo image and placeholder icon."""
        if has_photo:
            self._avatar_stack.content = self._photo_img
            self._photo_img.visible = True
        else:
            self._avatar_stack.content = self._avatar_placeholder

    def build(self):
        avatar = self._build_avatar()

        self._header_name = Text(
            "",
            size=fonts.HEADLING_1_SIZE,
            color=colors.text_primary,
            weight=fonts.BOLD_FONT,
        )
        self._header_subtitle = Text(
            "",
            size=fonts.SUBTITLE_1_SIZE,
            color=colors.text_secondary,
        )

        self._contact_body = Container()
        self._address_body = Container()
        self._business_body = Container()
        self._payment_body = Container()

        self.expand = True
        self.scroll = ScrollMode.AUTO
        self.spacing = 0
        self.controls = [
            views.Spacer(sm_space=True),
            # ── Header ────────────────────────────────────────
            Row(
                controls=[
                    avatar,
                    Column(
                        controls=[self._header_name, self._header_subtitle],
                        spacing=dimens.SPACE_XXS,
                        expand=True,
                    ),
                    TextButton(
                        "Change Photo",
                        on_click=self._on_update_photo_clicked,
                        style=ButtonStyle(color=colors.accent),
                    ),
                ],
                vertical_alignment=CrossAxisAlignment.CENTER,
                spacing=dimens.SPACE_LG,
            ),
            views.Spacer(lg_space=True),
            self._section_divider(),
            views.Spacer(lg_space=True),
            # ── Contact ───────────────────────────────────────
            self._section_header("Contact", on_edit=self._edit_contact),
            views.Spacer(sm_space=True),
            self._contact_body,
            views.Spacer(lg_space=True),
            self._section_divider(),
            views.Spacer(lg_space=True),
            # ── Address ───────────────────────────────────────
            self._section_header("Address", on_edit=self._edit_address),
            views.Spacer(sm_space=True),
            self._address_body,
            views.Spacer(lg_space=True),
            self._section_divider(),
            views.Spacer(lg_space=True),
            # ── Business ──────────────────────────────────────
            self._section_header("Business", on_edit=self._edit_business),
            views.Spacer(sm_space=True),
            self._business_body,
            views.Spacer(lg_space=True),
            self._section_divider(),
            views.Spacer(lg_space=True),
            # ── Payment ───────────────────────────────────────
            self._section_header("Payment", on_edit=self._edit_payment),
            views.Spacer(sm_space=True),
            self._payment_body,
            views.Spacer(lg_space=True),
        ]

    def did_mount(self):
        self.mounted = True
        result: IntentResult = self.intent.get_user_if_exists()
        if not result.was_intent_successful:
            self.show_snack(result.error_msg, True)
        else:
            self.user_profile = result.data
            has_photo = bool(self.user_profile.profile_photo_path)
            if has_photo:
                self._photo_img.src_base64 = utils.toBase64(
                    self.user_profile.profile_photo_path
                )
            self._show_photo(has_photo)
            self._rebuild_display()
        self.update_self()

    def will_unmount(self):
        self.mounted = False
