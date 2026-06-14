"""
RMACD Governance Packs
======================

Declarative, reusable, signable bundles ("governance packs") that map a tool
call to RMACD terms ``(operation, data tier, target)`` as data instead of
hand-written classifiers — plus the runtime engine that compiles a pack into the
``ToolClassifier`` callable the registry already understands.

The module is named for the artifact (a *pack*); "classification" remains the
mechanic (the act of mapping a call to RMACD terms), consistent with
``rmacd.registry``'s ``ToolClassifier`` / ``LLMToolClassifier``. The runtime is
fully deterministic — packs only produce the ``(operation, tier, target)`` input
to the evaluator; the §12.5 floor, agent profile, and capability ceiling remain
the authoritative gates.

Usage (target shape; loaders/engine land in later phases)::

    from rmacd.packs import load_packs
    enforcer.registry = load_packs(["shell", "aws", "jira"])

Author: Kash Kashyap
License: CC BY 4.0
"""

from rmacd.packs.models import (
    ArgRegex,
    ArgvContains,
    ClassifySpec,
    GovernancePack,
    OperationStr,
    ParseSpec,
    PatternMapEntry,
    Provenance,
    ResolverDecl,
    Rule,
    Selector,
    TierSpec,
    TierStr,
)
from rmacd.packs.validation import (
    PackValidationError,
    get_schema,
    is_valid_pack,
    validate_pack_dict,
    validate_pack_file,
)

__all__ = [
    # models
    "GovernancePack",
    "Rule",
    "Selector",
    "ParseSpec",
    "ClassifySpec",
    "TierSpec",
    "PatternMapEntry",
    "ArgRegex",
    "ArgvContains",
    "ResolverDecl",
    "Provenance",
    "OperationStr",
    "TierStr",
    # validation
    "PackValidationError",
    "validate_pack_dict",
    "validate_pack_file",
    "is_valid_pack",
    "get_schema",
]
