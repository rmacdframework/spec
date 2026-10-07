"""rmacd-intents — the RMACD Intents adjudication engine.

Implements the Intent Specification (``docs/intent-specification.md``) on top
of ``rmacd-framework``: the base level for every intent comes from the SDK's
``PolicyEvaluator.required_autonomy`` (N-13), and the engine owns escalation,
precedent, grants, the two logs and the decision record.

This revision implements all three levels (L1 Adjudicating, L2 Reconciling,
L3 Delegating) against Intent Specification 2.5.0 and claims L3 by default.
"""

from __future__ import annotations

from importlib import metadata as _metadata

from .actors import ActorResolver, Resolution, ResolvedActor, StaticActorResolver
from .envelope import validate_submission
from .grading import Engine, escalate
from .models import (
    ActionPatternFields,
    AdjudicationLogEntry,
    DecisionRecord,
    Disposition,
    EscalationFactor,
    Intent,
    IntentLogEntry,
    Normalization,
    Rejection,
)
from .pattern import action_pattern_key, derive_target_class, pattern_fields
from .reconcile import Reconciler, ReconcileReport
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
    "Engine",
    "Disposition",
    "EscalationFactor",
    "Intent",
    "IntentLogEntry",
    "JSONLStore",
    "MemoryStore",
    "Normalization",
    "ReconcileReport",
    "Reconciler",
    "Rejection",
    "ResolvedActor",
    "Resolution",
    "StaticActorResolver",
    "Store",
    "WeightTable",
    "__version__",
    "action_pattern_key",
    "derive_target_class",
    "escalate",
    "pattern_fields",
    "validate_submission",
]
