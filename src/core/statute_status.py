"""Canonical statutory validity vocabulary for LegalPilot-VN.

Vietnamese statutory instruments are stored with two competing status literals in
this codebase:

* ``"in_force"`` — the convention used by the ingestion pipeline, the Neo4j client,
  the Qdrant client and ``data/processed/neo4j_graph_export.json``.
* ``"active"``   — the convention used by the hand-authored ``STATUTE_CATALOG`` in
  ``src/agents/lawgraph.py``.

Because both literals describe the *same* real-world state, every validity check
MUST treat them as equivalent. Comparing against a single literal silently marks
in-force instruments as revoked, which both destroys recall and corrupts the
Claim Auditor's grounding rate.

This module is the single source of truth for that vocabulary. Do not reintroduce
literal status comparisons elsewhere.
"""

from __future__ import annotations

# --- Status literals ---------------------------------------------------------

ACTIVE = "active"
IN_FORCE = "in_force"
EXPIRED = "expired"
PARTIALLY_EXPIRED = "partially_expired"
NOT_IN_FORCE = "not_in_force"
UNKNOWN = "unknown"

#: Every literal that denotes a statute currently in effect.
ACTIVE_STATUSES: frozenset[str] = frozenset({ACTIVE, IN_FORCE})

#: Every literal that denotes a statute no longer (fully) in effect.
INACTIVE_STATUSES: frozenset[str] = frozenset({EXPIRED, PARTIALLY_EXPIRED, NOT_IN_FORCE})

#: Canonical spelling used when *writing* status values.
CANONICAL_ACTIVE = ACTIVE


def is_active_status(status: str | None, revoked_by: str | None = None) -> bool:
    """Return ``True`` when a statute is currently in force.

    A statute is considered active when its status maps to a member of
    :data:`ACTIVE_STATUSES` *and* it has no recorded revoking instrument.

    Args:
        status: Raw status literal as stored in the catalog or graph export.
            Compared case-insensitively and whitespace-trimmed.
        revoked_by: Document number of the instrument that repealed this one,
            if any. Any non-empty value forces an inactive verdict.

    Returns:
        ``True`` if the statute is in force, otherwise ``False``.
    """
    if revoked_by:
        return False
    if not status:
        return False
    return str(status).strip().lower() in ACTIVE_STATUSES


def normalize_status(status: str | None) -> str:
    """Map any known status literal onto its canonical spelling.

    Unknown values (including ``None``) are returned as :data:`UNKNOWN` so that
    they are never silently treated as active.

    Args:
        status: Raw status literal.

    Returns:
        One of the canonical literals defined in this module.
    """
    if not status:
        return UNKNOWN
    key = str(status).strip().lower()
    if key in ACTIVE_STATUSES:
        return CANONICAL_ACTIVE
    if key in INACTIVE_STATUSES:
        return key
    return UNKNOWN


if __name__ == "__main__":  # pragma: no cover - manual sanity check
    cases = [
        ("active", None, True),
        ("in_force", None, True),
        ("IN_FORCE ", None, True),
        ("expired", None, False),
        ("in_force", "52/2024/ND-CP", False),
        (None, None, False),
        ("bogus", None, False),
    ]
    for raw, revoked, expected in cases:
        actual = is_active_status(raw, revoked)
        flag = "ok " if actual == expected else "FAIL"
        print(f"[{flag}] is_active_status({raw!r}, {revoked!r}) -> {actual}")
