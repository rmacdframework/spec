"""
RMACD MCP Server
================

Expose RMACD policy evaluation to any MCP client (Claude Code, Claude
Desktop, non-Python agents) as a standard MCP server over stdio, so clients
can query policy without embedding the Python SDK in-process.

Start it from the CLI::

    rmacd mcp-serve                     # clients pass profile_path per call
    rmacd mcp-serve --profile ops.json  # enterprise mode: profile is pinned

Six read-only tools are served (server name ``rmacd``):

- ``rmacd_evaluate``          — policy decision for (operation, classification)
- ``rmacd_validate_profile``  — schema-validate a profile file or JSON string
- ``rmacd_matrix``            — effective autonomy matrix for a profile
- ``rmacd_list_packs``        — built-in governance packs (names + versions)
- ``rmacd_pack_info``         — pack metadata, rule count, signature status
- ``rmacd_classify_bash``     — advisory RMACD classification of a shell command

**Pinning (enterprise mode).** When the server is launched with ``--profile``,
that profile is authoritative: ``profile_path`` arguments become optional and,
if supplied to a decision-bearing tool (``rmacd_evaluate``, ``rmacd_matrix``),
are *rejected with a clear error* rather than silently ignored — clients
cannot swap profiles. ``rmacd_validate_profile`` still accepts arbitrary
documents (it is a linter and confers no policy authority); called with no
arguments in pinned mode it validates the pinned profile file.

**Read-only.** The server never mutates state, never runs approvals, and
never writes audit records: every decision comes from the same code path as
``PolicyEnforcer.evaluate_only`` (a bare :class:`PolicyEvaluator` run). The
§12.5 immutable floor applies as always.

The ``mcp`` dependency is an **optional** extra
(``pip install rmacd-framework[mcp]``) and is imported lazily, mirroring
``rmacd.registry.llm``: importing this module — and calling
:func:`build_tools` — is safe without it; only :func:`create_server` /
:func:`serve` require it.

Author: Kash Kashyap
License: CC BY 4.0
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rmacd.evaluator import PolicyEvaluator
from rmacd.loader import AnyProfile, ProfileLoader
from rmacd.models import DataClassification, Environment, EvaluationContext, Operation
from rmacd.validator import ProfileValidator, SchemaValidationError

if TYPE_CHECKING:  # pragma: no cover - typing only; [mcp] extra may be absent
    from mcp.server.fastmcp import FastMCP

SERVER_NAME = "rmacd"

_INSTALL_HINT = (
    "The RMACD MCP server requires the 'mcp' package. "
    "Install it with: pip install 'rmacd-framework[mcp]'"
)

_INSTRUCTIONS = (
    "Read-only RMACD governance queries: evaluate policy decisions, validate "
    "profiles, inspect autonomy matrices and governance packs, and classify "
    "shell commands. This server never mutates state and never grants "
    "approvals; the RMACD §12.5 immutable floor (no Add/Change/Delete on "
    "Restricted data for autonomous agents) always applies."
)


def _import_fastmcp() -> type[FastMCP]:
    """Import FastMCP lazily so the base install works without the extra."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ImportError(_INSTALL_HINT) from exc
    return FastMCP


def _parse_operation(operation: str) -> Operation:
    try:
        return Operation(operation.upper())
    except ValueError:
        raise ValueError(
            f"Invalid operation '{operation}'. Must be one of R, M, A, C, D."
        ) from None


def _parse_classification(classification: str) -> DataClassification:
    try:
        return DataClassification(classification.lower())
    except ValueError:
        raise ValueError(
            f"Invalid classification '{classification}'. Must be one of "
            "public, internal, confidential, restricted."
        ) from None


def _parse_environment(environment: str) -> Environment:
    try:
        return Environment(environment.lower())
    except ValueError:
        valid = ", ".join(e.value for e in Environment)
        raise ValueError(
            f"Invalid environment '{environment}'. Must be one of {valid}."
        ) from None


def build_tools(
    pinned_profile: str | Path | None = None,
) -> dict[str, Callable[..., Any]]:
    """Build the six MCP tool functions as plain callables.

    Does not require the ``mcp`` package — :func:`create_server` wraps these
    with FastMCP decorators. Keeping them plain functions lets tests call
    them directly without a transport.

    Args:
        pinned_profile: When given, the profile is loaded now and becomes
            authoritative; per-call ``profile_path`` arguments to
            decision-bearing tools are rejected with a clear error.
    """
    loader = ProfileLoader()
    pinned: AnyProfile | None = None
    pinned_source: str | None = None
    if pinned_profile is not None:
        pinned = loader.load_file(pinned_profile)
        pinned_source = str(pinned_profile)

    def _resolve_profile(profile_path: str | None) -> AnyProfile:
        if pinned is not None:
            if profile_path is not None:
                raise ValueError(
                    f"This server is pinned to profile '{pinned.profile_id}' "
                    f"({pinned_source}) and it is authoritative; per-call "
                    "profile_path arguments are rejected. Omit profile_path, "
                    "or restart the server without --profile."
                )
            return pinned
        if profile_path is None:
            raise ValueError(
                "profile_path is required (this server was started without "
                "--profile, so every call must name a profile file)."
            )
        return loader.load_file(profile_path)

    def rmacd_evaluate(
        operation: str,
        target: str,
        classification: str | None = None,
        environment: str | None = None,
        profile_path: str | None = None,
    ) -> dict[str, Any]:
        """Evaluate an RMACD policy decision (read-only; never approves or mutates).

        Args:
            operation: RMACD operation: R (Read), M (Move), A (Add),
                C (Change), or D (Delete).
            target: The resource acted on (traceability only; the decision is
                target-agnostic).
            classification: Data classification tier (public, internal,
                confidential, restricted). Required for 3D and DC2D profiles.
            environment: Deployment environment (development, staging,
                production, disaster-recovery, sandbox).
            profile_path: Path to the RMACD profile JSON. Required unless the
                server was started with --profile, in which case it must be
                omitted (the pinned profile is authoritative).

        Returns the PolicyDecision as JSON: allowed, autonomy_level,
        requires_approval, requires_notification, blocked_reason,
        constraints_applied. The §12.5 immutable floor (no A/C/D on
        Restricted) is enforced regardless of profile contents.
        """
        profile = _resolve_profile(profile_path)
        op = _parse_operation(operation)
        tier = _parse_classification(classification) if classification is not None else None
        env = _parse_environment(environment) if environment is not None else None
        context = EvaluationContext(environment=env)
        decision = PolicyEvaluator(profile).evaluate(op, tier, context)
        result: dict[str, Any] = {
            "profile_id": profile.profile_id,
            "target": target,
        }
        result.update(json.loads(decision.model_dump_json()))
        return result

    def rmacd_validate_profile(
        profile_path: str | None = None,
        profile_json: str | None = None,
    ) -> dict[str, Any]:
        """Validate an RMACD profile against its JSON Schema.

        Args:
            profile_path: Path to a profile JSON file.
            profile_json: A profile as a JSON string (alternative to
                profile_path; pass exactly one). When the server is pinned
                via --profile, both may be omitted to validate the pinned
                profile file.

        Returns {"valid": bool, "errors": [str, ...]}. Purely a lint: it
        confers no policy authority and works on arbitrary documents even in
        pinned mode.
        """
        if profile_path is not None and profile_json is not None:
            raise ValueError("Pass either profile_path or profile_json, not both.")
        source: str | Path | None = profile_path
        if source is None and profile_json is None:
            if pinned_source is None:
                raise ValueError("Pass profile_path or profile_json.")
            source = pinned_source
        errors: list[str] = []
        try:
            if source is not None:
                ProfileValidator().validate_file(source)
            else:
                assert profile_json is not None
                ProfileValidator().validate(json.loads(profile_json))
        except SchemaValidationError as exc:
            errors = exc.errors or [str(exc)]
        except json.JSONDecodeError as exc:
            errors = [f"Invalid JSON: {exc}"]
        except OSError as exc:
            errors = [f"Cannot read profile: {exc}"]
        return {"valid": not errors, "errors": errors}

    def rmacd_matrix(profile_path: str | None = None) -> dict[str, Any]:
        """Return a profile's effective autonomy matrix (same data as `rmacd matrix`).

        Args:
            profile_path: Path to the RMACD profile JSON. Required unless the
                server was started with --profile, in which case it must be
                omitted (the pinned profile is authoritative).

        For 3D profiles: {classification: {R/M/A/C/D: autonomy}}. For 2D:
        {operation: autonomy}. For DC2D: {classification: autonomy}.
        """
        profile = _resolve_profile(profile_path)
        return {
            "profile_id": profile.profile_id,
            "model": profile.model,
            "matrix": PolicyEvaluator(profile).get_effective_autonomy_matrix(),
        }

    def rmacd_list_packs() -> dict[str, Any]:
        """List the governance packs built into the RMACD SDK.

        Returns {"count": N, "packs": [{"name", "version", "description",
        "rules"}, ...]} for every pack bundled under rmacd/packs/data/.
        """
        from rmacd.packs import builtin_pack_names, load_pack

        packs: list[dict[str, Any]] = []
        for name in builtin_pack_names():
            pack = load_pack(name)
            packs.append(
                {
                    "name": pack.pack,
                    "version": pack.version,
                    "description": pack.description,
                    "rules": len(pack.rules),
                }
            )
        return {"count": len(packs), "packs": packs}

    def rmacd_pack_info(name_or_path: str) -> dict[str, Any]:
        """Inspect one governance pack: metadata, rule count, signature status.

        Args:
            name_or_path: A built-in pack name (see rmacd_list_packs) or a
                path to a pack file (.json/.yaml/.yml).

        Signature status reports presence and content-hash integrity only;
        verifying the signature against a trusted key requires the key and is
        not exposed over MCP.
        """
        from rmacd.packs import load_pack

        pack = load_pack(name_or_path)
        provenance = (
            pack.provenance.model_dump(exclude_none=True) if pack.provenance else None
        )
        return {
            "name": pack.pack,
            "version": pack.version,
            "description": pack.description,
            "default_operation": pack.default_operation,
            "rule_count": len(pack.rules),
            "resolvers": [r.name for r in pack.resolvers],
            "provenance": provenance,
            "signature_status": {
                "signed": pack.signature is not None,
                "content_hash": pack.content_hash,
                "content_hash_valid": pack.verify_hash() if pack.content_hash else None,
            },
        }

    def rmacd_classify_bash(command: str) -> dict[str, Any]:
        """Classify a shell command line into its worst-case RMACD operation.

        Args:
            command: The shell command line to classify.

        ADVISORY ONLY: this is the SDK's deterministic keyword classifier
        (max operation across segments, sub-shells, and redirects; unknown
        binaries fail closed to Change). It informs governance, it is not
        the governance — enforcement always goes through a profile and the
        §12.5 floor.
        """
        from rmacd.registry.bash import classify_bash_command

        result = classify_bash_command(command)
        return {
            "operation": result.operation.value,
            "binary": result.binary,
            "detail": result.detail,
            "advisory": (
                "Deterministic keyword heuristic; advisory input only. "
                "Enforcement is decided by the bound profile and the §12.5 floor."
            ),
        }

    return {
        fn.__name__: fn
        for fn in (
            rmacd_evaluate,
            rmacd_validate_profile,
            rmacd_matrix,
            rmacd_list_packs,
            rmacd_pack_info,
            rmacd_classify_bash,
        )
    }


def create_server(pinned_profile: str | Path | None = None) -> FastMCP:
    """Create the FastMCP server with all six tools registered.

    Raises ImportError (with a pip-install hint) when the ``mcp`` package is
    not installed; raises ProfileLoadError when *pinned_profile* is invalid.
    """
    fastmcp_cls = _import_fastmcp()
    server = fastmcp_cls(SERVER_NAME, instructions=_INSTRUCTIONS)
    for fn in build_tools(pinned_profile).values():
        server.tool()(fn)
    return server


def serve(pinned_profile: str | Path | None = None) -> None:
    """Run the RMACD MCP server on stdio (blocks until the client disconnects)."""
    create_server(pinned_profile).run("stdio")


__all__ = ["SERVER_NAME", "build_tools", "create_server", "serve"]
