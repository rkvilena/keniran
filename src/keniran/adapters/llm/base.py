"""Requirement-extractor port — interface only in v1 (LLM support is backlog).

The v1 pipeline uses the deterministic rules parser
(:func:`keniran.core.requirements_parser.parse`) as its extractor. This module
defines the structural contract a future LLM-backed adapter (``openai.py`` and
friends) must satisfy so it can be added without changing the service layer.

No implementation lives here in v1.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from keniran.core.models import GameRequirements

__all__ = ["RequirementExtractor"]


@runtime_checkable
class RequirementExtractor(Protocol):
    """Turn cleaned Steam requirement text into the ``GameRequirements`` schema.

    Implementations receive the labeled text produced by
    :func:`keniran.adapters.steam.strip_requirements_html` and must return the
    same pydantic model the rules parser does; nothing may be fabricated for
    generic, model-numberless component names.
    """

    def extract(self, text: str) -> GameRequirements:
        """Return structured minimum requirements for *text*."""
        ...
