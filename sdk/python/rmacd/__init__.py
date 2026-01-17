"""RMACD Framework SDK - Policy evaluation for autonomous AI agents.

This SDK provides tools for:
- Loading and validating RMACD permission profiles (2D and 3D models)
- Evaluating policy decisions (can agent X perform operation Y on data Z?)
- Managing autonomy levels and HITL controls
- Handling emergency escalation logic
- Enforcing time windows and rate limits

Example usage:
    from rmacd import ProfileLoader, PolicyEvaluator

    # Load a profile
    loader = ProfileLoader()
    profile = loader.load_file("profiles/devops-agent.json")

    # Evaluate a policy decision
    evaluator = PolicyEvaluator(profile)
    decision = evaluator.evaluate(
        operation="C",  # Change
        data_classification="internal",
    )

    print(f"Allowed: {decision.allowed}")
    print(f"Autonomy: {decision.autonomy_level}")
    print(f"Requires approval: {decision.requires_approval}")
"""

from rmacd.models import (
    AutonomyLevel,
    DataClassification,
    Operation,
    PolicyDecision,
    Profile2D,
    Profile3D,
)
from rmacd.evaluator import PolicyEvaluator
from rmacd.loader import ProfileLoader
from rmacd.validator import ProfileValidator

__version__ = "0.1.0"
__all__ = [
    "AutonomyLevel",
    "DataClassification",
    "Operation",
    "PolicyDecision",
    "PolicyEvaluator",
    "Profile2D",
    "Profile3D",
    "ProfileLoader",
    "ProfileValidator",
]
