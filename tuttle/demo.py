from typing import Callable, List, Optional

import datetime
import random
from datetime import date, timedelta
from pathlib import Path
from decimal import Decimal

import faker
import ics
import numpy
import sqlalchemy
from loguru import logger
from sqlmodel import Field, Session, SQLModel, create_engine, select

from tuttle import rendering
from tuttle.calendar import Calendar, ICSCalendar
from tuttle.migrations.run import run_migrations
from tuttle.model import (
    Address,
    BankAccount,
    Client,
    Contact,
    Contract,
    Cycle,
    FinancialGoal,
    Invoice,
    InvoiceItem,
    Timesheet,
    TimeTrackingItem,
    Project,
    TimeUnit,
    User,
)


# ---------------------------------------------------------------------------
# Curated heating-repair domain data
# ---------------------------------------------------------------------------

_HEATING_CLIENTS = [
    ("Warmwasser Hausverwaltung GmbH", "Property management"),
    ("Centralheating AG", "Heating systems supplier"),
    ("Altbau Wohnungsbau e.G.", "Housing cooperative"),
    ("Stadtwerke Metropolis", "Municipal utilities"),
]

_HEATING_CONTRACTS = [
    "Annual heating maintenance",
    "Boiler service agreement",
    "Emergency repair retainer",
    "Heating system modernisation",
]

_HEATING_PROJECTS = [
    (
        "Boiler replacement Marienstr. 12",
        "Replace ageing gas boiler with modern condensing unit",
    ),
    (
        "Annual inspection Q1",
        "Scheduled safety and efficiency inspection for all units",
    ),
    (
        "Emergency pipe repair Nordblock",
        "Fix burst heating pipe in basement utility room",
    ),
    (
        "Radiator upgrade Westflügel",
        "Swap cast-iron radiators for energy-efficient panel radiators",
    ),
]

_HEATING_TASKS = [
    "Thermostat calibration",
    "Radiator bleeding",
    "Boiler diagnostics",
    "Pump pressure test",
    "Flue gas analysis",
    "Pipe insulation check",
    "Expansion vessel service",
    "Control panel firmware update",
    "Heat exchanger cleaning",
    "Safety valve inspection",
]

_HEATING_INVOICE_ITEMS = [
    ("Labor: boiler service", "hours"),
    ("Replacement valve DN20", "hours"),
    ("Thermostat head Danfoss RA-N", "hours"),
    ("Circulation pump Grundfos UPS", "hours"),
    ("Pipe insulation material", "hours"),
    ("Flue gas measurement", "hours"),
    ("Emergency callout surcharge", "hours"),
    ("Travel to site", "hours"),
]


def create_fake_user(
    fake: faker.Faker,
) -> User:
    """Create a fake user."""
    user = User(
        name=fake.name(),
        email=fake.email(),
        subtitle=fake.job(),
        VAT_number=fake.ean8(),
    )
    return user


def create_fake_contact(
    fake: faker.Faker,
) -> Contact:
    split_address_lines = fake.address().splitlines()
    street_line = split_address_lines[0]
    city_line = split_address_lines[1]
    try:
        street = street_line.split(" ", 1)[0]
        number = street_line.split(" ", 1)[1]
        city = city_line.split(" ")[1]
        postal_code = city_line.split(" ")[0]
    except IndexError:
        street = street_line
        number = ""
        city = city_line
        postal_code = ""
    a = Address(
        street=street,
        number=number,
        city=city,
        postal_code=postal_code,
        country=fake.country(),
    )
    first_name, last_name = fake.name().split(" ", 1)
    contact = Contact(
        first_name=first_name,
        last_name=last_name,
        email=fake.email(),
        company=fake.company(),
        address_id=a.id,
        address=a,
    )
    return contact


def create_heating_contact(fake: faker.Faker, company_name: str) -> Contact:
    """Create a contact for a heating-industry client."""
    a = Address(
        street=fake.street_name(),
        number=str(fake.random_int(1, 200)),
        city=fake.city(),
        postal_code=fake.postcode(),
        country="Germany",
    )
    first_name, last_name = fake.name().split(" ", 1)
    return Contact(
        first_name=first_name,
        last_name=last_name,
        email=fake.email(),
        company=company_name,
        address=a,
    )


def create_fake_client(
    fake: faker.Faker,
    invoicing_contact: Optional[Contact] = None,
) -> Client:
    if invoicing_contact is None:
        invoicing_contact = create_fake_contact(fake)
    client = Client(
        name=fake.company(),
        invoicing_contact=invoicing_contact,
    )
    assert client.invoicing_contact is not None
    return client


def create_fake_contract(
    fake: faker.Faker,
    client: Optional[Client] = None,
) -> Contract:
    """Create a fake contract for the given client."""
    if client is None:
        client = create_fake_client(fake)
    unit = random.choice(list(TimeUnit))
    if unit == TimeUnit.day:
        rate = fake.random_int(200, 1000)
    elif unit == TimeUnit.hour:
        rate = fake.random_int(10, 100)
    else:
        rate = fake.random_int(1, 1000)
    return Contract(
        title=f"{client.name} service contract",
        client=client,
        signature_date=fake.date_this_year(before_today=True),
        start_date=fake.date_this_year(after_today=True),
        rate=rate,
        currency="EUR",
        VAT_rate=Decimal(round(random.uniform(0.05, 0.2), 2)),
        unit=unit,
        units_per_workday=random.randint(1, 12),
        volume=fake.random_int(1, 1000),
        term_of_payment=fake.random_int(1, 31),
        billing_cycle=random.choice([Cycle.weekly, Cycle.monthly, Cycle.quarterly]),
    )


def create_fake_project(
    fake: faker.Faker,
    contract: Optional[Contract] = None,
) -> Project:
    if contract is None:
        contract = create_fake_contract(fake)

    project_title = fake.bs().replace("/", "-")
    project_tag = f"#{'-'.join(project_title.split(' ')[:2]).lower()}"

    project = Project(
        title=project_title,
        tag=project_tag,
        description=fake.paragraph(nb_sentences=2),
        is_completed=fake.pybool(),
        start_date=datetime.date.today(),
        end_date=datetime.date.today() + datetime.timedelta(days=80),
        contract=contract,
    )
    return project


def invoice_number_counting():
    count = 0
    while True:
        count += 1
        yield count


invoice_number_counter = invoice_number_counting()


def create_fake_timesheet(
    fake: faker.Faker,
    project: Optional[Project] = None,
) -> Timesheet:
    """
    Create a fake timesheet object with random values.

    Args:
    project (Project): The project associated with the timesheet.
    fake (faker.Faker): An instance of the Faker class to generate random values.

    Returns:
    Timesheet: A fake timesheet object.
    """
    if project is None:
        project = create_fake_project(fake)
    timesheet = Timesheet(
        title=f"Timesheet – {project.title}",
        comment=f"Work log for {project.title}",
        date=datetime.date.today(),
        period_start=datetime.date.today() - datetime.timedelta(days=30),
        period_end=datetime.date.today(),
        project=project,
    )
    number_of_items = fake.random_int(min=2, max=5)
    for _ in range(number_of_items):
        task = random.choice(_HEATING_TASKS)
        hours = fake.random_int(min=1, max=8)
        begin = fake.date_time_this_year(before_now=True, after_now=False)
        time_tracking_item = TimeTrackingItem(
            timesheet=timesheet,
            begin=begin,
            end=begin + datetime.timedelta(hours=hours),
            duration=datetime.timedelta(hours=hours),
            title=f"{task} {project.tag}",
            tag=project.tag,
            description=task,
        )
        timesheet.items.append(time_tracking_item)
    return timesheet


def create_fake_invoice(
    fake: faker.Faker,
    project: Optional[Project] = None,
    user: Optional[User] = None,
    render: bool = True,
    invoice_date: Optional[date] = None,
    paid: Optional[bool] = None,
    sent: Optional[bool] = None,
    cancelled: bool = False,
) -> Invoice:
    """
    Create a fake invoice object with random values.

    Args:
    project (Project): The project associated with the invoice.
    fake (faker.Faker): An instance of the Faker class to generate random values.
    invoice_date: The date for the invoice. Defaults to today.
    paid: Whether the invoice is paid. Random if None.
    sent: Whether the invoice was sent. Random if None.
    cancelled: Whether the invoice is cancelled.

    Returns:
    Invoice: A fake invoice object.
    """
    if project is None:
        project = create_fake_project(fake)

    if user is None:
        user = create_fake_user(fake)

    inv_date = invoice_date or datetime.date.today()
    invoice_number = f"{inv_date.strftime('%Y-%m-%d')}-{next(invoice_number_counter)}"
    invoice = Invoice(
        number=invoice_number,
        date=inv_date,
        sent=sent if sent is not None else fake.pybool(),
        paid=paid if paid is not None else fake.pybool(),
        cancelled=cancelled,
        contract=project.contract,
        project=project,
        rendered=render,
    )
    number_of_items = fake.random_int(min=1, max=4)
    used_items = random.sample(
        _HEATING_INVOICE_ITEMS,
        k=min(number_of_items, len(_HEATING_INVOICE_ITEMS)),
    )
    for desc, unit in used_items:
        unit_price = abs(round(numpy.random.normal(75, 20), 2))
        invoice_item = InvoiceItem(
            start_date=fake.date_this_year(before_today=True),
            end_date=fake.date_this_year(before_today=True),
            quantity=fake.random_int(min=1, max=8),
            unit=unit,
            unit_price=Decimal(unit_price),
            description=desc,
            VAT_rate=Decimal("0.19"),
            invoice=invoice,
        )

    # an invoice is created together with a timesheet. For the sake of simplicity, timesheet and invoice items are not linked.
    timesheet = create_fake_timesheet(fake, project)
    # attach timesheet to invoice
    timesheet.invoice = invoice
    assert len(invoice.timesheets) == 1

    if render:
        # render invoice
        try:
            rendering.render_invoice(
                user=user,
                invoice=invoice,
                out_dir=Path.home() / ".tuttle" / "Invoices",
                only_final=True,
            )
            logger.info(f"✅ rendered invoice for {project.title}")
        except Exception as ex:
            logger.error(f"❌ Error rendering invoice for {project.title}: {ex}")
            logger.exception(ex)
        # render timesheet
        try:
            rendering.render_timesheet(
                user=user,
                timesheet=timesheet,
                out_dir=Path.home() / ".tuttle" / "Timesheets",
                only_final=True,
            )
            logger.info(f"✅ rendered timesheet for {project.title}")
        except Exception as ex:
            logger.error(f"❌ Error rendering timesheet for {project.title}: {ex}")
            logger.exception(ex)

    return invoice


def create_heating_data(
    user: User,
    n: int = 4,
):
    """Create heating-repair themed demo data for Harry Tuttle."""
    fake = faker.Faker(locale=["de_DE", "en_US"])

    n = min(n, len(_HEATING_CLIENTS))
    contacts = []
    clients = []
    for i in range(n):
        name, _desc = _HEATING_CLIENTS[i]
        contact = create_heating_contact(fake, company_name=name)
        contacts.append(contact)
        client = Client(name=name, invoicing_contact=contact)
        clients.append(client)

    contracts = []
    for i, client in enumerate(clients):
        title = _HEATING_CONTRACTS[i % len(_HEATING_CONTRACTS)]
        rate = random.choice([65, 72, 80, 85, 95])
        contract = Contract(
            title=f"{title} – {client.name}",
            client=client,
            signature_date=fake.date_between(start_date="-1y", end_date="-3M"),
            start_date=fake.date_between(start_date="-3M", end_date="today"),
            rate=rate,
            currency="EUR",
            VAT_rate=Decimal("0.19"),
            unit=TimeUnit.hour,
            units_per_workday=8,
            volume=random.randint(100, 400),
            term_of_payment=14,
            billing_cycle=Cycle.monthly,
        )
        contracts.append(contract)

    projects = []
    for i, contract in enumerate(contracts):
        title, description = _HEATING_PROJECTS[i % len(_HEATING_PROJECTS)]
        tag = f"#{''.join(title.split()[:2]).lower()}"
        project = Project(
            title=title,
            tag=tag,
            description=description,
            is_completed=False,
            start_date=contract.start_date,
            end_date=contract.start_date + datetime.timedelta(days=90),
            contract=contract,
        )
        projects.append(project)

    invoices = [
        create_fake_invoice(fake, project=project, user=user) for project in projects
    ]
    return projects, invoices


def create_fake_data(
    user: User,
    n: int = 10,
):
    """Legacy entry point — delegates to heating-themed generator."""
    return create_heating_data(user, n=n)


def create_historical_invoices(
    fake: faker.Faker,
    projects: List[Project],
    user: User,
    n_months: int = 11,
) -> List[Invoice]:
    """Create invoices spread across the past n_months for dashboard history."""
    today = datetime.date.today()
    invoices = []
    for months_ago in range(n_months, 0, -1):
        # First day of that month
        inv_date = (today - timedelta(days=30 * months_ago)).replace(day=15)
        # Pick 1-2 random projects to invoice each month
        month_projects = random.sample(
            projects, k=min(random.randint(1, 2), len(projects))
        )
        for project in month_projects:
            inv = create_fake_invoice(
                fake,
                project=project,
                user=user,
                render=True,
                invoice_date=inv_date,
                paid=True,
                sent=True,
                cancelled=False,
            )
            invoices.append(inv)
    return invoices


def create_demo_user() -> User:
    user = User(
        name="Harry Tuttle",
        subtitle="Heating Engineer",
        website="https://tuttle-dev.github.io/tuttle/",
        email="mail@tuttle.com",
        phone_number="+55555555555",
        VAT_number="27B-6",
        address=Address(
            street="Main Street",
            number="450",
            city="Somewhere",
            postal_code="555555",
            country="Brazil",
        ),
        bank_account=BankAccount(
            name="Giro",
            IBAN="BZ99830994950003161565",
            BIC="BANKINFO101",
        ),
    )
    return user


def create_fake_calendar(project_list: List[Project]) -> ics.Calendar:
    def random_datetime(start, end):
        return start + timedelta(
            seconds=random.randint(0, int((end - start).total_seconds()))
        )

    def random_duration():
        return timedelta(hours=random.randint(1, 8))

    # create a new calendar
    calendar = ics.Calendar()

    # get the last month's date range
    # get todays date
    now = datetime.datetime.now()
    month_ago = now - timedelta(days=30)

    # populate the calendar with events
    for project in project_list:
        # create 1-5 events for each project
        for _ in range(random.randint(1, 5)):
            # create a new event
            event = ics.Event()
            event.name = f"Meeting for {project.tag}"

            # set the event's begin and end datetime
            event.begin = random_datetime(month_ago, now)
            event.end = event.begin + random_duration()

            # add to calendar.events
            calendar.events.add(event)
    return calendar


def install_demo_data(
    n_projects: int,
    db_path: str,
    on_cache_timetracking_dataframe: Optional[Callable] = None,
):
    """
    Install demo data in the database.

    Args:
    n_projects (int): The number of projects to create.
    db_path (str): The path to the database.
    on_cache_timetracking_dataframe (Optional[Callable], optional): A callback function to be called when the timetracking dataframe is cached. Defaults to None.
    """
    db_url = f"""sqlite:///{db_path}"""
    logger.info(f"Installing demo data in {db_url}...")
    logger.info(f"Creating database engine at: {db_url}...")
    db_engine = create_engine(db_url)
    logger.info("Creating database tables via migrations...")
    run_migrations(db_url)

    logger.info("Creating demo user...")
    with Session(db_engine) as session:
        user = create_demo_user()
        session.add(user)
        session.commit()
        session.refresh(user)

    logger.info(f"Creating {n_projects} fake projects...")
    projects, invoices = create_fake_data(user, n_projects)

    # create a fake calendar and add time tracking data from it
    logger.info("Creating a fake calendar...")
    calendar: Calendar = ICSCalendar(
        name="Demo calendar",
        ics_calendar=create_fake_calendar(project_list=projects),
    )
    time_tracking_data = calendar.to_data()
    logger.info("Caching timetracking data")
    on_cache_timetracking_dataframe(time_tracking_data)
    logger.info("Demo data installed.")

    # add fake invoices
    logger.info("Adding fake invoices...")
    with Session(db_engine) as session:
        for invoice in invoices:
            session.add(invoice)
        session.commit()

        # add historical invoices in the same session so relationships resolve
        logger.info("Adding historical invoices...")
        locales = ["de_DE", "en_US", "en_GB", "fr_FR"]
        fake = faker.Faker(locale=locales)
        historical_invoices = create_historical_invoices(
            fake, projects, user, n_months=11
        )
        for invoice in historical_invoices:
            session.add(invoice)
        session.commit()

        # add projects in the same session
        logger.info("Adding fake projects...")
        for project in projects:
            session.merge(project)
        session.commit()

    logger.info("Adding financial goals...")
    with Session(db_engine) as session:
        today = datetime.date.today()
        goals = [
            FinancialGoal(
                title="Service van replacement fund",
                target_amount=Decimal("35000.00"),
                target_date=today.replace(year=today.year + 1, month=3, day=31),
            ),
            FinancialGoal(
                title="Workshop tool upgrade",
                target_amount=Decimal("8000.00"),
                target_date=today.replace(month=12, day=31),
            ),
        ]
        for goal in goals:
            session.add(goal)
        session.commit()
