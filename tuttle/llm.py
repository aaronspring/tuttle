"""LLM integration for AI-powered document processing.

Provides configuration management, Ollama model discovery, and
structured entity extraction from documents using llama_index.
"""

import base64
import json
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, Field
from loguru import logger


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: str = Field(
        default="ollama", description="LLM provider: ollama or anthropic"
    )
    base_url: str = Field(
        default="http://localhost:11434", description="Base URL for Ollama API"
    )
    model: str = Field(default="", description="Selected model name")
    api_key: str = Field(
        default="", description="API key (for Anthropic or other hosted providers)"
    )
    request_timeout: float = Field(
        default=600.0, description="LLM request timeout in seconds"
    )


def load_config() -> LLMConfig:
    """Load LLM config from the centralized app.db."""
    from tuttle.app_db import AppDatabase

    db = AppDatabase()
    data = db.get_llm_config()
    return LLMConfig(**data)


def save_config(config: LLMConfig) -> LLMConfig:
    """Persist LLM config to the centralized app.db."""
    from tuttle.app_db import AppDatabase

    db = AppDatabase()
    db.save_llm_config(config.model_dump())
    return config


# ---------------------------------------------------------------------------
# Model discovery
# ---------------------------------------------------------------------------


def get_available_models(base_url: str) -> List[str]:
    """Fetch available model names from an Ollama instance."""
    url = f"{base_url.rstrip('/')}/api/tags"
    try:
        resp = httpx.get(url, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        models = data.get("models", [])
        return [m["name"] for m in models if "name" in m]
    except Exception as e:
        logger.error(f"Failed to fetch models from {url}: {e}")
        raise RuntimeError(f"Could not connect to Ollama at {base_url}: {e}")


# ---------------------------------------------------------------------------
# Document text extraction
# ---------------------------------------------------------------------------


def _extract_text(file_bytes: bytes, file_name: str) -> str:
    """Extract plain text from a file (PDF or text-based)."""
    lower = file_name.lower()
    if lower.endswith(".pdf"):
        import pymupdf

        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
        pages = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        return "\n".join(pages)
    else:
        return file_bytes.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Extraction schemas — flat projections of SQLModel classes (no relationships)
# ---------------------------------------------------------------------------

from pydantic import create_model as _create_model

from tuttle.model import Contact, Address, Client, Contract, Project


def _flat_schema(model_cls: type, *, include: Optional[List[str]] = None) -> type:
    """Derive a flat Pydantic BaseModel from a SQLModel class.

    Uses model_fields (which already excludes relationships) and keeps only
    scalar columns. All fields made Optional for partial extraction.
    """
    fields: Dict[str, Any] = {}
    for name in model_cls.model_fields:
        if name == "id" or name.endswith("_id"):
            continue
        if include and name not in include:
            continue
        annotation = model_cls.__annotations__.get(name)
        if annotation is None:
            continue
        fields[name] = (Optional[annotation], None)

    return _create_model(f"{model_cls.__name__}Extract", **fields)


_AddressExtract = _flat_schema(Address)


class _ContactExtract(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    address: Optional[_AddressExtract] = None  # type: ignore[valid-type]


_ClientExtract = _flat_schema(Client, include=["name"])
_ContractExtract = _flat_schema(
    Contract,
    include=[
        "title",
        "rate",
        "currency",
        "unit",
        "billing_cycle",
        "volume",
        "signature_date",
        "start_date",
        "end_date",
        "VAT_rate",
        "term_of_payment",
    ],
)
_ProjectExtract = _flat_schema(
    Project,
    include=["title", "tag", "description", "start_date", "end_date"],
)


class ContactExtractionResult(BaseModel):
    items: List[_ContactExtract]  # type: ignore[valid-type]


class ClientExtractionResult(BaseModel):
    class _Item(BaseModel):
        client: _ClientExtract  # type: ignore[valid-type]
        contact_name_hint: Optional[str] = Field(
            default=None,
            description="Name of the invoicing contact person (for user to link)",
        )

    items: List[_Item]


class ContractExtractionResult(BaseModel):
    class _Item(BaseModel):
        contract: _ContractExtract  # type: ignore[valid-type]
        client_name_hint: Optional[str] = Field(
            default=None,
            description="Name of the client this contract belongs to (for user to link)",
        )

    items: List[_Item]


class ProjectExtractionResult(BaseModel):
    class _Item(BaseModel):
        project: _ProjectExtract  # type: ignore[valid-type]
        contract_title_hint: Optional[str] = Field(
            default=None,
            description="Title of the contract this project belongs to (for user to link)",
        )

    items: List[_Item]


# ---------------------------------------------------------------------------
# LLM instantiation
# ---------------------------------------------------------------------------


def _get_llm(config: LLMConfig):
    """Instantiate a llama_index LLM from config."""
    if config.provider == "ollama":
        from llama_index.llms.ollama import Ollama

        return Ollama(
            model=config.model,
            base_url=config.base_url,
            request_timeout=config.request_timeout,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {config.provider}")


# ---------------------------------------------------------------------------
# Prompts per entity type
# ---------------------------------------------------------------------------

_PROMPTS = {
    "contact": (
        "Extract all contact information (people or companies) from the following document. "
        "For each contact, extract: first_name, last_name, company, email. "
        "If a field is not present in the document, leave it as null.\n\n"
    ),
    "client": (
        "Extract all client/company entities from the following document. "
        "For each client, extract the company or client name. "
        "If there's a contact person mentioned for a client, include their name as contact_name_hint. "
        "If a field is not present, leave it as null.\n\n"
    ),
    "contract": (
        "Extract all contracts or service agreements from the following document. "
        "For each contract, extract: title, rate, currency, unit (hour/day), billing_cycle (monthly/quarterly/yearly), "
        "volume, signature_date, start_date, end_date, VAT_rate, term_of_payment. "
        "If the client name is mentioned, include it as client_name_hint. "
        "Dates should be in YYYY-MM-DD format. If a field is not present, leave it as null.\n\n"
    ),
    "project": (
        "Extract all project descriptions from the following document. "
        "For each project, extract: title, tag (starting with #), description, start_date, end_date. "
        "If the contract title is mentioned, include it as contract_title_hint. "
        "Dates should be in YYYY-MM-DD format. If a field is not present, leave it as null.\n\n"
    ),
}

_OUTPUT_CLASSES = {
    "contact": ContactExtractionResult,
    "client": ClientExtractionResult,
    "contract": ContractExtractionResult,
    "project": ProjectExtractionResult,
}


# ---------------------------------------------------------------------------
# Generic document parsing
# ---------------------------------------------------------------------------


def parse_document(
    file_base64: str,
    file_name: str,
    entity_type: str,
    config: Optional[LLMConfig] = None,
) -> List[Dict[str, Any]]:
    """Parse entities from a document using an LLM.

    Args:
        file_base64: Base64-encoded file content.
        file_name: Original file name (for type detection).
        entity_type: One of "contact", "client", "contract", "project".
        config: LLM configuration. Loads from disk if None.

    Returns:
        List of dicts shaped for the corresponding *.save RPC endpoint.
    """
    if config is None:
        config = load_config()

    if not config.model:
        raise ValueError("No LLM model configured. Please set up an LLM in Settings.")

    if entity_type not in _OUTPUT_CLASSES:
        raise ValueError(f"Unsupported entity_type: {entity_type}")

    file_bytes = base64.b64decode(file_base64)
    text = _extract_text(file_bytes, file_name)

    if not text.strip():
        raise ValueError("Document appears to be empty or could not be read.")

    llm = _get_llm(config)
    output_cls = _OUTPUT_CLASSES[entity_type]
    sllm = llm.as_structured_llm(output_cls=output_cls)

    prompt = (
        _PROMPTS[entity_type]
        + "--- DOCUMENT START ---\n"
        + text
        + "\n--- DOCUMENT END ---"
    )

    response = sllm.complete(prompt)
    extracted = response.raw

    if entity_type == "contact":
        return _map_contacts(extracted)
    elif entity_type == "client":
        return _map_clients(extracted)
    elif entity_type == "contract":
        return _map_contracts(extracted)
    elif entity_type == "project":
        return _map_projects(extracted)

    return []


# ---------------------------------------------------------------------------
# Result mappers: convert extraction results to RPC-ready dicts
# ---------------------------------------------------------------------------


def _serialise_date(d) -> str:
    """Coerce date-like values to ISO string."""
    if d is None:
        return ""
    if hasattr(d, "isoformat"):
        return d.isoformat()
    return str(d)


def _map_contacts(result: ContactExtractionResult) -> List[Dict[str, Any]]:
    """Map extracted Contact objects to dicts shaped for contacts.save."""
    results = []
    for c in result.items:
        addr = {}
        if c.address:
            addr = {
                "street": getattr(c.address, "street", "") or "",
                "number": getattr(c.address, "number", "") or "",
                "city": getattr(c.address, "city", "") or "",
                "postal_code": getattr(c.address, "postal_code", "") or "",
                "country": getattr(c.address, "country", "") or "",
            }
        d = {
            "first_name": c.first_name or "",
            "last_name": c.last_name or "",
            "company": c.company or "",
            "email": c.email or "",
            "address": addr,
        }
        results.append(d)
    return results


def _map_clients(result: ClientExtractionResult) -> List[Dict[str, Any]]:
    """Map extracted Client objects to dicts shaped for clients.save."""
    results = []
    for item in result.items:
        d = {"name": getattr(item.client, "name", "") or ""}
        d["contact_name_hint"] = item.contact_name_hint or ""
        results.append(d)
    return results


def _map_contracts(result: ContractExtractionResult) -> List[Dict[str, Any]]:
    """Map extracted Contract objects to dicts for contracts.save."""
    results = []
    for item in result.items:
        c = item.contract
        unit = getattr(c, "unit", None)
        billing_cycle = getattr(c, "billing_cycle", None)
        rate = getattr(c, "rate", None)
        vat = getattr(c, "VAT_rate", None)
        results.append(
            {
                "title": getattr(c, "title", "") or "",
                "rate": float(rate) if rate is not None else None,
                "currency": getattr(c, "currency", "") or "",
                "unit": unit.value if unit else "",
                "billing_cycle": billing_cycle.value if billing_cycle else "",
                "volume": getattr(c, "volume", None),
                "signature_date": _serialise_date(getattr(c, "signature_date", None)),
                "start_date": _serialise_date(getattr(c, "start_date", None)),
                "end_date": _serialise_date(getattr(c, "end_date", None)),
                "VAT_rate": float(vat) if vat is not None else None,
                "term_of_payment": getattr(c, "term_of_payment", None),
                "client_name_hint": item.client_name_hint or "",
            }
        )
    return results


def _map_projects(result: ProjectExtractionResult) -> List[Dict[str, Any]]:
    """Map extracted Project objects to dicts for projects.save."""
    results = []
    for item in result.items:
        p = item.project
        results.append(
            {
                "title": getattr(p, "title", "") or "",
                "tag": getattr(p, "tag", "") or "",
                "description": getattr(p, "description", "") or "",
                "start_date": _serialise_date(getattr(p, "start_date", None)),
                "end_date": _serialise_date(getattr(p, "end_date", None)),
                "contract_title_hint": item.contract_title_hint or "",
            }
        )
    return results


# ---------------------------------------------------------------------------
# Legacy function kept for backward compat (wraps parse_document)
# ---------------------------------------------------------------------------


def parse_contacts_from_document(
    file_base64: str,
    file_name: str,
    config: Optional[LLMConfig] = None,
) -> List[Dict[str, Any]]:
    """Parse contact information from a document (legacy wrapper)."""
    return parse_document(file_base64, file_name, "contact", config)
