"""LLM configuration and document parsing."""

import tuttle.llm as _llm

from ..core.intent_result import IntentResult


class LlmIntent:
    def get_config(self) -> IntentResult:
        return IntentResult(
            was_intent_successful=True,
            data=_llm.load_config(),
        )

    def save_config(self, config: dict) -> IntentResult:
        saved = _llm.save_config(_llm.LLMConfig(**config))
        return IntentResult(was_intent_successful=True, data=saved)

    def get_models(self, base_url: str = "http://localhost:11434") -> IntentResult:
        return IntentResult(
            was_intent_successful=True,
            data=_llm.get_available_models(base_url),
        )

    def parse_document(
        self,
        file_base64: str,
        file_name: str,
        entity_type: str = "contact",
    ) -> IntentResult:
        items = _llm.parse_document(
            file_base64,
            file_name,
            entity_type,
            _llm.load_config(),
        )
        return IntentResult(was_intent_successful=True, data=items)

    def parse_contract_document(
        self,
        file_base64: str,
        file_name: str,
    ) -> IntentResult:
        result = _llm.parse_contract_document(
            file_base64,
            file_name,
            _llm.load_config(),
        )
        return IntentResult(was_intent_successful=True, data=result)
