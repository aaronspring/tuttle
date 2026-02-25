from typing import Optional

from ..clients.intent import ClientsIntent
from ..contracts.intent import ContractsIntent
from ..core.intent_result import IntentResult
from ..core.abstractions import CrudIntent

from ...model import Project


class ProjectsIntent(CrudIntent):
    """Handles intents related to the projects data UI."""

    entity_type = Project

    def __init__(self):
        super().__init__()
        self._clients_intent = ClientsIntent()
        self._contracts_intent = ContractsIntent()

    # -- Cross-entity delegates ------------------------------------------------

    def get_all_clients_as_map(self):
        return self._clients_intent.get_all_as_map()

    def get_all_contracts_as_map(self):
        return self._contracts_intent.get_all_as_map()

    # -- Project-specific logic ------------------------------------------------

    def save_project(self, project: Project) -> IntentResult[Optional[Project]]:
        """Validate and save a project."""
        is_updating = project.id is not None
        result = self.save(project)
        if not result.was_intent_successful:
            if is_updating:
                old = self.get_by_id(project.id)
                result.data = old.data if old.was_intent_successful else None
            result.error_msg = "Failed to save the project."
            result.log_message_if_any()
        return result

    def toggle_project_completed_status(
        self, project: Project
    ) -> IntentResult[Project]:
        """Updates the project completed status."""
        return self.toggle_completed(project)
