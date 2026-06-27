"""Canonical row and table checksums for deterministic validation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Mapping


CANONICALIZATION_VERSION = "canonical_checksum.v1"


class ChecksumError(ValueError):
    """Raised when a value cannot be canonically encoded."""


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    logical_type: str
    precision: int | None = None
    scale: int | None = None


def row_digest(row: Mapping[str, Any], columns: Iterable[ColumnSpec]) -> str:
    """Return a stable digest for one row using column-name order."""

    payload = {
        "version": CANONICALIZATION_VERSION,
        "columns": [
            {
                "name": column.name,
                "value": _canonical_value(row.get(column.name), column),
            }
            for column in sorted(columns, key=lambda column: column.name)
        ],
    }
    return _sha256_json(payload)


def table_digest(rows: Iterable[Mapping[str, Any]], columns: Iterable[ColumnSpec]) -> str:
    """Return an order-independent digest for a table-sized row collection."""

    column_specs = tuple(columns)
    row_hashes = sorted(row_digest(row, column_specs) for row in rows)
    return _sha256_json(
        {
            "version": CANONICALIZATION_VERSION,
            "row_hashes": row_hashes,
        }
    )


def _canonical_value(value: Any, column: ColumnSpec) -> dict[str, Any]:
    if value is None:
        return {"type": "null", "value": None}

    logical_type = column.logical_type.lower()

    if logical_type in {"numeric", "decimal"}:
        return {"type": "numeric", "value": _canonical_decimal(value)}
    if logical_type in {"integer", "bigint", "smallint"}:
        return {"type": "integer", "value": str(int(value))}
    if logical_type in {"timestamptz", "timestamp with time zone"}:
        return {"type": "timestamptz", "value": _canonical_timestamptz(value)}
    if logical_type in {"json", "jsonb"}:
        return {"type": "jsonb", "value": _canonical_json(value)}
    if logical_type in {"text", "varchar", "character varying", "char", "character"}:
        return {"type": "text", "value": str(value)}
    if logical_type in {"boolean", "bool"}:
        return {"type": "boolean", "value": bool(value)}

    return {"type": logical_type, "value": _canonical_json(value)}


def _canonical_decimal(value: Any) -> str:
    decimal = value if isinstance(value, Decimal) else Decimal(str(value))
    if decimal.is_zero():
        decimal = Decimal("0")
    else:
        decimal = decimal.normalize()
    return format(decimal, "f")


def _canonical_timestamptz(value: Any) -> str:
    if not isinstance(value, datetime):
        raise ChecksumError(f"Expected datetime for timestamptz, got {type(value).__name__}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ChecksumError("timestamptz values must be timezone-aware")

    utc_value = value.astimezone(timezone.utc)
    return utc_value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _canonical_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _canonical_json(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonical_json(item) for item in value]
    if isinstance(value, tuple):
        return [_canonical_json(item) for item in value]
    if isinstance(value, Decimal):
        return {"__type": "numeric", "value": _canonical_decimal(value)}
    if isinstance(value, datetime):
        if value.tzinfo is not None and value.utcoffset() is not None:
            return {"__type": "timestamptz", "value": _canonical_timestamptz(value)}
        return {"__type": "timestamp", "value": value.isoformat(timespec="microseconds")}
    return value


def _sha256_json(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
