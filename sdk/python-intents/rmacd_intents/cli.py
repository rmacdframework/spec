"""``rmacd-intents`` — submit, decide, transition, log.

Configuration is one JSON file::

    {
      "store": "./intent-store",
      "policy_version": "corp-policy-2026.10",
      "implementation_level": "L1",
      "profiles": {
        "spiffe://corp/ns/agents/devops-agent-007": "profiles/devops-3d.json"
      },
      "accountable": {
        "spiffe://corp/ns/agents/devops-agent-007": ["platform-team@company.com"]
      },
      "default_profile": "profiles/observer-3d.json",
      "weights": {"version": "default-1.0.0"}
    }

``profiles`` maps an ``actor.authorization`` to the profile it is bound to;
``accountable`` optionally restricts which ``on_behalf_of`` values resolve for
it. An authorization not in the map is unresolved and fails closed (N-6)
against ``default_profile``, or is rejected when there is none (N-13).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from rmacd import ProfileLoader

from .actors import StaticActorResolver
from .grading import Engine
from .models import GrantStatus, Rejection
from .store import JSONLStore
from .weights import WeightTable


def load_engine(config_path: Path) -> Engine:
    cfg: dict[str, Any] = json.loads(config_path.read_text(encoding="utf-8"))
    base = config_path.parent
    resolver = StaticActorResolver.from_paths(
        {auth: base / p for auth, p in cfg.get("profiles", {}).items()},
        {auth: set(v) for auth, v in cfg.get("accountable", {}).items()},
    )
    default_profile = None
    if cfg.get("default_profile"):
        default_profile = ProfileLoader().load_file(base / cfg["default_profile"])
    return Engine(
        JSONLStore(base / cfg.get("store", "intent-store")),
        resolver,
        weights=WeightTable.model_validate(cfg.get("weights", {})),
        policy_version=cfg.get("policy_version", "unversioned"),
        matrix_version=cfg.get("matrix_version", "1.4"),
        implementation_level=cfg.get("implementation_level", "L3"),
        default_profile=default_profile,
    )


def _emit(obj: Any) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="rmacd-intents", description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", "-c", type=Path, default=Path("rmacd-intents.json"))
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("submit", help="validate and grade an intent; prints the decision record")
    s.add_argument("file", type=Path, help="intent JSON, or - for stdin")

    d = sub.add_parser("decide", help="attach a human decision to a decision record")
    d.add_argument("decision_id")
    d.add_argument("--outcome", required=True,
                   choices=["approved", "approved_with_modifications", "deferred", "denied"])
    d.add_argument("--approver", required=True)
    d.add_argument("--note")

    t = sub.add_parser("transition", help="move a grant through its lifecycle")
    t.add_argument("intent_id")
    t.add_argument("--to", required=True, choices=[s.value for s in GrantStatus])
    t.add_argument("--by", required=True)

    rc = sub.add_parser("reconcile", help="join an Appendix C.6 audit trail to the decision log")
    rc.add_argument("audit_jsonl", type=Path)
    rc.add_argument("--undeclared", choices=["demote", "report"], default="demote",
                    help="what an executed action with no intent_id does to its agent (N-48)")

    ld = sub.add_parser("lift-demotion", help="end an actor's demotion (N-77)")
    ld.add_argument("actor_id")
    ld.add_argument("--by", required=True)

    lg = sub.add_parser("log", help="print a log")
    lg.add_argument("which", choices=["intents", "adjudications"])

    sub.add_parser("version", help="print the engine version")

    args = ap.parse_args(argv)
    if args.cmd == "version":
        from . import __version__

        print(__version__)
        return 0

    engine = load_engine(args.config)
    if args.cmd == "submit":
        raw = sys.stdin.buffer.read() if str(args.file) == "-" else args.file.read_bytes()
        result = engine.submit(raw)
        if isinstance(result, Rejection):
            _emit({"rejected": True, "intent_id": result.intent_id, "failure": result.failure})
            return 2
        _emit(result.to_json_dict())
        return 0
    if args.cmd == "decide":
        try:
            disp = engine.decide(args.decision_id, args.outcome, args.approver, args.note)
        except (KeyError, ValueError) as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 2
        _emit(disp.model_dump(mode="json", exclude_none=True))
        return 0
    if args.cmd == "transition":
        try:
            entry = engine.transition(args.intent_id, GrantStatus(args.to), args.by)
        except (KeyError, ValueError) as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 2
        _emit(entry.to_json_dict())
        return 0
    if args.cmd == "reconcile":
        from .reconcile import Reconciler

        report = Reconciler(engine).run(args.audit_jsonl, undeclared=args.undeclared)
        _emit(report.__dict__)
        return 0
    if args.cmd == "lift-demotion":
        try:
            entry = engine.lift_demotion(args.actor_id, args.by)
        except ValueError as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 2
        _emit(entry.to_json_dict())
        return 0
    if args.cmd == "log":
        entries = (
            engine.store.intent_entries()
            if args.which == "intents"
            else engine.store.adjudication_entries()
        )
        for e in entries:
            print(json.dumps(e.to_json_dict(), ensure_ascii=False))
        return 0
    return 1  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
