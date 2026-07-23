from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional

import pandas as pd

PUBLIC = "public"
PRIVATE = "private"
VISIBILITY_COLUMN = "visibility"
ALLOWED_VISIBILITIES = {PUBLIC, PRIVATE}


def normalise_visibility(value: Any, default: str = PRIVATE) -> str:
    """Return a canonical visibility value: public or private.

    Unknown, blank, or null values default to PRIVATE unless a different valid
    default is supplied. This keeps accidental leakage conservative.
    """
    default_value = str(default or PRIVATE).strip().lower()
    if default_value not in ALLOWED_VISIBILITIES:
        default_value = PRIVATE

    if value is None:
        return default_value

    candidate = str(value).strip().lower()
    if candidate in ALLOWED_VISIBILITIES:
        return candidate
    return default_value


def ensure_visibility(
    row: MutableMapping[str, Any], default: str = PRIVATE
) -> Dict[str, Any]:
    """Return a dict copy of row with a valid visibility column."""
    out = dict(row or {})
    out[VISIBILITY_COLUMN] = normalise_visibility(
        out.get(VISIBILITY_COLUMN), default=default
    )
    return out


def ensure_rows_visibility(
    rows: Iterable[Mapping[str, Any]], default: str = PRIVATE
) -> List[Dict[str, Any]]:
    """Normalise visibility for a sequence of row dictionaries."""
    return [ensure_visibility(dict(row), default=default) for row in rows or []]


def is_public(row: Mapping[str, Any]) -> bool:
    """Return True when a row is explicitly public."""
    return (
        normalise_visibility((row or {}).get(VISIBILITY_COLUMN), default=PRIVATE)
        == PUBLIC
    )


def is_private(row: Mapping[str, Any]) -> bool:
    """Return True when a row is private or missing/invalid visibility."""
    return not is_public(row)


def force_public(row: MutableMapping[str, Any]) -> Dict[str, Any]:
    """Return a dict copy of row forced to public visibility."""
    out = dict(row or {})
    out[VISIBILITY_COLUMN] = PUBLIC
    return out


def force_private(row: MutableMapping[str, Any]) -> Dict[str, Any]:
    """Return a dict copy of row forced to private visibility."""
    out = dict(row or {})
    out[VISIBILITY_COLUMN] = PRIVATE
    return out


def force_world_news_public(row: MutableMapping[str, Any]) -> Dict[str, Any]:
    """World news is always public by design."""
    return force_public(row)


def force_world_news_rows_public(
    rows: Iterable[Mapping[str, Any]]
) -> List[Dict[str, Any]]:
    """Force every world-news row to public visibility."""
    return [force_world_news_public(dict(row)) for row in rows or []]


def filter_public_rows(rows: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Return only rows explicitly marked public."""
    return [dict(row) for row in rows or [] if is_public(row)]


def filter_private_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    actor_type: Optional[str] = None,
    actor_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return private rows, optionally filtered to one actor.

    This is used by private-summary generation. It must not be used to expose
    raw private rows to other agents.
    """
    out: List[Dict[str, Any]] = []
    for row in rows or []:
        row_dict = dict(row)
        if not is_private(row_dict):
            continue
        if actor_type is not None and str(row_dict.get("actor_type", "")) != str(
            actor_type
        ):
            continue
        if actor_id is not None and str(row_dict.get("actor_id", "")) != str(actor_id):
            continue
        out.append(row_dict)
    return out


def normalise_dataframe_visibility(
    df: pd.DataFrame, default: str = PRIVATE
) -> pd.DataFrame:
    """Return a dataframe copy with a valid visibility column."""
    if df is None or df.empty:
        out = pd.DataFrame() if df is None else df.copy()
        if VISIBILITY_COLUMN not in out.columns:
            out[VISIBILITY_COLUMN] = []
        return out

    out = df.copy()
    if VISIBILITY_COLUMN not in out.columns:
        out[VISIBILITY_COLUMN] = default
    out[VISIBILITY_COLUMN] = out[VISIBILITY_COLUMN].apply(
        lambda value: normalise_visibility(value, default=default)
    )
    return out


def public_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Return dataframe rows where visibility == public."""
    out = normalise_dataframe_visibility(df, default=PRIVATE)
    if out.empty:
        return out
    return out[out[VISIBILITY_COLUMN] == PUBLIC].copy()


def private_dataframe(
    df: pd.DataFrame,
    *,
    actor_type: Optional[str] = None,
    actor_id: Optional[str] = None,
) -> pd.DataFrame:
    """Return private dataframe rows, optionally filtered to actor_type/actor_id."""
    out = normalise_dataframe_visibility(df, default=PRIVATE)
    if out.empty:
        return out

    out = out[out[VISIBILITY_COLUMN] == PRIVATE].copy()
    if actor_type is not None and "actor_type" in out.columns:
        out = out[out["actor_type"].astype(str) == str(actor_type)]
    if actor_id is not None and "actor_id" in out.columns:
        out = out[out["actor_id"].astype(str) == str(actor_id)]
    return out.copy()


def validate_visibility_rules(
    public_value: str = PUBLIC,
    private_value: str = PRIVATE,
    world_news_visibility: str = PUBLIC,
) -> None:
    """Validate the project-level visibility conventions."""
    public_value = normalise_visibility(public_value, default=PUBLIC)
    private_value = normalise_visibility(private_value, default=PRIVATE)
    world_news_visibility = normalise_visibility(world_news_visibility, default=PUBLIC)

    if public_value != PUBLIC:
        raise ValueError("public visibility value must be 'public'")
    if private_value != PRIVATE:
        raise ValueError("private visibility value must be 'private'")
    if public_value == private_value:
        raise ValueError("public and private visibility values must be different")
    if world_news_visibility != PUBLIC:
        raise ValueError("world news visibility must be public")
