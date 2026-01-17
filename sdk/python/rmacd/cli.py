"""Command-line interface for RMACD Framework SDK."""

import argparse
import json
import sys
from pathlib import Path

from rmacd.evaluator import PolicyEvaluator
from rmacd.loader import ProfileLoadError, ProfileLoader
from rmacd.models import DataClassification, EvaluationContext, Operation
from rmacd.validator import ProfileValidator, SchemaValidationError


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate profile(s) against JSON schema."""
    validator = ProfileValidator(schema_dir=args.schema_dir)
    exit_code = 0

    for profile_path in args.profiles:
        path = Path(profile_path)
        if not path.exists():
            print(f"ERROR: File not found: {profile_path}", file=sys.stderr)
            exit_code = 1
            continue

        try:
            validator.validate_file(path)
            if not args.quiet:
                print(f"VALID: {profile_path}")
        except SchemaValidationError as e:
            print(f"INVALID: {profile_path}", file=sys.stderr)
            for error in e.errors:
                print(f"  - {error}", file=sys.stderr)
            exit_code = 1

    return exit_code


def cmd_evaluate(args: argparse.Namespace) -> int:
    """Evaluate a policy decision."""
    loader = ProfileLoader()

    try:
        profile = loader.load_file(args.profile)
    except ProfileLoadError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    evaluator = PolicyEvaluator(profile)

    # Parse operation
    try:
        operation = Operation(args.operation.upper())
    except ValueError:
        print(f"ERROR: Invalid operation '{args.operation}'. Must be R, M, A, C, or D.", file=sys.stderr)
        return 1

    # Parse data classification (required for 3D)
    classification = None
    if args.classification:
        try:
            classification = DataClassification(args.classification.lower())
        except ValueError:
            print(
                f"ERROR: Invalid classification '{args.classification}'. "
                "Must be public, internal, confidential, or restricted.",
                file=sys.stderr,
            )
            return 1

    # Build context
    context = EvaluationContext(emergency_active=args.emergency)

    try:
        decision = evaluator.evaluate(operation, classification, context)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(decision.model_dump_json(indent=2))
    else:
        status = "ALLOWED" if decision.allowed else "DENIED"
        print(f"Decision: {status}")
        print(f"Operation: {decision.operation.value}")
        if decision.data_classification:
            print(f"Classification: {decision.data_classification.value}")
        print(f"Autonomy Level: {decision.autonomy_level.value}")
        print(f"Requires Approval: {decision.requires_approval}")
        print(f"Requires Notification: {decision.requires_notification}")
        if decision.blocked_reason:
            print(f"Blocked Reason: {decision.blocked_reason}")
        if decision.emergency_mode:
            print("Emergency Mode: ACTIVE")

    return 0 if decision.allowed else 2


def cmd_info(args: argparse.Namespace) -> int:
    """Display profile information."""
    loader = ProfileLoader()

    try:
        profile = loader.load_file(args.profile)
    except ProfileLoadError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    evaluator = PolicyEvaluator(profile)

    if args.json:
        info = {
            "profile_id": profile.profile_id,
            "profile_name": profile.profile_name,
            "model": profile.model,
            "version": profile.version,
            "description": profile.description,
            "permissions": evaluator.get_all_permissions(),
        }
        if profile.metadata:
            info["metadata"] = {
                "status": profile.metadata.status.value if profile.metadata.status else None,
                "author": profile.metadata.author,
                "created": profile.metadata.created.isoformat() if profile.metadata.created else None,
            }
        print(json.dumps(info, indent=2))
    else:
        print(f"Profile ID: {profile.profile_id}")
        print(f"Name: {profile.profile_name}")
        print(f"Model: {profile.model}")
        print(f"Version: {profile.version}")
        if profile.description:
            print(f"Description: {profile.description}")

        print("\nPermissions:")
        permissions = evaluator.get_all_permissions()
        for classification, ops in permissions.items():
            print(f"  {classification}: {', '.join(ops)}")

        if profile.emergency_escalation and profile.emergency_escalation.enabled:
            print("\nEmergency Escalation: ENABLED")
            print(f"  Max Duration: {profile.emergency_escalation.max_duration_minutes} minutes")

        if profile.metadata:
            print("\nMetadata:")
            print(f"  Status: {profile.metadata.status.value if profile.metadata.status else 'N/A'}")
            print(f"  Author: {profile.metadata.author}")

    return 0


def cmd_matrix(args: argparse.Namespace) -> int:
    """Display the effective autonomy matrix."""
    loader = ProfileLoader()

    try:
        profile = loader.load_file(args.profile)
    except ProfileLoadError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    evaluator = PolicyEvaluator(profile)
    matrix = evaluator.get_effective_autonomy_matrix()

    if args.json:
        print(json.dumps(matrix, indent=2))
    else:
        is_3d = profile.model == "three-dimensional"

        if is_3d:
            # Print header
            print(f"{'Classification':<15} {'R':<12} {'M':<12} {'A':<12} {'C':<12} {'D':<12}")
            print("-" * 75)

            for classification in ["public", "internal", "confidential", "restricted"]:
                if classification in matrix:
                    row = matrix[classification]
                    print(
                        f"{classification:<15} "
                        f"{row.get('R', 'N/A'):<12} "
                        f"{row.get('M', 'N/A'):<12} "
                        f"{row.get('A', 'N/A'):<12} "
                        f"{row.get('C', 'N/A'):<12} "
                        f"{row.get('D', 'N/A'):<12}"
                    )
        else:
            print(f"{'Operation':<12} {'Autonomy Level':<20}")
            print("-" * 35)
            for op in ["R", "M", "A", "C", "D"]:
                if op in matrix:
                    print(f"{op:<12} {matrix[op]:<20}")

    return 0


def main() -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="rmacd",
        description="RMACD Framework CLI - Policy evaluation and profile management",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # validate command
    validate_parser = subparsers.add_parser(
        "validate", help="Validate profile(s) against JSON schema"
    )
    validate_parser.add_argument(
        "profiles", nargs="+", help="Profile file(s) to validate"
    )
    validate_parser.add_argument(
        "--schema-dir", help="Directory containing schema files"
    )
    validate_parser.add_argument(
        "-q", "--quiet", action="store_true", help="Only output errors"
    )

    # evaluate command
    eval_parser = subparsers.add_parser("evaluate", help="Evaluate a policy decision")
    eval_parser.add_argument("profile", help="Profile file to evaluate against")
    eval_parser.add_argument(
        "operation", help="Operation to evaluate (R, M, A, C, or D)"
    )
    eval_parser.add_argument(
        "-c",
        "--classification",
        help="Data classification (public, internal, confidential, restricted)",
    )
    eval_parser.add_argument(
        "--emergency", action="store_true", help="Evaluate with emergency escalation active"
    )
    eval_parser.add_argument(
        "--json", action="store_true", help="Output result as JSON"
    )

    # info command
    info_parser = subparsers.add_parser("info", help="Display profile information")
    info_parser.add_argument("profile", help="Profile file to display")
    info_parser.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )

    # matrix command
    matrix_parser = subparsers.add_parser(
        "matrix", help="Display effective autonomy matrix"
    )
    matrix_parser.add_argument("profile", help="Profile file to analyze")
    matrix_parser.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    commands = {
        "validate": cmd_validate,
        "evaluate": cmd_evaluate,
        "info": cmd_info,
        "matrix": cmd_matrix,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
