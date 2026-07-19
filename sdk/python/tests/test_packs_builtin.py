"""Phase 3 — built-in packs: schema validity, golden classifications, shell parity."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from rmacd import PolicyEnforcer, RMACDProhibitedError
from rmacd.approval import AutoApproveGateway
from rmacd.models import DataClassification as DC
from rmacd.models import Operation as Op
from rmacd.models import Profile3D
from rmacd.packs import (
    builtin_pack_names,
    capability_for,
    classify_call,
    clear_resolvers,
    is_valid_pack,
    load_pack,
    load_packs,
    register_resolver,
)
from rmacd.registry.bash import classify_bash_command

EXPECTED_PACKS = {
    "shell", "kubectl", "aws", "gcloud", "az",
    "github", "gitlab", "sql", "filesystem",
    "jira", "confluence", "slack", "google-drive", "postgres",
    "boto3", "aws-api-mcp", "azure-mcp", "gcp-toolbox", "ms365",
    "aws-iam", "az-identity", "gcp-iam",
    "git", "gh", "docker", "terraform", "npm", "pip-uv", "make",
    "servicenow", "helm", "ssh-transfer", "stripe", "vault",
}


@pytest.fixture(autouse=True)
def _resolvers() -> Iterator[None]:
    clear_resolvers()
    tiered = lambda v, ctx: {"SEC": "restricted", "HR": "confidential"}.get(v, "internal")  # noqa: E731
    register_resolver("jira_project_tier", tiered)
    register_resolver("confluence_space_tier", tiered)
    register_resolver("azure_resource_tier", lambda v, ctx: "internal")
    register_resolver("aws_resource_tier", lambda v, ctx: "internal")
    register_resolver(
        "servicenow_table_tier",
        lambda v, ctx: {"sn_hr_core_case": "confidential"}.get(v, "internal"),
    )
    yield
    clear_resolvers()


def test_all_expected_packs_present() -> None:
    assert EXPECTED_PACKS.issubset(set(builtin_pack_names()))


def test_builtin_pack_count() -> None:
    # 22 packs through SDK 0.12.0 + the 7 developer-toolchain packs (c3)
    # + the 5 enterprise packs (c3c: servicenow, helm, ssh-transfer, stripe, vault).
    assert len(builtin_pack_names()) == 34


@pytest.mark.parametrize("name", sorted(EXPECTED_PACKS))
def test_every_pack_is_schema_valid(name: str) -> None:
    pack = load_pack(name)  # raises if invalid
    assert is_valid_pack(pack.to_dict()) is True


# (pack, tool, args, expected_operation, expected_tier)
GOLDEN: list[tuple[str, str, dict[str, Any], str, str | None]] = [
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
    # git (direct tool + shell passthrough; destructive/history-rewrite -> restricted)
    ("git", "git", {"command": "status"}, "R", "internal"),
    ("git", "bash", {"command": "git log --oneline"}, "R", "internal"),
    ("git", "bash", {"command": "git commit -m msg"}, "A", "internal"),
    ("git", "bash", {"command": "git pull origin main"}, "C", "internal"),
    ("git", "bash", {"command": "git push origin main"}, "C", "confidential"),
    ("git", "bash", {"command": "git push --force origin main"}, "C", "restricted"),
    ("git", "git", {"command": "branch -D feature"}, "D", "restricted"),
    ("git", "bash", {"command": "git reset --hard HEAD~1"}, "C", "restricted"),
    ("git", "bash", {"command": "git clean -fd"}, "D", "restricted"),
    ("git", "bash", {"command": "git remote set-url origin git@x:y/z"}, "C", "confidential"),
    ("git", "bash", {"command": "git credential fill"}, "C", "restricted"),
    # gh (reads internal; merge/release confidential; repo/secret/auth -> restricted)
    ("gh", "gh", {"command": "pr list"}, "R", "internal"),
    ("gh", "bash", {"command": "gh pr create --title x"}, "A", "internal"),
    ("gh", "bash", {"command": "gh pr merge 42"}, "C", "confidential"),
    ("gh", "bash", {"command": "gh release create v1.0.0"}, "C", "confidential"),
    ("gh", "bash", {"command": "gh repo delete owner/x --yes"}, "D", "restricted"),
    ("gh", "gh", {"command": "secret set NPM_TOKEN"}, "C", "restricted"),
    ("gh", "bash", {"command": "gh auth token"}, "R", "restricted"),
    # docker (lifecycle Change; removals Delete-confidential; login/privileged restricted)
    ("docker", "docker", {"command": "ps -a"}, "R", "internal"),
    ("docker", "bash", {"command": "docker build -t app ."}, "A", "internal"),
    ("docker", "bash", {"command": "docker run -d nginx"}, "C", "internal"),
    ("docker", "bash", {"command": "docker system prune -af"}, "D", "confidential"),
    ("docker", "bash", {"command": "docker volume rm data"}, "D", "confidential"),
    ("docker", "bash", {"command": "docker login registry.example.com"}, "C", "restricted"),
    ("docker", "bash", {"command": "docker push registry/app:1.0"}, "C", "restricted"),
    ("docker", "bash", {"command": "docker run --privileged -v /:/host alpine"},
     "C", "restricted"),
    # terraform (plan reads confidential; apply/destroy/state surgery restricted)
    ("terraform", "terraform", {"command": "validate"}, "R", "internal"),
    ("terraform", "bash", {"command": "terraform plan"}, "R", "confidential"),
    ("terraform", "bash", {"command": "terraform init"}, "A", "internal"),
    ("terraform", "bash", {"command": "terraform apply -auto-approve"}, "C", "restricted"),
    ("terraform", "bash", {"command": "terraform destroy"}, "D", "restricted"),
    ("terraform", "terraform", {"command": "state list"}, "R", "confidential"),
    ("terraform", "bash", {"command": "terraform state rm aws_instance.web"},
     "D", "restricted"),
    ("terraform", "tofu", {"command": "workspace delete staging"}, "D", "restricted"),
    # npm (+ npx; registry/publish/token/auth surface -> restricted)
    ("npm", "npm", {"command": "outdated"}, "R", "internal"),
    ("npm", "bash", {"command": "npm audit"}, "R", "internal"),
    ("npm", "bash", {"command": "npm audit fix"}, "C", "internal"),
    ("npm", "bash", {"command": "npm install express"}, "A", "internal"),
    ("npm", "bash", {"command": "npm uninstall express"}, "D", "internal"),
    ("npm", "bash", {"command": "npm publish"}, "C", "restricted"),
    ("npm", "bash", {"command": "npm token create"}, "C", "restricted"),
    ("npm", "bash", {"command": "npm deprecate pkg@1.0.0 msg"}, "C", "restricted"),
    ("npm", "npx", {"command": "create-react-app my-app"}, "C", "internal"),
    # pip-uv (pip/pip3/uv/twine; publishing and credentials -> restricted)
    ("pip-uv", "pip", {"command": "list"}, "R", "internal"),
    ("pip-uv", "uv", {"command": "lock"}, "R", "internal"),
    ("pip-uv", "bash", {"command": "pip install requests"}, "A", "internal"),
    ("pip-uv", "bash", {"command": "uv sync"}, "A", "internal"),
    ("pip-uv", "bash", {"command": "pip uninstall requests -y"}, "D", "internal"),
    ("pip-uv", "bash", {"command": "uv publish"}, "C", "restricted"),
    ("pip-uv", "bash", {"command": "twine upload dist/*"}, "C", "restricted"),
    ("pip-uv", "bash", {"command": "pip config set global.index-url https://x"},
     "C", "confidential"),
    # make (opaque recipes fail closed to Change; dry-run Read; clean Delete)
    ("make", "make", {"command": "build"}, "C", "internal"),
    ("make", "bash", {"command": "make -n all"}, "R", "internal"),
    ("make", "bash", {"command": "make clean"}, "D", "internal"),
    ("make", "bash", {"command": "make distclean"}, "D", "internal"),
    ("make", "bash", {"command": "make install"}, "C", "confidential"),
    ("make", "make", {"command": "uninstall"}, "D", "confidential"),
    # vault (§12.5 showcase: everything >= confidential; secret reads restricted)
    ("vault", "vault", {"command": "status"}, "R", "confidential"),
    ("vault", "bash", {"command": "vault token lookup"}, "R", "confidential"),
    ("vault", "vault", {"command": "kv get secret/x"}, "R", "restricted"),
    ("vault", "bash", {"command": "vault read secret/data/app"}, "R", "restricted"),
    ("vault", "bash", {"command": "vault kv put secret/db pass=x"}, "C", "restricted"),
    ("vault", "bash", {"command": "vault kv destroy -versions=1 secret/db"},
     "D", "restricted"),
    ("vault", "bash", {"command": "vault secrets disable kv/"}, "D", "restricted"),
    ("vault", "bash", {"command": "vault policy write admin policy.hcl"}, "C", "restricted"),
    ("vault", "bash", {"command": "vault auth enable userpass"}, "C", "restricted"),
    ("vault", "bash", {"command": "vault token create -policy=admin"}, "C", "restricted"),
    ("vault", "bash", {"command": "vault operator seal"}, "C", "restricted"),
    # helm (install Add-confidential; uninstall Delete-restricted; registry/plugin restricted)
    ("helm", "helm", {"command": "list -A"}, "R", "internal"),
    ("helm", "bash", {"command": "helm status my-release"}, "R", "internal"),
    ("helm", "bash", {"command": "helm repo add bitnami https://charts.bitnami.com"},
     "A", "internal"),
    ("helm", "bash", {"command": "helm install my-release bitnami/nginx"},
     "A", "confidential"),
    ("helm", "bash", {"command": "helm upgrade my-release bitnami/nginx"},
     "C", "confidential"),
    ("helm", "helm", {"command": "rollback my-release 1"}, "C", "confidential"),
    ("helm", "bash", {"command": "helm uninstall prod-release"}, "D", "restricted"),
    ("helm", "bash", {"command": "helm registry login registry.example.com"},
     "C", "restricted"),
    ("helm", "bash", {"command": "helm plugin install https://github.com/x/y"},
     "A", "restricted"),
    # ssh-transfer (canonical Move pack; rsync --delete Delete; keys restricted)
    ("ssh-transfer", "rsync", {"command": "-a src host:dst"}, "M", "confidential"),
    ("ssh-transfer", "bash", {"command": "rsync -a src host:dst"}, "M", "confidential"),
    ("ssh-transfer", "bash", {"command": "scp file.txt host:/tmp/"}, "M", "confidential"),
    ("ssh-transfer", "bash", {"command": "rsync -a --delete src/ host:dst/"},
     "D", "confidential"),
    ("ssh-transfer", "bash", {"command": "ssh host systemctl restart app"},
     "C", "confidential"),
    ("ssh-transfer", "ssh", {"command": "host uptime"}, "C", "confidential"),
    ("ssh-transfer", "bash", {"command": "ssh-keygen -t ed25519"}, "C", "restricted"),
    ("ssh-transfer", "ssh-copy-id", {"command": "user@host"}, "C", "restricted"),
    # stripe (payment data never internal; money movement restricted; test mode internal)
    ("stripe", "stripe", {"command": "customers list"}, "R", "confidential"),
    ("stripe", "bash", {"command": "stripe charges retrieve ch_123"}, "R", "confidential"),
    ("stripe", "bash", {"command": "stripe customers create --email a@b.c"},
     "A", "confidential"),
    ("stripe", "bash", {"command": "stripe subscriptions update sub_1 --price p"},
     "C", "confidential"),
    ("stripe", "bash", {"command": "stripe refunds create --charge ch_1"},
     "C", "restricted"),
    ("stripe", "bash", {"command": "stripe refunds list"}, "R", "restricted"),
    ("stripe", "bash", {"command": "stripe payouts create --amount 100"},
     "C", "restricted"),
    ("stripe", "stripe", {"command": "listen --forward-to localhost:4242"},
     "R", "internal"),
    ("stripe", "bash", {"command": "stripe trigger payment_intent.succeeded"},
     "A", "internal"),
    ("stripe", "bash", {"command": "stripe login"}, "C", "restricted"),
    # servicenow (MCP-style; change approval is a human act -> restricted)
    ("servicenow", "get_record", {"table": "incident", "sys_id": "abc"}, "R", "internal"),
    ("servicenow", "get_record", {"table": "sn_hr_core_case", "sys_id": "abc"},
     "R", "confidential"),
    ("servicenow", "create_incident", {"short_description": "x"}, "A", "internal"),
    ("servicenow", "resolve_incident", {"number": "INC0001"}, "C", "confidential"),
    ("servicenow", "create_change_request", {"short_description": "x"},
     "A", "confidential"),
    ("servicenow", "approve_change", {"number": "CHG0001"}, "C", "restricted"),
    ("servicenow", "delete_record", {"table": "cmdb_ci", "sys_id": "abc"},
     "D", "restricted"),
]


@pytest.mark.parametrize("name,tool,args,exp_op,exp_tier", GOLDEN)
def test_golden_classifications(
    name: str, tool: str, args: dict[str, Any], exp_op: str, exp_tier: str | None
) -> None:
    pack = load_pack(name)
    result = classify_call(pack, tool, args)
    assert result.operation == exp_op, f"{name}:{tool} op"
    assert result.tier == exp_tier, f"{name}:{tool} tier"


@pytest.mark.parametrize("name,tool", [
    ("sql", "query"), ("boto3", "aws_call"), ("aws", "aws"),
    ("aws-api-mcp", "call_aws"), ("postgres", "query"), ("shell", "bash"),
    ("git", "git"), ("git", "bash"), ("gh", "gh"), ("docker", "docker"),
    ("terraform", "terraform"), ("npm", "npm"), ("pip-uv", "uv"), ("make", "make"),
    ("vault", "vault"), ("vault", "bash"), ("helm", "helm"), ("stripe", "stripe"),
    ("ssh-transfer", "ssh"), ("ssh-transfer", "rsync"),
])
def test_passthrough_packs_have_worst_case_ceiling(name: str, tool: str) -> None:
    assert capability_for(load_pack(name), tool) == ["R", "M", "A", "C", "D"]


# --- c3 acceptance: restricted-tier ops hit the §12.5 floor through bash -------
def _dev_profile() -> Profile3D:
    """A permissive 3D profile *without* Change/Delete on restricted."""
    return Profile3D(
        profile_id="rmacd-3d-devtools",
        profile_name="Dev Tools",
        model="three-dimensional",
        version="1.0",
        permissions={
            DC.PUBLIC: [Op.READ, Op.MOVE, Op.ADD, Op.CHANGE, Op.DELETE],
            DC.INTERNAL: [Op.READ, Op.MOVE, Op.ADD, Op.CHANGE, Op.DELETE],
            DC.CONFIDENTIAL: [Op.READ, Op.MOVE, Op.ADD, Op.CHANGE, Op.DELETE],
            DC.RESTRICTED: [Op.READ],
        },
    )


def test_git_force_push_via_bash_is_floor_blocked() -> None:
    enforcer = PolicyEnforcer(
        profile=_dev_profile(), agent_id="agent-1", registry=load_packs(["git"]),
        approval_gateway=AutoApproveGateway(),
    )
    # An ordinary push (Change on confidential) is permitted by this profile...
    decision = enforcer.enforce_tool_call("bash", {"command": "git push origin main"})
    assert decision.allowed is True
    assert decision.operation == Op.CHANGE
    assert decision.data_classification == DC.CONFIDENTIAL
    # ...but a force push resolves to restricted and hits the immutable floor.
    with pytest.raises(RMACDProhibitedError):
        enforcer.enforce_tool_call("bash", {"command": "git push --force origin main"})


@pytest.mark.parametrize("pack,tool,args", [
    ("git", "bash", {"command": "git push --force origin main"}),
    ("gh", "bash", {"command": "gh repo delete owner/x --yes"}),
    ("docker", "bash", {"command": "docker login registry.example.com"}),
    ("terraform", "bash", {"command": "terraform apply -auto-approve"}),
    ("npm", "bash", {"command": "npm publish"}),
    ("pip-uv", "bash", {"command": "twine upload dist/*"}),
])
def test_devtool_restricted_ops_floor_blocked_through_bash(
    pack: str, tool: str, args: dict[str, str]
) -> None:
    enforcer = PolicyEnforcer(
        profile=_dev_profile(), agent_id="agent-1", registry=load_packs([pack]),
        approval_gateway=AutoApproveGateway(),
    )
    with pytest.raises(RMACDProhibitedError):
        enforcer.enforce_tool_call(tool, args)


# --- c3c acceptance: enterprise packs (servicenow/helm/ssh-transfer/stripe/vault)
def _enterprise_enforcer(pack: str) -> PolicyEnforcer:
    return PolicyEnforcer(
        profile=_dev_profile(), agent_id="agent-1", registry=load_packs([pack]),
        approval_gateway=AutoApproveGateway(),
    )


def test_vault_secret_read_is_read_on_restricted() -> None:
    """`vault kv get secret/x` -> Read on restricted: profile-gated, not floor-blocked."""
    decision = _enterprise_enforcer("vault").enforce_tool_call(
        "bash", {"command": "vault kv get secret/x"}
    )
    assert decision.allowed is True
    assert decision.operation == Op.READ
    assert decision.data_classification == DC.RESTRICTED


def test_rsync_transfer_is_move() -> None:
    """`rsync -a src host:dst` -> Move on confidential (the canonical Move pack)."""
    decision = _enterprise_enforcer("ssh-transfer").enforce_tool_call(
        "bash", {"command": "rsync -a src host:dst"}
    )
    assert decision.allowed is True
    assert decision.operation == Op.MOVE
    assert decision.data_classification == DC.CONFIDENTIAL


@pytest.mark.parametrize("pack,tool,args", [
    ("stripe", "bash", {"command": "stripe refunds create --charge ch_1"}),
    ("helm", "bash", {"command": "helm uninstall prod-release"}),
    ("vault", "bash", {"command": "vault kv put secret/db pass=x"}),
    ("vault", "bash", {"command": "vault policy write admin policy.hcl"}),
    ("ssh-transfer", "bash", {"command": "ssh-keygen -t ed25519"}),
    ("servicenow", "approve_change", {"number": "CHG0001"}),
    ("servicenow", "delete_record", {"table": "cmdb_ci", "sys_id": "abc"}),
])
def test_enterprise_restricted_ops_floor_blocked(
    pack: str, tool: str, args: dict[str, str]
) -> None:
    with pytest.raises(RMACDProhibitedError):
        _enterprise_enforcer(pack).enforce_tool_call(tool, args)


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
