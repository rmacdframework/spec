"""Phase 1 — declarative classification engine."""

from __future__ import annotations

import pytest

from rmacd.packs import (
    DeclarativeClassifier,
    GovernancePack,
    capability_for,
    classify_call,
    clear_resolvers,
    register_resolver,
)
from rmacd.packs.engine import ResolverContext
from rmacd.registry.bash import classify_bash_command


@pytest.fixture(autouse=True)
def _clean_resolvers() -> None:
    clear_resolvers()
    yield
    clear_resolvers()


# --- a small MCP-style pack (verb in tool name) -------------------------------
JIRA_PACK = GovernancePack.from_dict(
    {
        "pack": "jira",
        "version": "1.0.0",
        "default_operation": "C",
        "resolvers": [
            {"name": "jira_project_tier", "fail_closed_default": "confidential"}
        ],
        "rules": [
            {
                "id": "jira-read",
                "when": {"tool": ["jira_search", "jira_get_*", "jira_list_*"]},
                "classify": {
                    "operation": "R",
                    "tier": {
                        "resolver": "jira_project_tier",
                        "from": "project_key",
                        "default": "internal",
                    },
                    "target": "jira://{project_key}/{issue_key}",
                },
            },
            {
                "id": "jira-delete",
                "when": {"tool": "jira_delete_issue"},
                "classify": {"operation": "D", "tier": "confidential"},
            },
        ],
    }
)


def test_mcp_glob_and_literal_operation() -> None:
    r = classify_call(JIRA_PACK, "jira_get_issue", {"project_key": "ENG", "issue_key": "ENG-1"})
    assert r.operation == "R"
    assert r.tier == "confidential"  # no resolver registered -> fail-closed default
    assert r.target == "jira://ENG/ENG-1"
    assert r.matched_rule_ids == ["jira-read"]


def test_resolver_used_when_registered() -> None:
    register_resolver("jira_project_tier", lambda value, ctx: "internal")
    r = classify_call(JIRA_PACK, "jira_search", {"project_key": "ENG"})
    assert r.tier == "internal"
    assert r.resolver_lookups[0].failed is False
    assert r.resolver_lookups[0].result == "internal"


def test_resolver_failure_is_fail_closed_and_recorded() -> None:
    def boom(value: str, ctx: ResolverContext) -> str:
        raise RuntimeError("cmdb down")

    register_resolver("jira_project_tier", boom)
    r = classify_call(JIRA_PACK, "jira_search", {"project_key": "ENG"})
    assert r.tier == "confidential"  # fail_closed_default
    assert r.resolver_lookups[0].failed is True


def test_unmatched_tool_falls_back_to_pack_default() -> None:
    r = classify_call(JIRA_PACK, "totally_unknown_tool", {})
    assert r.operation == "C"  # default_operation
    assert r.tier is None
    assert r.matched_rule_ids == []


def test_declarative_classifier_matches_tool_classifier_protocol() -> None:
    clf = DeclarativeClassifier(JIRA_PACK, "jira_delete_issue")
    op, tier, target = clf({"project_key": "SEC", "issue_key": "SEC-1"})
    assert (op, tier) == ("D", "confidential")


# --- CLI-style pack with verb_table + pattern_map -----------------------------
KUBECTL_PACK = GovernancePack.from_dict(
    {
        "pack": "kubectl",
        "version": "1.0.0",
        "default_operation": "C",
        "rules": [
            {
                "id": "kubectl",
                "when": {"tool": "kubectl"},
                "parse": {"arg": "command", "strip_wrappers": ["sudo", "env"]},
                "verb_table": {
                    "get": "R",
                    "describe": "R",
                    "apply": "C",
                    "scale": "C",
                    "create": "A",
                    "delete": "D",
                },
                "default": "C",
                "tier": {
                    "pattern_map": [
                        {"arg_regex": {"arg": "command", "pattern": r"-n\s+prod"},
                         "tier": "confidential"}
                    ],
                    "default": "internal",
                },
                "target": "k8s://{command}",
            }
        ],
    }
)


@pytest.mark.parametrize(
    "command,expected_op,expected_tier",
    [
        ("get pods", "R", "internal"),
        ("delete pod web -n prod", "D", "confidential"),
        ("sudo apply -f x.yaml", "C", "internal"),
        ("create deployment web", "A", "internal"),
        ("rollout status", "C", "internal"),  # unknown verb -> default C
    ],
)
def test_verb_table_and_pattern_map(command: str, expected_op: str, expected_tier: str) -> None:
    r = classify_call(KUBECTL_PACK, "kubectl", {"command": command})
    assert r.operation == expected_op
    assert r.tier == expected_tier


def test_max_operation_over_compound_command() -> None:
    # A pipeline containing a delete must classify as Delete (worst-case).
    r = classify_call(KUBECTL_PACK, "kubectl", {"command": "get pods && delete pod web"})
    assert r.operation == "D"


# --- SDK style: delimiter split (boto3) ---------------------------------------
BOTO3_PACK = GovernancePack.from_dict(
    {
        "pack": "boto3",
        "version": "1.0.0",
        "default_operation": "C",
        "rules": [
            {
                "id": "boto3-call",
                "when": {"tool": "aws_call"},
                "parse": {"arg": "operation", "delimiter": "_", "token": "first"},
                "verb_table": {
                    "describe": "R", "get": "R", "list": "R",
                    "create": "A", "put": "C", "update": "C",
                    "delete": "D", "terminate": "D",
                },
                "default": "C",
                "target": "aws://{service}/{operation}",
                "capability": ["R", "M", "A", "C", "D"],
            }
        ],
    }
)


@pytest.mark.parametrize(
    "operation,expected",
    [
        ("delete_object", "D"),
        ("describe_instances", "R"),
        ("put_object", "C"),
        ("create_bucket", "A"),
        ("batch_write_item", "C"),  # compound prefix unmatched -> default C
    ],
)
def test_boto3_leading_verb_token(operation: str, expected: str) -> None:
    r = classify_call(BOTO3_PACK, "aws_call", {"service": "s3", "operation": operation})
    assert r.operation == expected


def test_passthrough_capability_ceiling() -> None:
    assert capability_for(BOTO3_PACK, "aws_call") == ["R", "M", "A", "C", "D"]
    assert capability_for(BOTO3_PACK, "some_other_tool") is None


# --- cross-rule combination: tier overlay -------------------------------------
AZURE_PACK = GovernancePack.from_dict(
    {
        "pack": "azure-mcp",
        "version": "1.0.0",
        "default_operation": "C",
        "rules": [
            {
                "id": "az-keyvault-tier",
                "when": {"tool": "azmcp_keyvault_*"},
                "classify": {"tier": "restricted"},  # tier only, no operation
            },
            {
                "id": "az-delete",
                "when": {"tool": "azmcp_*_delete"},
                "classify": {"operation": "D", "tier": "internal"},
            },
            {
                "id": "az-read",
                "when": {"tool": "azmcp_*_list"},
                "classify": {"operation": "R", "tier": "internal"},
            },
        ],
    }
)


def test_tier_overlay_raises_tier_without_changing_operation() -> None:
    # keyvault delete matches BOTH az-delete (op D) and az-keyvault-tier (restricted)
    r = classify_call(AZURE_PACK, "azmcp_keyvault_secret_delete", {})
    assert r.operation == "D"
    assert r.tier == "restricted"  # most-sensitive across rules
    assert set(r.matched_rule_ids) == {"az-keyvault-tier", "az-delete"}


def test_non_keyvault_delete_keeps_internal_tier() -> None:
    r = classify_call(AZURE_PACK, "azmcp_storage_delete", {})
    assert r.operation == "D"
    assert r.tier == "internal"


# --- regex tool match + arg predicates ----------------------------------------
def test_regex_tool_match_and_arg_present() -> None:
    pack = GovernancePack.from_dict(
        {
            "pack": "rx",
            "version": "1.0.0",
            "rules": [
                {
                    "id": "only-with-id",
                    "when": {"tool": "/svc_.*/", "arg_present": "id"},
                    "operation": "D",
                    "tier": "restricted",
                }
            ],
        }
    )
    assert classify_call(pack, "svc_delete", {"id": "x"}).operation == "D"
    # arg_present fails -> rule doesn't apply -> pack default
    assert classify_call(pack, "svc_delete", {}).operation == "C"
    # regex doesn't match
    assert classify_call(pack, "other", {"id": "x"}).matched_rule_ids == []


# --- parity with bash.py on a curated subset ----------------------------------
SHELL_PARITY_PACK = GovernancePack.from_dict(
    {
        "pack": "shell-subset",
        "version": "1.0.0",
        "default_operation": "C",
        "rules": [
            {
                "id": "shell",
                "when": {"tool": "bash"},
                "parse": {"arg": "command", "strip_wrappers": ["sudo", "env", "nice"]},
                "verb_table": {
                    "ls": "R", "cat": "R", "grep": "R", "find": "R", "echo": "R",
                    "head": "R", "tail": "R", "wc": "R", "stat": "R", "pwd": "R",
                    "cp": "A", "mv": "M",
                    "mkdir": "A", "touch": "A",
                    "rm": "D", "rmdir": "D",
                },
                "default": "C",
            }
        ],
    }
)

# Commands where the generic flat-token engine and bash.py agree by construction.
_PARITY_COMMANDS = [
    "ls -la",
    "cat /etc/hosts",
    "grep foo bar.txt",
    "cp a b",
    "mv a b",
    "mkdir newdir",
    "touch f",
    "rm file",
    "rmdir d",
    "sudo rm -rf /tmp/x",
    "cat access.log | grep error",
]


@pytest.mark.parametrize("command", _PARITY_COMMANDS)
def test_shell_pack_parity_with_bash_classifier(command: str) -> None:
    engine_op = classify_call(SHELL_PARITY_PACK, "bash", {"command": command}).operation
    bash_op = classify_bash_command(command).operation.value
    assert engine_op == bash_op, f"{command!r}: engine={engine_op} bash={bash_op}"
