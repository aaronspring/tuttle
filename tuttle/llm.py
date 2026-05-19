"""LLM integration for AI-powered document processing.

Provides configuration management, Ollama model discovery, and
structured entity extraction from documents using llama_index.
"""

import base64
import json
import time
from decimal import Decimal
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
    Field descriptions are preserved so llama_index structured output
    can communicate field semantics to the LLM via the JSON Schema.
    """
    fields: Dict[str, Any] = {}
    for name, field_info in model_cls.model_fields.items():
        if name == "id" or name.endswith("_id"):
            continue
        if include and name not in include:
            continue
        annotation = model_cls.__annotations__.get(name)
        if annotation is None:
            continue
        # Decimal/condecimal emit regex patterns that crash Ollama's
        # SchemaToGrammar; use plain float for LLM extraction instead.
        origin = getattr(annotation, "__origin__", None)
        if annotation is Decimal or (
            origin is not None and Decimal in getattr(annotation, "__args__", ())
        ):
            annotation = float
        elif hasattr(annotation, "__supertype__") and issubclass(
            annotation.__supertype__, Decimal
        ):
            annotation = float
        fields[name] = (
            Optional[annotation],
            Field(
                default=None,
                description=field_info.description,
            ),
        )

    return _create_model(f"{model_cls.__name__}Extract", **fields)


_AddressExtract = _flat_schema(Address)
_ContactScalarExtract = _flat_schema(
    Contact, include=["first_name", "last_name", "company", "email"]
)


# Contact needs a nested address object (not an FK), so extend the flat schema
class _ContactExtract(_ContactScalarExtract):  # type: ignore[valid-type]
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
            thinking=True,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {config.provider}")


# ---------------------------------------------------------------------------
# Prompts per entity type
# ---------------------------------------------------------------------------

_PROMPTS = {
    "contact": "Extract all contact information (people or companies) from the following document.\n\n",
    "client": "Extract all client or company entities from the following document.\n\n",
    "contract": "Extract all contracts or service agreements from the following document.\n\n",
    "project": "Extract all project descriptions or work packages from the following document.\n\n",
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
# Unified contract-document extraction (all entity types in one pass)
# ---------------------------------------------------------------------------


class _RefContact(_ContactExtract):
    ref: str = Field(description="Internal reference ID, e.g. 'contact_1'")


class _RefClient(_ClientExtract):  # type: ignore[valid-type]
    ref: str = Field(description="Internal reference ID, e.g. 'client_1'")
    contact_ref: Optional[str] = Field(
        default=None, description="ref of the contact person for this client"
    )


class _RefContract(_ContractExtract):  # type: ignore[valid-type]
    ref: str = Field(description="Internal reference ID, e.g. 'contract_1'")
    client_ref: Optional[str] = Field(
        default=None, description="ref of the client this contract belongs to"
    )


class _RefProject(_ProjectExtract):  # type: ignore[valid-type]
    ref: str = Field(description="Internal reference ID, e.g. 'project_1'")
    contract_ref: Optional[str] = Field(
        default=None, description="ref of the contract this project belongs to"
    )


class ContractDocumentExtractionResult(BaseModel):
    """All entities extracted from a single contract document, with cross-refs."""

    contacts: List[_RefContact] = Field(
        description="People mentioned, e.g. signatories or contact persons"
    )
    clients: List[_RefClient] = Field(
        description="Companies or organisations that are the contracting party"
    )
    contracts: List[_RefContract] = Field(description="Contractual agreements")
    projects: List[_RefProject] = Field(
        description="Project descriptions or work packages"
    )


_CONTRACT_DOC_PROMPT = (
    "You are extracting structured data from a contract or service-agreement document.\n"
    "Extract ALL of the following entity types:\n\n"
    "CONTACTS: Every person mentioned by name (signatories, contact persons, managers). "
    "Include their name, company, email, and address if available.\n\n"
    "CLIENTS: Every company or organisation that is a party to the contract. "
    "Link each client to its contact person via contact_ref.\n\n"
    "CONTRACTS: The contractual agreement(s) described. "
    "Extract the rate, currency, unit of time, billing cycle, volume, dates, "
    "VAT rate, and payment terms. Link each contract to its client via client_ref.\n\n"
    "PROJECTS: Any project, work package, or deliverable described. "
    "Link each project to its contract via contract_ref.\n\n"
    "RULES:\n"
    "- Populate EVERY field you can find evidence for; only use null for truly unknown values.\n"
    "- Use ref strings (contact_1, client_1, contract_1, project_1) to cross-link entities.\n"
    "- Dates must be in YYYY-MM-DD format.\n"
    "- You MUST return at least one contact and one client if the document mentions any parties.\n\n"
)


_IMPORT_STEPS = [
    {"key": "load_config", "label": "Loading LLM configuration"},
    {"key": "read_document", "label": "Reading document"},
    {"key": "connect_llm", "label": "Connecting to LLM"},
    {"key": "extract_entities", "label": "Extracting entities with AI"},
    {"key": "map_results", "label": "Processing results"},
]


def parse_contract_document(
    file_base64: str,
    file_name: str,
    config: Optional[LLMConfig] = None,
) -> Dict[str, Any]:
    """Extract all entity types from a contract document in a single LLM call.

    Returns a dict with keys:
    - steps: list of {key, label, status, error?} tracking pipeline progress
    - contacts, clients, contracts, projects (when successful)
    """
    steps = [{**s, "status": "pending", "error": None} for s in _IMPORT_STEPS]

    def _mark(key: str, status: str, error: str | None = None):
        for s in steps:
            if s["key"] == key:
                s["status"] = status
                if error:
                    s["error"] = error
                break

    def _fail(key: str, error: str) -> Dict[str, Any]:
        _mark(key, "error", error)
        return {"steps": steps}

    # Step 1: Load config
    _mark("load_config", "running")
    try:
        if config is None:
            config = load_config()
        if not config.model:
            return _fail(
                "load_config",
                "No LLM model configured. Please set up an LLM in Settings.",
            )
        _mark("load_config", "done")
    except Exception as e:
        logger.exception("parse_contract_document: load_config failed")
        return _fail("load_config", str(e))

    # Step 2: Read document
    _mark("read_document", "running")
    try:
        file_bytes = base64.b64decode(file_base64)
        text = _extract_text(file_bytes, file_name)
        if not text.strip():
            return _fail(
                "read_document",
                "Document appears to be empty or could not be read.",
            )
        _mark("read_document", "done")
    except Exception as e:
        logger.exception("parse_contract_document: read_document failed")
        return _fail("read_document", f"Could not read document: {e}")

    # Step 3: Connect to LLM
    _mark("connect_llm", "running")
    try:
        llm = _get_llm(config)
        sllm = llm.as_structured_llm(output_cls=ContractDocumentExtractionResult)
        _mark("connect_llm", "done")
    except Exception as e:
        logger.exception("parse_contract_document: connect_llm failed")
        return _fail("connect_llm", f"Could not connect to LLM: {e}")

    # Step 4: Extract entities
    _mark("extract_entities", "running")
    text_len = len(text)
    est_tokens = text_len // 4
    diag = (
        f"model={config.model}, base_url={config.base_url}, "
        f"text={text_len} chars (~{est_tokens} tokens), "
        f"timeout={config.request_timeout}s"
    )
    logger.info(f"LLM extraction starting: {diag}")
    t0 = time.monotonic()
    try:
        prompt = (
            _CONTRACT_DOC_PROMPT
            + "--- DOCUMENT START ---\n"
            + text
            + "\n--- DOCUMENT END ---"
        )
        response = sllm.complete(prompt)
        elapsed = time.monotonic() - t0
        logger.info(f"LLM extraction completed in {elapsed:.1f}s: {diag}")
        raw_text = response.text
        logger.info(f"LLM raw response ({len(raw_text)} chars): {raw_text[:2000]}")
        extracted: ContractDocumentExtractionResult = response.raw
        logger.info(
            f"Parsed extraction: "
            f"contacts={len(extracted.contacts)}, "
            f"clients={len(extracted.clients)}, "
            f"contracts={len(extracted.contracts)}, "
            f"projects={len(extracted.projects)}"
        )
        _mark("extract_entities", "done")
    except Exception as e:
        elapsed = time.monotonic() - t0
        logger.exception(f"LLM extraction failed after {elapsed:.1f}s: {diag}")
        msg = str(e)
        low = msg.lower()
        if "timed out" in low or "timeout" in low:
            msg = (
                f"LLM request timed out after {elapsed:.0f}s. "
                f"Try a faster model or increase the timeout in Settings. ({msg})"
            )
        elif (
            "disconnected" in low
            or "remoteprotocolerror" in low
            or "connection reset" in low
        ):
            msg = (
                f"The LLM server disconnected after {elapsed:.0f}s. "
                f"This usually means the model crashed (out of memory). "
                f"Check the Ollama server logs, try a smaller model, "
                f"or reduce the context window. "
                f"[{config.model} @ {config.base_url}, ~{est_tokens} tokens]"
            )
        elif "connection" in low or "refused" in low:
            msg = f"Could not reach the LLM server. Is Ollama running? ({msg})"
        return _fail("extract_entities", msg)

    # Step 5: Map results
    _mark("map_results", "running")
    try:
        result = _map_contract_document(extracted)
        _mark("map_results", "done")
    except Exception as e:
        logger.exception("parse_contract_document: map_results failed")
        return _fail("map_results", f"Failed to process LLM output: {e}")

    return {"steps": steps, **result}


def _has_content(d: Dict[str, Any], ignore: set = {"ref"}) -> bool:
    """True if the dict has at least one non-null, non-empty value beyond ignored keys."""
    for k, v in d.items():
        if k in ignore:
            continue
        if v is None or v == "" or v == 0:
            continue
        if isinstance(v, dict) and not _has_content(v, ignore=set()):
            continue
        return True
    return False


def _dump_extracted(items: list) -> List[Dict[str, Any]]:
    """Serialise a list of Pydantic extraction models to dicts.

    Coerces date fields via ``_serialise_date`` for frontend convenience.
    Drops skeleton items where only the ref is populated.
    """
    results = []
    for item in items:
        d = item.model_dump()
        for k in list(d):
            if k.endswith("_date"):
                d[k] = _serialise_date(d[k])
        if _has_content(d):
            results.append(d)
        else:
            logger.debug(f"Dropping skeleton entity: {d}")
    return results


def _map_contract_document(
    result: ContractDocumentExtractionResult,
) -> Dict[str, Any]:
    """Convert the unified extraction result to a frontend-ready dict."""
    mapped = {
        "contacts": _dump_extracted(result.contacts),
        "clients": _dump_extracted(result.clients),
        "contracts": _dump_extracted(result.contracts),
        "projects": _dump_extracted(result.projects),
    }
    logger.info(
        f"Mapped result counts: "
        + ", ".join(f"{k}={len(v)}" for k, v in mapped.items())
    )
    return mapped


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
