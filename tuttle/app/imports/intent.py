"""Batch-commit workflow for document-imported entity graphs."""

import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

import sqlmodel
from loguru import logger

from ..core.abstractions import SQLModelDataSourceMixin
from ..core.intent_result import IntentResult
from ...model import Address, Contact, Client, Contract, Project
from ...time import Cycle, TimeUnit


# Fields that are internal to the import workflow, not part of the model
_IMPORT_META = {
    "ref",
    "existing_id",
    "update_existing",
    "contact_ref",
    "client_ref",
    "contract_ref",
}


class ImportsIntent(SQLModelDataSourceMixin):
    """Commit a reviewed set of extracted entities in dependency order."""

    def __init__(self):
        super().__init__()

    def get_existing_entities(self) -> IntentResult:
        """Return all contacts, clients, contracts, projects for smart-matching."""
        try:
            return IntentResult(
                was_intent_successful=True,
                data={
                    "contacts": [c.to_rpc_dict() for c in self.query(Contact)],
                    "clients": [c.to_rpc_dict() for c in self.query(Client)],
                    "contracts": [c.to_rpc_dict() for c in self.query(Contract)],
                    "projects": [p.to_rpc_dict() for p in self.query(Project)],
                },
            )
        except Exception as e:
            return IntentResult(
                was_intent_successful=False,
                error_msg="Failed to load existing entities for matching.",
                log_message=f"ImportsIntent.get_existing_entities: {e}",
                exception=e,
            )

    def commit_contract_import(self, data: dict) -> IntentResult:
        """Persist the finalized import graph transactionally.

        Each entity list item has either ``existing_id`` (link/update) or
        not (create new).  Cross-references use ``ref`` strings resolved
        via ``contact_ref``, ``client_ref``, ``contract_ref``.
        """
        try:
            ref_to_id: Dict[str, int] = {}
            summary: Dict[str, List[str]] = {"created": [], "linked": [], "updated": []}

            with self.create_session() as session:
                for item in data.get("contacts", []):
                    _save_entity(
                        session,
                        Contact,
                        item,
                        ref_to_id,
                        summary,
                        nested={"address": Address},
                    )

                for item in data.get("clients", []):
                    _save_entity(
                        session,
                        Client,
                        item,
                        ref_to_id,
                        summary,
                        ref_fks={"contact_ref": "invoicing_contact_id"},
                    )

                for item in data.get("contracts", []):
                    _save_entity(
                        session,
                        Contract,
                        item,
                        ref_to_id,
                        summary,
                        ref_fks={"client_ref": "client_id"},
                    )

                for item in data.get("projects", []):
                    _save_entity(
                        session,
                        Project,
                        item,
                        ref_to_id,
                        summary,
                        ref_fks={"contract_ref": "contract_id"},
                    )

                session.commit()

            return IntentResult(was_intent_successful=True, data=summary)
        except Exception as e:
            logger.exception("commit_contract_import failed")
            return IntentResult(
                was_intent_successful=False,
                error_msg=f"Import failed: {e}",
                log_message=f"ImportsIntent.commit_contract_import: {e}",
                exception=e,
            )


def _save_entity(
    session: sqlmodel.Session,
    model_cls: type,
    item: dict,
    ref_to_id: Dict[str, int],
    summary: Dict[str, List[str]],
    *,
    ref_fks: Optional[Dict[str, str]] = None,
    nested: Optional[Dict[str, type]] = None,
):
    """Create or link a single entity, resolving cross-refs to FK ids."""
    ref = item.get("ref", "")
    existing_id = item.get("existing_id")
    label = _entity_label(model_cls, item)

    if existing_id:
        entity = session.get(model_cls, existing_id)
        if entity and item.get("update_existing"):
            fields = _model_fields(item, model_cls)
            for k, v in fields.items():
                setattr(entity, k, v)
            summary["updated"].append(label)
        else:
            summary["linked"].append(label)
        if entity:
            _bind_ref(ref, entity.id, ref_to_id)
        return

    # Resolve cross-ref strings to FK ids
    fields = dict(item)
    for ref_key, fk_field in (ref_fks or {}).items():
        ref_val = fields.pop(ref_key, "")
        if ref_val and ref_val in ref_to_id:
            fields[fk_field] = ref_to_id[ref_val]

    # Handle nested objects (e.g. address)
    nested_objects = {}
    for rel_name, rel_cls in (nested or {}).items():
        rel_data = fields.pop(rel_name, None)
        if isinstance(rel_data, dict):
            rel_data.pop("id", None)
            nested_objects[rel_name] = rel_cls(**rel_data)

    clean = _model_fields(fields, model_cls)
    entity = model_cls(**clean, **nested_objects)
    session.add(entity)
    session.flush()
    _bind_ref(ref, entity.id, ref_to_id)
    summary["created"].append(label)


def _coerce_value(value: Any, annotation: Any) -> Any:
    """Coerce a JSON value to the expected Python type."""
    if value is None or value == "":
        return None
    origin = getattr(annotation, "__origin__", None)
    args = getattr(annotation, "__args__", ())
    if origin is not None and type(None) in args:
        inner = next((a for a in args if a is not type(None)), None)
        if inner is not None:
            return _coerce_value(value, inner)
    if annotation is datetime.date or annotation == datetime.date:
        if isinstance(value, str):
            return datetime.date.fromisoformat(value)
    if annotation is Decimal or (
        hasattr(annotation, "__supertype__")
        and issubclass(getattr(annotation, "__supertype__", type), Decimal)
    ):
        if isinstance(value, (int, float, str)):
            return Decimal(str(value))
    return value


def _model_fields(data: dict, model_cls: type) -> dict:
    """Filter a dict to only keys that are valid model fields, excluding meta.

    Coerces date strings and decimals to their Python types.
    """
    valid = set(model_cls.model_fields.keys()) - {"id"}
    result = {}
    for k, v in data.items():
        if k not in valid or k in _IMPORT_META:
            continue
        field_info = model_cls.model_fields.get(k)
        if field_info and field_info.annotation is not None:
            v = _coerce_value(v, field_info.annotation)
        if v is not None:
            result[k] = v
    return result


def _entity_label(model_cls: type, item: dict) -> str:
    name = model_cls.__name__
    title = item.get("title") or item.get("name") or ""
    if not title:
        first = item.get("first_name", "")
        last = item.get("last_name", "")
        title = f"{first} {last}".strip()
    return f"{name}: {title}" if title else name


def _bind_ref(ref: str, entity_id: Optional[int], ref_to_id: Dict[str, int]):
    """Record the ref -> DB id mapping after flush."""
    if ref and entity_id is not None:
        ref_to_id[ref] = entity_id
