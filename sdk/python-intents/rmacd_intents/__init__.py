"""rmacd-intents — the RMACD Intents adjudication engine.

Implements the Intent Specification (``docs/intent-specification.md``) on top
of ``rmacd-framework``: the base level for every intent comes from the SDK's
``PolicyEvaluator.required_autonomy`` (N-13), and the engine owns escalation,
precedent, grants, the two logs and the decision record.

Wave 1 (this revision) targets implementation level L1 — Adjudicating.
"""

from __future__ import annotations

from importlib import metadata as _metadata

from .actors import ActorResolver, Resolution, ResolvedActor, StaticActorResolver
from .envelope import validate_submission
from .models import (
    ActionPatternFields,
    AdjudicationLogEntry,
    DecisionRecord,
    Disposition,
    EscalationFactor,
    Intent,
    IntentLogEntry,
    Rejection,
)
from .pattern import action_pattern_key, derive_target_class, pattern_fields
from .store import JSONLStore, MemoryStore, Store
from .weights import DEFAULT_WEIGHTS, WeightTable

try:
    __version__ = _metadata.version("rmacd-intents")
except _metadata.PackageNotFoundError:  # running from a source tree without installation
    __version__ = "0.0.0+unknown"

__all__ = [
    "ActionPatternFields",
    "ActorResolver",
    "AdjudicationLogEntry",
    "DEFAULT_WEIGHTS",
    "DecisionRecord",
    "Disposition",
    "EscalationFactor",
    "Intent",
    "IntentLogEntry",
    "JSONLStore",
    "MemoryStore",
    "Rejection",
    "ResolvedActor",
    "Resolution",
    "StaticActorResolver",
    "Store",
    "WeightTable",
    "__version__",
    "action_pattern_key",
    "derive_target_class",
    "pattern_fields",
    "validate_submission",
]
