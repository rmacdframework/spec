"""RMACD Framework SDK - Policy evaluation for autonomous AI agents.

This SDK provides tools for:
- Loading and validating RMACD permission profiles (2D and 3D models)
- Evaluating policy decisions (can agent X perform operation Y on data Z?)
- Managing autonomy levels and HITL controls
- Handling emergency escalation logic
- Enforcing time windows and rate limits
- Tool registry for governance and risk assessment

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

Tools Registry usage:
    from rmacd.registry import ToolsRegistry, quick_register

    # Create registry
    registry = ToolsRegistry("my-registry")

    # Register tools
    quick_register(registry, "file_reader", "File Reader", "R", data_access="internal")

    # Validate access
    allowed, reason = registry.validate_tool_access("file_reader", ["R", "M"], "internal")
"""

from rmacd.models import (
    AutonomyLevel,
    DataAccess,
    DataClassification,
    Operation,
    PolicyDecision,
    Profile2D,
    Profile3D,
    ProfileDC2D,
    TierPolicy,
)
from rmacd.evaluator import PolicyEvaluator
from rmacd.loader import ProfileLoader
from rmacd.validator import ProfileValidator

__version__ = "0.3.0"
__all__ = [
    "AutonomyLevel",
    "DataAccess",
    "DataClassification",
    "Operation",
    "PolicyDecision",
    "PolicyEvaluator",
    "Profile2D",
    "Profile3D",
    "ProfileDC2D",
    "ProfileLoader",
    "ProfileValidator",
    "TierPolicy",
    # Registry available via rmacd.registry
]
