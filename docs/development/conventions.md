# Coding Standards & Conventions

This document outlines the coding standards, repository conventions, and contribution guidelines for LegalPilot-VN.

---

## 1. Python Standards & Type Annotations

* **Target Version**: Python 3.11+.
* **Type Annotations**: All public functions, methods, and class attributes must have explicit type hints.
  * Use built-in generics (`list[str]`, `dict[str, Any]`, `tuple[int, ...]`) instead of `typing.List` or `typing.Dict`.
  * Use the pipe operator `|` for unions (`str | None`, `int | float`) instead of `typing.Optional` or `typing.Union`.
  * Add `from __future__ import annotations` at the top of every new module.

```python
from __future__ import annotations

from typing import Any


def resolve_citation(doc_id: str, article_num: int | None = None) -> dict[str, Any]:
    """Resolves citation metadata for a legal document."""
    ...
```

---

## 2. Zero Em-Dash / En-Dash Rule

To prevent character encoding inconsistencies across terminals, databases, and LLM tokenizers:

* **Strict Rule**: Do not use literal em-dash (U+2014) or en-dash (U+2013) characters anywhere in code, docstrings, or markdown files.
* **Alternative**: Use standard ASCII hyphen (`-`), colon (`:`), or parentheses (`()`).
* **Exception Handling**: If mapping Vietnamese legal text containing unicode dashes during parsing, use explicit unicode escape sequences (`\u2013`, `\u2014`) rather than literal characters.

---

## 3. Error Handling & Exceptions

* Never use bare `except:` clauses. Always catch specific exceptions.
* Domain-specific errors must inherit from base exceptions in `src/core/exceptions.py`:
  * `KnowledgeBaseError` for Neo4j and Qdrant operations.
  * `SecurityError` for guardrail and sanitizer violations.
  * `MemoryError` for SQLite storage issues.
* Always log errors with contextual details using `logger = get_logger(__name__)`.

---

## 4. Git & Commit Guidelines

We follow the **Conventional Commits** specification:

* `feat(scope): ...` for new features or capabilities.
* `fix(scope): ...` for bug fixes.
* `docs(scope): ...` for documentation updates.
* `test(scope): ...` for adding or updating tests.
* `refactor(scope): ...` for code improvements without functional changes.
* `chore(scope): ...` for dependency updates and build scripts.

### Examples:
```bash
feat(knowledge): add HTML parsing and LLM fallback to ingestion pipeline
fix(neo4j): cast document properties to prevent mypy return type error
docs(adr): document dual storage architecture decision
test(selective_traversal): add test cases for multi-hop amendment resolution
```

---

## 5. Pre-Flight Quality Checklist

Before submitting a pull request, ensure all of the following commands pass cleanly:

```bash
# 1. Format check
ruff format --check src tests

# 2. Lint check
ruff check src tests

# 3. Static type check
mypy src tests

# 4. Unit & integration tests
pytest tests/ -v
```
