from ..core.abstractions import CrudIntent
from ..core.intent_result import IntentResult
from ...model import Contact


class ContactsIntent(CrudIntent):
    """Contact CRUD with validation and referential integrity."""

    entity_type = Contact
    entity_name = "contact"
    deletion_guards = [
        ("invoicing_contact_of", "clients", lambda c: c.name),
    ]

    def save_contact(self, contact: Contact) -> IntentResult:
        """Validate and save a contact."""
        if not contact.first_name or not contact.last_name:
            return IntentResult(
                was_intent_successful=False,
                error_msg="Saving contact failed. A name is required.",
            )
        if contact.address.is_empty:
            return IntentResult(
                was_intent_successful=False,
                error_msg="Saving contact failed. Please specify the address.",
            )
        return self.save(contact)

    def delete_contact(self, contact_id) -> IntentResult:
        """Alias kept for backward compatibility."""
        return self.delete(contact_id)
