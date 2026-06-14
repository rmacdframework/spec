"""Command-line interface for RMACD Framework SDK."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import rmacd
from rmacd.evaluator import PolicyEvaluator
from rmacd.loader import ProfileLoader, ProfileLoadError
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
        print(
            f"ERROR: Invalid operation '{args.operation}'. Must be R, M, A, C, or D.",
            file=sys.stderr,
        )
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
        info: dict[str, Any] = {
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
                "created": (
                    profile.metadata.created.isoformat() if profile.metadata.created else None
                ),
            }
        print(json.dumps(info, indent=2))
    else:
        print(f"Profile ID: {profile.profile_id}")
        print(f"Name: {profile.profile_name}")
        print(f"Model: {profile.model}")
        print(f"Version: {profile.version}")
        if profile.description:
            print(f"Description: {profile.description}")

        if profile.model == "data-classification-2d":
            print("\nData Access:")
            permissions = evaluator.get_all_permissions()
            matrix = evaluator.get_effective_autonomy_matrix()
            for tier in ["public", "internal", "confidential", "restricted"]:
                status = "ALLOWED" if "allowed" in permissions.get(tier, []) else "DENIED"
                autonomy = matrix.get(tier, "N/A") if isinstance(matrix, dict) else "N/A"
                print(f"  {tier}: {status} (autonomy: {autonomy})")
        else:
            print("\nPermissions:")
            permissions = evaluator.get_all_permissions()
            for classification, ops in permissions.items():
                print(f"  {classification}: {', '.join(ops)}")

        if profile.emergency_escalation and profile.emergency_escalation.enabled:
            print("\nEmergency Escalation: ENABLED")
            print(f"  Max Duration: {profile.emergency_escalation.max_duration_minutes} minutes")

        if profile.metadata:
            print("\nMetadata:")
            status = profile.metadata.status.value if profile.metadata.status else "N/A"
            print(f"  Status: {status}")
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
        is_dc2d = profile.model == "data-classification-2d"

        if is_dc2d:
            print(f"{'Classification':<15} {'Autonomy Level':<20}")
            print("-" * 35)
            for tier in ["public", "internal", "confidential", "restricted"]:
                if tier in matrix:
                    print(f"{tier:<15} {matrix[tier]:<20}")
        elif is_3d:
            # Print header
            print(f"{'Classification':<15} {'R':<12} {'M':<12} {'A':<12} {'C':<12} {'D':<12}")
            print("-" * 75)

            for classification in ["public", "internal", "confidential", "restricted"]:
                if classification in matrix:
                    row = matrix[classification]
                    if not isinstance(row, dict):
                        continue
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


def _read_tool_source(path: str) -> list[dict[str, Any]]:
    """Read an MCP ``tools/list`` response (or a bare tool list) from a JSON file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("tools"), list):
        tools: list[dict[str, Any]] = data["tools"]
        return tools
    if isinstance(data, list):
        return data
    raise ValueError("source must be an MCP tools/list response or a JSON list of tools")


def _write_pack(pack: Any, out_path: str) -> None:
    p = Path(out_path)
    if p.suffix.lower() in (".yaml", ".yml"):
        import yaml

        p.write_text(yaml.safe_dump(pack.to_dict(), sort_keys=False), encoding="utf-8")
    else:
        p.write_text(pack.to_json(), encoding="utf-8")


def cmd_classify(args: argparse.Namespace) -> int:
    """AI-compile a governance pack from a tool source (MCP tools/list, etc.)."""
    from rmacd.packs.compile import compile_pack, review_items

    try:
        tools = _read_tool_source(args.source)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    llm = None
    if args.llm:
        try:
            from rmacd.registry.llm import LLMToolClassifier

            llm = LLMToolClassifier()
        except ImportError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1

    pack = compile_pack(
        tools,
        pack_name=args.name,
        version=args.pack_version,
        llm_classifier=llm,
        llm_mode=args.llm_mode,
    )

    if args.output:
        _write_pack(pack, args.output)
        print(f"Wrote {args.output} ({len(pack.rules)} rules)")
    else:
        print(pack.to_json())

    items = review_items(pack)
    if items:
        print(
            f"\n{len(items)} rule(s) need review before signing "
            "(low-confidence or delete-capable):",
            file=sys.stderr,
        )
        for it in items:
            print(f"  - {it['id']} [{it['operation']}] {it['reason']}", file=sys.stderr)
    return 0


def cmd_pack_validate(args: argparse.Namespace) -> int:
    """Validate a governance pack against the pack schema."""
    from rmacd.packs import PackValidationError, load_pack

    try:
        load_pack(args.pack)
        print(f"VALID: {args.pack}")
        return 0
    except PackValidationError as e:
        print(f"INVALID: {args.pack}", file=sys.stderr)
        for error in e.errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    except (OSError, ValueError, FileNotFoundError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


def cmd_pack_review(args: argparse.Namespace) -> int:
    """List the rules in a pack that warrant human review."""
    from rmacd.packs import load_pack
    from rmacd.packs.compile import review_items

    try:
        pack = load_pack(args.pack)
    except Exception as e:  # noqa: BLE001 - surface any load error to the CLI user
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    items = review_items(pack)
    status = getattr(pack.provenance, "review_status", None) if pack.provenance else None
    print(f"{pack.pack} v{pack.version}: {len(pack.rules)} rules, {len(items)} need review")
    if status:
        print(f"review status: {status}")
    for it in items:
        print(
            f"  - {it['id']}: operation={it['operation']} "
            f"confidence={it['confidence']} ({it['reason']})"
        )
    return 0


def cmd_pack_sign(args: argparse.Namespace) -> int:
    """Freeze and Ed25519-sign a pack."""
    from rmacd.packs import load_pack, sign_pack

    try:
        pack = load_pack(args.pack)
        key_pem = Path(args.key).read_text(encoding="utf-8")
        signed = sign_pack(pack, key_pem)
    except (OSError, ValueError, ImportError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    out = args.output or args.pack
    _write_pack(signed, out)
    print(f"Signed {out}\n  content_hash: {signed.content_hash}")
    return 0


def cmd_pack_verify(args: argparse.Namespace) -> int:
    """Verify a signed pack against a public key."""
    from rmacd.packs import load_pack, verify_pack

    try:
        pack = load_pack(args.pack)
        key_pem = Path(args.key).read_text(encoding="utf-8")
    except (OSError, ValueError, ImportError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    if verify_pack(pack, key_pem):
        print(f"VERIFIED: {args.pack}")
        return 0
    print(f"UNVERIFIED: {args.pack} (hash mismatch, missing, or bad signature)", file=sys.stderr)
    return 1


def cmd_pack_diff(args: argparse.Namespace) -> int:
    """Detect drift between a pack and a live tool source."""
    from rmacd.packs import load_pack, pack_drift

    try:
        pack = load_pack(args.pack)
        tools = _read_tool_source(args.source)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    drift = pack_drift(pack, tools)
    if not drift["drifted"]:
        print(f"IN SYNC: {args.pack}")
        return 0
    print(f"DRIFTED: {args.pack}")
    if drift["added"]:
        print(f"  added (re-review/classify):   {', '.join(drift['added'])}")
    if drift["removed"]:
        print(f"  removed (no longer in source): {', '.join(drift['removed'])}")
    if not drift["added"] and not drift["removed"]:
        print("  same tool names, but a tool definition changed (source hash differs)")
    return 1


def main() -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="rmacd",
        description="RMACD Framework CLI - Policy evaluation and profile management",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {rmacd.__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # validate command
    validate_parser = subparsers.add_parser(
        "validate", help="Validate profile(s) against JSON schema"
    )
    validate_parser.add_argument(
        "profiles", nargs="+", help="Profile file(s) to validate"
    )
    validate_parser.add_argument(
        "--schema-dir",
        help="Directory containing schema files (default: schemas bundled with the package)",
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

    # classify command (AI-compile a governance pack)
    classify_parser = subparsers.add_parser(
        "classify", help="AI-compile a governance pack from a tool source"
    )
    classify_parser.add_argument(
        "source", help="MCP tools/list JSON (or a JSON list of tool definitions)"
    )
    classify_parser.add_argument("-n", "--name", required=True, help="Pack name")
    classify_parser.add_argument(
        "-o", "--output", help="Output pack file (.json or .yaml); prints to stdout if omitted"
    )
    classify_parser.add_argument(
        "--pack-version", default="0.1.0", help="Pack version (default: 0.1.0)"
    )
    classify_parser.add_argument(
        "--llm", action="store_true", help="Use the LLM classifier (needs the [llm] extra)"
    )
    classify_parser.add_argument(
        "--llm-mode", choices=["fallback", "always"], default="fallback",
        help="When to consult the LLM (default: fallback)",
    )

    # pack command group
    pack_parser = subparsers.add_parser("pack", help="Author/validate governance packs")
    pack_sub = pack_parser.add_subparsers(dest="pack_command", help="Pack subcommands")

    pack_validate = pack_sub.add_parser("validate", help="Validate a pack against the schema")
    pack_validate.add_argument("pack", help="Pack file to validate")

    pack_review = pack_sub.add_parser("review", help="List rules that warrant human review")
    pack_review.add_argument("pack", help="Pack file to review")

    pack_sign = pack_sub.add_parser("sign", help="Freeze and Ed25519-sign a pack")
    pack_sign.add_argument("pack", help="Pack file to sign")
    pack_sign.add_argument("-k", "--key", required=True, help="Ed25519 private key (PEM)")
    pack_sign.add_argument("-o", "--output", help="Output file (default: overwrite input)")

    pack_verify = pack_sub.add_parser("verify", help="Verify a signed pack")
    pack_verify.add_argument("pack", help="Pack file to verify")
    pack_verify.add_argument("-k", "--key", required=True, help="Ed25519 public key (PEM)")

    pack_diff = pack_sub.add_parser("diff", help="Detect drift vs a live tool source")
    pack_diff.add_argument("pack", help="Pack file")
    pack_diff.add_argument("source", help="MCP tools/list JSON (or a JSON list of tools)")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "pack":
        pack_commands = {
            "validate": cmd_pack_validate,
            "review": cmd_pack_review,
            "sign": cmd_pack_sign,
            "verify": cmd_pack_verify,
            "diff": cmd_pack_diff,
        }
        if getattr(args, "pack_command", None) is None:
            pack_parser.print_help()
            return 0
        return pack_commands[args.pack_command](args)

    commands = {
        "validate": cmd_validate,
        "evaluate": cmd_evaluate,
        "info": cmd_info,
        "matrix": cmd_matrix,
        "classify": cmd_classify,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
