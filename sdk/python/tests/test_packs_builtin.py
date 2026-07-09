"""Phase 3 — built-in packs: schema validity, golden classifications, shell parity."""

from __future__ import annotations

import pytest

from rmacd.packs import (
    builtin_pack_names,
    capability_for,
    classify_call,
    clear_resolvers,
    is_valid_pack,
    load_pack,
    register_resolver,
)
from rmacd.registry.bash import classify_bash_command

EXPECTED_PACKS = {
    "shell", "kubectl", "aws", "gcloud", "az",
    "github", "gitlab", "sql", "filesystem",
    "jira", "confluence", "slack", "google-drive", "postgres",
    "boto3", "aws-api-mcp", "azure-mcp", "gcp-toolbox", "ms365",
    "aws-iam", "az-identity", "gcp-iam",
}


@pytest.fixture(autouse=True)
def _resolvers() -> None:
    clear_resolvers()
    tiered = lambda v, ctx: {"SEC": "restricted", "HR": "confidential"}.get(v, "internal")  # noqa: E731
    register_resolver("jira_project_tier", tiered)
    register_resolver("confluence_space_tier", tiered)
    register_resolver("azure_resource_tier", lambda v, ctx: "internal")
    register_resolver("aws_resource_tier", lambda v, ctx: "internal")
    yield
    clear_resolvers()


def test_all_expected_packs_present() -> None:
    assert EXPECTED_PACKS.issubset(set(builtin_pack_names()))


@pytest.mark.parametrize("name", sorted(EXPECTED_PACKS))
def test_every_pack_is_schema_valid(name: str) -> None:
    pack = load_pack(name)  # raises if invalid
    assert is_valid_pack(pack.to_dict()) is True


# (pack, tool, args, expected_operation, expected_tier)
GOLDEN: list[tuple[str, str, dict, str, str | None]] = [
    # shell
    ("shell", "bash", {"command": "ls -la"}, "R", "internal"),
    ("shell", "bash", {"command": "rm -rf /tmp/x"}, "D", "internal"),
    ("shell", "bash", {"command": "cp a b"}, "A", "internal"),
    ("shell", "bash", {"command": "cat /etc/shadow"}, "R", "confidential"),
    # kubectl
    ("kubectl", "kubectl", {"command": "get pods"}, "R", "internal"),
    ("kubectl", "kubectl", {"command": "delete pod web -n prod"}, "D", "confidential"),
    ("kubectl", "kubectl", {"command": "apply -f x.yaml"}, "C", "internal"),
    # aws CLI (verb-noun matched by prefix)
    ("aws", "aws", {"command": "ec2 describe-instances"}, "R", "internal"),
    ("aws", "aws", {"command": "s3 rm s3://b/k"}, "D", "internal"),
    ("aws", "aws", {"command": "s3 cp a s3://b"}, "A", "internal"),
    ("aws", "aws", {"command": "ec2 terminate-instances --instance-ids i-1"}, "D", "internal"),
    ("aws", "aws", {"command": "iam delete-user --user-name x"}, "D", "confidential"),
    # gcloud
    ("gcloud", "gcloud", {"command": "compute instances list"}, "R", "internal"),
    ("gcloud", "gcloud", {"command": "compute instances delete web"}, "D", "internal"),
    ("gcloud", "gcloud", {"command": "secrets list"}, "R", "confidential"),
    # az
    ("az", "az", {"command": "vm list"}, "R", "internal"),
    ("az", "az", {"command": "vm delete --name web"}, "D", "internal"),
    ("az", "az", {"command": "keyvault secret show --name x"}, "R", "confidential"),
    # github
    ("github", "gh", {"command": "pr list"}, "R", "internal"),
    ("github", "gh", {"command": "repo delete owner/x"}, "D", "internal"),
    ("github", "gh", {"command": "secret set NAME"}, "C", "confidential"),
    # gitlab
    ("gitlab", "glab", {"command": "mr list"}, "R", "internal"),
    ("gitlab", "glab", {"command": "issue delete 1"}, "D", "internal"),
    # sql (case-insensitive verbs)
    ("sql", "query", {"query": "SELECT * FROM orders"}, "R", "internal"),
    ("sql", "query", {"query": "DROP TABLE users"}, "D", "confidential"),
    ("sql", "query", {"query": "UPDATE accounts SET x=1"}, "C", "confidential"),
    ("sql", "query", {"query": "SELECT ssn FROM patients"}, "R", "restricted"),
    # filesystem (MCP-style + sensitive overlay)
    ("filesystem", "read_file", {"path": "/home/x/a.txt"}, "R", "internal"),
    ("filesystem", "delete_file", {"path": "/tmp/x"}, "D", "internal"),
    ("filesystem", "write_file", {"path": "/app/config"}, "C", "internal"),
    ("filesystem", "read_file", {"path": "/app/.env"}, "R", "restricted"),
    # jira (resolver)
    ("jira", "jira_get_issue", {"project_key": "ENG", "issue_key": "ENG-1"}, "R", "internal"),
    ("jira", "jira_delete_issue", {"project_key": "SEC", "issue_key": "SEC-1"}, "D", "restricted"),
    ("jira", "jira_update_issue", {"project_key": "FIN", "issue_key": "FIN-1"},
     "C", "confidential"),
    # confluence (resolver)
    ("confluence", "confluence_get_page", {"space_key": "ENG", "page_id": "1"}, "R", "internal"),
    ("confluence", "confluence_delete_page", {"space_key": "SEC", "page_id": "2"},
     "D", "restricted"),
    # slack (+ DM overlay)
    ("slack", "slack_post_message", {"channel_id": "C123"}, "A", "internal"),
    ("slack", "slack_delete_message", {"channel_id": "C123"}, "D", "internal"),
    ("slack", "slack_post_message", {"channel_id": "D999"}, "A", "confidential"),
    # google-drive
    ("google-drive", "gdrive_read_file", {"file_id": "f1"}, "R", "internal"),
    ("google-drive", "gdrive_delete_file", {"file_id": "f1"}, "D", "internal"),
    # postgres (meta + passthrough)
    ("postgres", "list_tables", {}, "R", "internal"),
    ("postgres", "query", {"sql": "SELECT 1"}, "R", "internal"),
    ("postgres", "query", {"sql": "DROP TABLE customers"}, "D", "confidential"),
    # boto3 (SDK delimiter)
    ("boto3", "aws_call", {"service": "s3", "operation": "delete_object", "params": {}},
     "D", "internal"),
    ("boto3", "aws_call", {"service": "iam", "operation": "create_user", "params": {}},
     "A", "confidential"),
    # aws-api-mcp (passthrough + docs)
    ("aws-api-mcp", "call_aws", {"cli_command": "s3 ls"}, "R", "internal"),
    ("aws-api-mcp", "call_aws", {"cli_command": "iam delete-user --user-name x"},
     "D", "confidential"),
    ("aws-api-mcp", "get_aws_documentation", {}, "R", "internal"),
    # azure-mcp (glob + keyvault overlay + cli passthrough)
    ("azure-mcp", "azmcp_storage_list", {"resource_group": "rg"}, "R", "internal"),
    ("azure-mcp", "azmcp_keyvault_secret_delete", {}, "D", "restricted"),
    ("azure-mcp", "azmcp_extension_az", {"command": "vm delete --name x"}, "D", "internal"),
    # gcp-toolbox
    ("gcp-toolbox", "execute_sql", {"sql": "SELECT 1"}, "R", "internal"),
    ("gcp-toolbox", "execute_sql", {"sql": "DELETE FROM users"}, "D", "confidential"),
    ("gcp-toolbox", "list_tables", {}, "R", "internal"),
    # ms365
    ("ms365", "get_message", {"id": "m1"}, "R", "confidential"),
    ("ms365", "delete_event", {"id": "e1"}, "D", "confidential"),
    ("ms365", "send_mail", {"id": "x"}, "A", "confidential"),
    # aws-iam (identity/secrets overlay on the aws CLI)
    ("aws-iam", "aws", {"command": "ec2 describe-instances"}, "R", "internal"),
    ("aws-iam", "aws", {"command": "iam list-users"}, "R", "confidential"),
    ("aws-iam", "aws", {"command": "iam delete-user --user-name x"}, "D", "restricted"),
    ("aws-iam", "aws", {"command": "iam attach-user-policy --user-name x --policy-arn a"},
     "C", "restricted"),
    ("aws-iam", "aws", {"command": "secretsmanager get-secret-value --secret-id db"},
     "R", "restricted"),
    # az-identity (Entra ID / RBAC / Key Vault overlay on the az CLI)
    ("az-identity", "az", {"command": "vm list"}, "R", "internal"),
    ("az-identity", "az", {"command": "role assignment create --role Owner --assignee a"},
     "A", "restricted"),
    ("az-identity", "az", {"command": "role definition delete --name x"}, "D", "restricted"),
    ("az-identity", "az", {"command": "keyvault secret show --name x"}, "R", "restricted"),
    ("az-identity", "az", {"command": "ad user list"}, "R", "confidential"),
    # gcp-iam (Cloud IAM / Secret Manager / KMS overlay on the gcloud CLI)
    ("gcp-iam", "gcloud", {"command": "compute instances list"}, "R", "internal"),
    ("gcp-iam", "gcloud", {"command": "iam service-accounts list"}, "R", "confidential"),
    ("gcp-iam", "gcloud",
     {"command": "projects add-iam-policy-binding p --member=user:a --role=roles/owner"},
     "A", "restricted"),
    ("gcp-iam", "gcloud", {"command": "secrets versions access latest --secret=db"},
     "C", "restricted"),
    ("gcp-iam", "gcloud", {"command": "kms keys versions destroy v --key=k"}, "D", "restricted"),
]


@pytest.mark.parametrize("name,tool,args,exp_op,exp_tier", GOLDEN)
def test_golden_classifications(
    name: str, tool: str, args: dict, exp_op: str, exp_tier: str | None
) -> None:
    pack = load_pack(name)
    result = classify_call(pack, tool, args)
    assert result.operation == exp_op, f"{name}:{tool} op"
    assert result.tier == exp_tier, f"{name}:{tool} tier"


@pytest.mark.parametrize("name,tool", [
    ("sql", "query"), ("boto3", "aws_call"), ("aws", "aws"),
    ("aws-api-mcp", "call_aws"), ("postgres", "query"), ("shell", "bash"),
])
def test_passthrough_packs_have_worst_case_ceiling(name: str, tool: str) -> None:
    assert capability_for(load_pack(name), tool) == ["R", "M", "A", "C", "D"]


# --- shell pack parity with the bash.py engine on a representative subset ------
_PARITY = [
    "ls -la", "cat /etc/hosts", "grep foo bar.txt", "cp a b", "mv a b",
    "mkdir d", "touch f", "rm file", "rmdir d", "chmod 600 f", "chown u f",
    "sudo rm -rf /tmp/x", "cat access.log | grep error", "head -n5 f", "wc -l f",
]


@pytest.mark.parametrize("command", _PARITY)
def test_shell_pack_parity_with_bash_engine(command: str) -> None:
    pack = load_pack("shell")
    engine_op = classify_call(pack, "bash", {"command": command}).operation
    bash_op = classify_bash_command(command).operation.value
    assert engine_op == bash_op, f"{command!r}: pack={engine_op} bash={bash_op}"
