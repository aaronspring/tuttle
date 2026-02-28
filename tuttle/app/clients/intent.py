from ..contacts.intent import ContactsIntent
from ..core.abstractions import CrudIntent
from ..core.intent_result import IntentResult
from ...model import Client


class ClientsIntent(CrudIntent):
    """Client CRUD with validation."""

    entity_type = Client
    entity_name = "client"
    deletion_guards = [
        ("contracts", "contracts", lambda c: c.title),
    ]

    def __init__(self):
        super().__init__()
        self._contacts_intent = ContactsIntent()

    def get_all_contacts_as_map(self):
        """Delegate to ContactsIntent for cross-entity lookup."""
        return self._contacts_intent.get_all_as_map()

    def save_client(self, client: Client) -> IntentResult:
        """Validate and save a client."""
        if not client.name:
            return IntentResult(
                was_intent_successful=False,
                error_msg="Please provide the client's name",
            )
        if (
            not client.invoicing_contact.first_name
            or not client.invoicing_contact.last_name
        ):
            return IntentResult(
                was_intent_successful=False,
                error_msg="A contact name is required.",
            )
        if client.invoicing_contact.address.is_empty:
            return IntentResult(
                was_intent_successful=False,
                error_msg="Please specify the contact address.",
            )
        return self.save(client)
