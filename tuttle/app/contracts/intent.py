from ..clients.intent import ClientsIntent
from ..contacts.intent import ContactsIntent
from ..core.abstractions import CrudIntent
from ..core.intent_result import IntentResult

from ...model import Client, Contract, User
from ...tax import get_tax_system


class ContractsIntent(CrudIntent):
    """Handles Contract CRUD intents."""

    entity_type = Contract
    deletion_guards = [
        ("projects", "projects", lambda p: p.title),
        ("invoices", "invoices", lambda i: i.number or f"#{i.id}"),
    ]

    def __init__(self):
        super().__init__()
        self._clients_intent = ClientsIntent()
        self._contacts_intent = ContactsIntent()

    # -- Cross-entity delegates ------------------------------------------------

    def get_all_clients_as_map(self):
        return self._clients_intent.get_all_as_map()

    def get_all_contacts_as_map(self):
        return self._contacts_intent.get_all_as_map()

    def save_client(self, client: Client) -> IntentResult:
        return self._clients_intent.save_client(client=client)

    def get_default_currency(self) -> IntentResult:
        """Derive default contract currency from the user's operating country."""
        try:
            users = self.query(User)
            country = users[0].operating_country if users else "Germany"
            ts = get_tax_system(country)
            return IntentResult(was_intent_successful=True, data=ts.currency)
        except Exception as e:
            return IntentResult(was_intent_successful=True, data="EUR")

    # -- Contract-specific logic -----------------------------------------------

    def save_contract(self, contract: Contract) -> IntentResult:
        """Validate and save a contract."""
        is_updating = contract.id is not None
        result = self.save(contract)
        if not result.was_intent_successful and is_updating:
            old = self.get_by_id(contract.id)
            result.data = old.data if old.was_intent_successful else None
            result.error_msg = "Failed to save the contract. Verify the info and retry."
            result.log_message_if_any()
        return result

    def toggle_complete_status(self, contract: Contract) -> IntentResult[Contract]:
        """Toggles the completed status of the contract."""
        return self.toggle_completed(contract)
