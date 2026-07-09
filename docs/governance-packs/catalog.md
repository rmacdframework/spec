# Governance Pack Catalog

> The built-in governance packs that ship with `rmacd-framework` (22 packs). Each maps a tool call to RMACD terms **(operation, data tier, target)** as data — no hand-written classifier. Load one by name with `load_pack("aws")` or several with `load_packs(["aws", "kubectl", "github"])`.

> [!IMPORTANT]
> Built-in packs are **AI-drafted starting points** (`review_status: ai-drafted`). Review and sign them before relying on them in production — see the [authoring guide](authoring-guide.md) and the [overview](README.md). Runtime classification is always deterministic: the §12.5 floor, agent profile, and tool capability ceiling remain the authoritative gates, and the LLM never runs at enforcement time.

## At a glance

| Pack | Family | Tools / selectors | Rules | Summary |
|------|--------|-------------------|-------|---------|
| [`aws`](#aws) | Cloud CLIs | 1 | 1 | AWS CLI (verb-noun actions matched by prefix; s3 high-level verbs handled dir… |
| [`aws-api-mcp`](#aws-api-mcp) | Cloud-provider SDKs & MCPs | 7 | 2 | AWS API MCP server (awslabs). call_aws executes arbitrary AWS CLI commands —… |
| [`aws-iam`](#aws-iam) | Identity & access (focused) | 1 | 4 | AWS CLI focused on identity, access, and secrets (IAM, STS, SSO/Identity Cent… |
| [`az`](#az) | Cloud CLIs | 1 | 1 | Azure CLI (az) |
| [`az-identity`](#az-identity) | Identity & access (focused) | 1 | 4 | Azure CLI focused on identity, access, and secrets (Entra ID via 'az ad', RBA… |
| [`azure-mcp`](#azure-mcp) | Cloud-provider SDKs & MCPs | 11 | 6 | Azure MCP Server (40+ services, namespaced azmcp_<service>_<verb> tools) plus… |
| [`boto3`](#boto3) | Cloud-provider SDKs & MCPs | 3 | 1 | a generic boto3 invoker — aws_call(service, operation, params). One verb-pref… |
| [`confluence`](#confluence) | SaaS / collaboration MCPs | 13 | 5 | Confluence MCP server (Atlassian). Free-text wiki pages frequently hold sensi… |
| [`filesystem`](#filesystem) | Dev tools | 17 | 6 | a filesystem MCP server (read/write/move/delete file tools) |
| [`gcloud`](#gcloud) | Cloud CLIs | 1 | 1 | Google Cloud CLI (gcloud) |
| [`gcp-iam`](#gcp-iam) | Identity & access (focused) | 1 | 4 | Google Cloud CLI focused on identity, access, and secrets (Cloud IAM, service… |
| [`gcp-toolbox`](#gcp-toolbox) | Cloud-provider SDKs & MCPs | 10 | 2 | Google Cloud MCP Toolbox for Databases (googleapis/mcp-toolbox): read-only me… |
| [`github`](#github) | Dev tools | 1 | 1 | GitHub CLI (gh) |
| [`gitlab`](#gitlab) | Dev tools | 1 | 1 | GitLab CLI (glab) |
| [`google-drive`](#google-drive) | SaaS / collaboration MCPs | 15 | 5 | a Google Drive MCP server. Documents frequently hold sensitive data — pair wi… |
| [`jira`](#jira) | SaaS / collaboration MCPs | 17 | 5 | Jira MCP server (Atlassian). Ships with confluence |
| [`kubectl`](#kubectl) | Cloud CLIs | 1 | 1 | kubectl CLI tool |
| [`ms365`](#ms365) | Microsoft 365 MCP | 32 | 5 | a Microsoft 365 / Graph MCP server (Outlook, Teams, SharePoint, OneDrive, Cal… |
| [`postgres`](#postgres) | SaaS / collaboration MCPs | 10 | 2 | a Postgres MCP server: read-only metadata tools plus a passthrough SQL query… |
| [`shell`](#shell) | Shell | 6 | 1 | shell/bash command tools. The hand-tuned rmacd.registry.bash engine remains t… |
| [`slack`](#slack) | SaaS / collaboration MCPs | 16 | 5 | a Slack MCP server |
| [`sql`](#sql) | Dev tools | 6 | 1 | a generic SQL execution tool — a passthrough whose risk is in the statement (… |

## Shell

### `shell`

> RMACD classification for shell/bash command tools. The hand-tuned rmacd.registry.bash engine remains the fast path; this data pack is the portable, signable representation (parity-tested on a representative subset).

**Version** 1.0.0 · **Family** Shell · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

**Matches tools:** `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command`  
**Parses argument:** `command` (strips wrappers: `sudo`, `env`, `nice`, `nohup`, `time`, `timeout`, `xargs`, `doas`)  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `ls`, `cat`, `grep`, `egrep`, `find`, `echo`, `head`, `tail`, `wc`, `stat`, `pwd`, `which`, `whoami`, `id`, `env`, `printenv`, `df`, `du`, `ps`, `top`, `file`, `readlink`, `dirname`, `basename`, `sort`, `uniq`, `diff`, `less`, `more`, `date`, `uname`, `hostname`, `uptime`, `free` |
| **M** Move | `mv`, `rename` |
| **A** Add | `cp`, `mkdir`, `touch`, `tee`, `ln`, `install` |
| **C** Change | `chmod`, `chown`, `chgrp`, `truncate` |
| **D** Delete | `rm`, `rmdir`, `shred`, `unlink` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `confidential` when `command` matches `(shadow|/etc/sudoers|secret|credential|private[_-]?key|\.pem|\.env|password|token)`; otherwise `internal`  
**Target template:** `shell://{command}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

## Cloud CLIs

### `aws`

> RMACD classification for the AWS CLI (verb-noun actions matched by prefix; s3 high-level verbs handled directly).

**Version** 1.0.0 · **Family** Cloud CLIs · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

**Matches tools:** `aws`  
**Parses argument:** `command` (strips wrappers: `sudo`, `env`)  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `describe`, `get`, `list`, `ls`, `head`, `lookup`, `search`, `view`, `show`, `scan`, `query`, `select`, `estimate`, `wait`, `help` |
| **M** Move | `mv` |
| **A** Add | `cp`, `create`, `run`, `register`, `add`, `allocate`, `request`, `import`, `upload`, `provision`, `copy`, `publish` |
| **C** Change | `sync`, `put`, `update`, `modify`, `set`, `attach`, `detach`, `associate`, `disassociate`, `enable`, `disable`, `start`, `stop`, `reboot`, `tag`, `untag`, `configure`, `restore`, `reset` |
| **D** Delete | `delete`, `terminate`, `remove`, `deregister`, `release`, `revoke`, `cancel`, `purge`, `rm`, `destroy` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `confidential` when `command` matches `(iam|kms|secretsmanager|secret|ssm\s+.*parameter|sts|cognito|password|credential)`; `confidential` when `command` matches `(prod|prd|-pii|restricted)`; otherwise `internal`  
**Target template:** `aws://{command}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

### `az`

> RMACD classification for the Azure CLI (az).

**Version** 1.0.0 · **Family** Cloud CLIs · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

**Matches tools:** `az`  
**Parses argument:** `command` (strips wrappers: `sudo`, `env`)  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `list`, `show`, `get`, `export`, `check`, `wait`, `download`, `preview` |
| **A** Add | `create`, `add`, `import`, `deploy`, `upload`, `clone`, `copy` |
| **C** Change | `set`, `update`, `modify`, `configure`, `enable`, `disable`, `start`, `stop`, `restart`, `renew`, `rotate`, `regenerate`, `assign` |
| **D** Delete | `delete`, `remove`, `purge`, `destroy`, `cancel` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `confidential` when `command` matches `(keyvault|secret|key|certificate|ad\s|role|password|credential)`; `confidential` when `command` matches `(prod|prd|restricted)`; otherwise `internal`  
**Target template:** `azure://{command}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

### `gcloud`

> RMACD classification for the Google Cloud CLI (gcloud).

**Version** 1.0.0 · **Family** Cloud CLIs · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

**Matches tools:** `gcloud`  
**Parses argument:** `command` (strips wrappers: `sudo`, `env`)  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `list`, `describe`, `get`, `read`, `lookup`, `export`, `print`, `search`, `test`, `wait` |
| **A** Add | `create`, `add`, `import`, `deploy`, `submit`, `clone`, `copy`, `upload` |
| **C** Change | `enable`, `disable`, `update`, `set`, `modify`, `patch`, `replace`, `start`, `stop`, `restart`, `resume`, `suspend`, `rotate`, `bind`, `unbind` |
| **D** Delete | `delete`, `remove`, `destroy`, `purge`, `cancel` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `confidential` when `command` matches `(iam|kms|secrets|secret|password|credential|service-account)`; `confidential` when `command` matches `(prod|prd|restricted)`; otherwise `internal`  
**Target template:** `gcp://{command}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

### `kubectl`

> RMACD classification for the kubectl CLI tool.

**Version** 1.0.0 · **Family** Cloud CLIs · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

**Matches tools:** `kubectl`  
**Parses argument:** `command` (strips wrappers: `sudo`, `env`)  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `get`, `describe`, `logs`, `explain`, `top`, `api-resources`, `api-versions`, `config`, `version`, `cluster-info`, `auth`, `diff`, `wait` |
| **A** Add | `cp`, `create`, `run`, `expose` |
| **C** Change | `apply`, `edit`, `patch`, `set`, `scale`, `rollout`, `label`, `annotate`, `cordon`, `uncordon`, `drain`, `taint`, `exec`, `replace` |
| **D** Delete | `delete` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `confidential` when `command` matches `(-n\s+prod|--namespace[= ]prod|namespace=prod|secret)`; otherwise `internal`  
**Target template:** `k8s://{command}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

## Identity & access (focused)

Focused, security-hardened variants of the cloud CLI packs. Each is a drop-in standalone pack (load it *instead of* the general `aws` / `az` / `gcloud` pack for agents whose role touches identity or secrets): a general verb-table fallback governs ordinary commands, while scoped overlays raise the whole identity surface to **confidential** and privileged identity mutations and secret/credential access to **restricted**. Because the §12.5 floor makes Change/Delete on `restricted` *prohibited* for autonomous agents, these packs make destructive identity and RBAC changes (deleting users/roles, rewriting policies, purging Key Vault keys) structurally impossible to perform autonomously — while reads of the identity surface and secret access require elevated approval rather than running silently.

### `aws-iam`

> RMACD classification for the AWS CLI focused on identity, access, and secrets (IAM, STS, SSO/Identity Center, Organizations, Secrets Manager, KMS). Hardens the privileged-access surface that the general 'aws' pack treats generically: the whole identity surface is at least confidential, privileged identity mutations and secret/credential access are restricted. Load this instead of 'aws' for agents whose role touches identity or secrets.

**Version** 1.0.0 · **Family** Identity & access (focused) · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

**Matches tools:** `aws`  
**Parses argument:** `command` (strips wrappers: `sudo`, `env`)  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `describe`, `get`, `list`, `ls`, `head`, `lookup`, `search`, `view`, `show`, `scan`, `query`, `select`, `estimate`, `wait`, `help`, `generate`, `simulate` |
| **M** Move | `mv` |
| **A** Add | `cp`, `create`, `run`, `register`, `add`, `allocate`, `request`, `import`, `upload`, `provision`, `copy`, `publish` |
| **C** Change | `sync`, `put`, `update`, `modify`, `set`, `attach`, `detach`, `associate`, `disassociate`, `enable`, `disable`, `start`, `stop`, `reboot`, `tag`, `untag`, `configure`, `restore`, `reset`, `rotate`, `assume` |
| **D** Delete | `delete`, `terminate`, `remove`, `deregister`, `release`, `revoke`, `cancel`, `purge`, `rm`, `destroy` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `confidential` when `command` matches `(prod|prd|-pii|restricted)`; otherwise `internal`  
**Target template:** `aws://{command}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

**Tier overlays** (raise the data tier when the command matches; operation comes from the base rule):

| Applies when | Raises tier to |
|--------------|----------------|
| `command` matches `^\s*(iam|sts|sso|sso-admin|identitystore|organizations|account|secretsmanager|kms)\b` | `confidential` |
| `command` matches `^\s*(iam|sso|sso-admin|identitystore|organizations)\b.*\b(create|update|delete|attach|detach|put|remove|add|deactivate|activate|reset|set|enable|disable|tag|untag)\b` | `restricted` |
| `command` matches `\b(get-secret-value|put-secret-value|create-secret|update-secret|delete-secret|restore-secret|get-session-token|assume-role|get-federation-token|create-access-key|update-access-key|create-login-profile|update-login-profile|reset-service-specific-credential|decrypt|encrypt|re-encrypt|generate-data-key|schedule-key-deletion)\b` | `restricted` |

### `az-identity`

> RMACD classification for the Azure CLI focused on identity, access, and secrets (Entra ID via 'az ad', RBAC 'az role', managed identities, and Key Vault). Hardens the privileged-access surface the general 'az' pack treats generically: the identity surface is at least confidential, RBAC/Entra mutations and Key Vault secret/key/certificate access are restricted. Load this instead of 'az' for agents whose role touches identity or secrets.

**Version** 1.0.0 · **Family** Identity & access (focused) · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

**Matches tools:** `az`  
**Parses argument:** `command` (strips wrappers: `sudo`, `env`)  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `list`, `show`, `get`, `export`, `check`, `wait`, `download`, `preview` |
| **A** Add | `create`, `add`, `import`, `deploy`, `upload`, `clone`, `copy` |
| **C** Change | `set`, `update`, `modify`, `configure`, `enable`, `disable`, `start`, `stop`, `restart`, `renew`, `rotate`, `regenerate`, `assign`, `reset` |
| **D** Delete | `delete`, `remove`, `purge`, `destroy`, `cancel` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `confidential` when `command` matches `(prod|prd|restricted)`; otherwise `internal`  
**Target template:** `azure://{command}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

**Tier overlays** (raise the data tier when the command matches; operation comes from the base rule):

| Applies when | Raises tier to |
|--------------|----------------|
| `command` matches `^\s*(role|ad|keyvault|identity|managed-identity|account)\b` | `confidential` |
| `command` matches `^\s*(role|ad|identity|managed-identity)\b.*\b(create|update|delete|set|assign|add|remove|reset|regenerate|renew|rotate)\b` | `restricted` |
| `command` matches `^\s*keyvault\s+(secret|key|certificate)\b` | `restricted` |

### `gcp-iam`

> RMACD classification for the Google Cloud CLI focused on identity, access, and secrets (Cloud IAM, service accounts, IAM policy bindings on projects/folders/organizations, Secret Manager, and Cloud KMS). Hardens the privileged-access surface the general 'gcloud' pack treats generically: the identity surface is at least confidential, IAM policy-binding changes and secret/key access are restricted. Load this instead of 'gcloud' for agents whose role touches identity or secrets.

**Version** 1.0.0 · **Family** Identity & access (focused) · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

**Matches tools:** `gcloud`  
**Parses argument:** `command` (strips wrappers: `sudo`, `env`)  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `list`, `describe`, `get`, `read`, `lookup`, `export`, `print`, `search`, `test`, `wait` |
| **A** Add | `create`, `add`, `import`, `deploy`, `submit`, `clone`, `copy`, `upload` |
| **C** Change | `enable`, `disable`, `update`, `set`, `modify`, `patch`, `replace`, `start`, `stop`, `restart`, `resume`, `suspend`, `rotate`, `bind`, `unbind` |
| **D** Delete | `delete`, `remove`, `destroy`, `purge`, `cancel` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `confidential` when `command` matches `(prod|prd|restricted)`; otherwise `internal`  
**Target template:** `gcp://{command}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

**Tier overlays** (raise the data tier when the command matches; operation comes from the base rule):

| Applies when | Raises tier to |
|--------------|----------------|
| `command` matches `(\biam\b|iam-policy|service-account|\bsecrets?\b|\bkms\b|\borganizations\b)` | `confidential` |
| `command` matches `\b(add-iam-policy-binding|remove-iam-policy-binding|set-iam-policy)\b` | `restricted` |
| `command` matches `(secrets\s+versions\s+access|\bkms\b.*\b(decrypt|encrypt|destroy|disable)|service-accounts\s+keys\s+create|\biam\s+roles\s+(create|delete|update))` | `restricted` |

## Dev tools

### `filesystem`

> RMACD classification for a filesystem MCP server (read/write/move/delete file tools).

**Version** 1.0.0 · **Family** Dev tools · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

| Operation | Tools | Data tier | Target |
|-----------|-------|-----------|--------|
| **R** Read | `read_file`, `read_text_file`, `read_media_file`, `list_directory`, `directory_tree`, `get_file_info`, `search_files`, `list_allowed_directories` | `internal` | `file://{path}` |
| **C** Change | `create_directory`, `write_file` | `internal` | `file://{path}` |
| **C** Change | `edit_file`, `patch_file` | `internal` | `file://{path}` |
| **M** Move | `move_file`, `rename_file` | `internal` | `file://{source}->{destination}` |
| **D** Delete | `delete_file`, `delete_directory`, `remove_file` | `internal` | `file://{path}` |

**Tier overlays** (raise the data tier when the command matches; operation comes from the base rule):

| Applies when | Raises tier to |
|--------------|----------------|
| `path` matches `(?i)(\.env|\.pem|secret|credential|password|id_rsa|/etc/shadow|private[_-]?key)` | `restricted` |

### `github`

> RMACD classification for the GitHub CLI (gh).

**Version** 1.0.0 · **Family** Dev tools · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

**Matches tools:** `gh`  
**Parses argument:** `command` (strips wrappers: `sudo`, `env`)  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `list`, `view`, `status`, `diff`, `checks`, `browse`, `search`, `clone`, `checkout`, `download` |
| **A** Add | `create`, `fork`, `add` |
| **C** Change | `comment`, `edit`, `merge`, `close`, `reopen`, `ready`, `rename`, `lock`, `unlock`, `pin`, `transfer`, `set`, `set-default`, `sync`, `push`, `rerun`, `approve` |
| **D** Delete | `delete`, `remove` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `confidential` when `command` matches `(secret|token|key|password|credential)`; otherwise `internal`  
**Target template:** `github://{command}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

### `gitlab`

> RMACD classification for the GitLab CLI (glab).

**Version** 1.0.0 · **Family** Dev tools · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

**Matches tools:** `glab`  
**Parses argument:** `command` (strips wrappers: `sudo`, `env`)  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `list`, `view`, `show`, `diff`, `status`, `checkout`, `clone`, `search`, `browse` |
| **A** Add | `create`, `add`, `fork` |
| **C** Change | `note`, `comment`, `update`, `edit`, `merge`, `close`, `reopen`, `approve`, `revoke`, `rebase`, `set` |
| **D** Delete | `delete`, `remove` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `confidential` when `command` matches `(secret|token|variable|key|password|credential)`; otherwise `internal`  
**Target template:** `gitlab://{command}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

### `sql`

> RMACD classification for a generic SQL execution tool — a passthrough whose risk is in the statement (verb-aware, worst-case ceiling).

**Version** 1.0.0 · **Family** Dev tools · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

**Matches tools:** `sql`, `query`, `run_sql`, `execute_sql`, `db_query`, `run_query`  
**Parses argument:** `query`  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `select`, `show`, `describe`, `explain`, `with`, `values`, `table`, `analyze` |
| **A** Add | `insert`, `create`, `import`, `load`, `copy` |
| **C** Change | `update`, `alter`, `merge`, `upsert`, `replace`, `grant`, `revoke`, `set`, `call`, `exec`, `execute`, `rename`, `comment`, `vacuum` |
| **D** Delete | `delete`, `drop`, `truncate` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `restricted` when `query` matches `(?i)(password|ssn|credit[_ ]?card|card_number|secret|token|patients?|medical)`; `confidential` when `query` matches `(?i)(users?|customers?|accounts?|payment|email|address|salary|payroll)`; otherwise `internal`  
**Target template:** `sql://{query}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

## SaaS / collaboration MCPs

### `confluence`

> RMACD classification for the Confluence MCP server (Atlassian). Free-text wiki pages frequently hold sensitive data — pair with redaction/egress controls.

**Version** 1.0.0 · **Family** SaaS / collaboration MCPs · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

**Resolvers** (live tier lookups, fail-closed):

- `confluence_space_tier` — Resolve a Confluence space key to its data classification (fail-closed default: `confidential`)

| Operation | Tools | Data tier | Target |
|-----------|-------|-----------|--------|
| **R** Read | `confluence_search`, `confluence_get_page`, `confluence_get_space`, `confluence_list_pages`, `confluence_get_comments` | resolver `confluence_space_tier` from `space_key`; otherwise `internal` | `confluence://{space_key}/{page_id}` |
| **A** Add | `confluence_create_page`, `confluence_add_comment`, `confluence_add_attachment` | resolver `confluence_space_tier` from `space_key`; otherwise `internal` | `confluence://{space_key}` |
| **M** Move | `confluence_move_page` | resolver `confluence_space_tier` from `target_space_key`; otherwise `internal` | `confluence://{page_id}->{target_space_key}` |
| **C** Change | `confluence_update_page`, `confluence_edit_comment` | resolver `confluence_space_tier` from `space_key`; otherwise `internal` | `confluence://{space_key}/{page_id}` |
| **D** Delete | `confluence_delete_page`, `confluence_delete_comment` | resolver `confluence_space_tier` from `space_key`; otherwise `confidential` | `confluence://{space_key}/{page_id}` |

### `google-drive`

> RMACD classification for a Google Drive MCP server. Documents frequently hold sensitive data — pair with redaction/egress controls.

**Version** 1.0.0 · **Family** SaaS / collaboration MCPs · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

| Operation | Tools | Data tier | Target |
|-----------|-------|-----------|--------|
| **R** Read | `gdrive_search`, `gdrive_read_file`, `gdrive_list_files`, `gdrive_get_file`, `gdrive_export` | `internal` | `gdrive://{file_id}` |
| **A** Add | `gdrive_create_file`, `gdrive_upload_file`, `gdrive_copy_file` | `internal` | `gdrive://{file_id}` |
| **M** Move | `gdrive_move_file` | `internal` | `gdrive://{file_id}` |
| **C** Change | `gdrive_update_file`, `gdrive_rename_file`, `gdrive_share_file`, `gdrive_set_permission` | `internal` | `gdrive://{file_id}` |
| **D** Delete | `gdrive_delete_file`, `gdrive_trash_file` | `internal` | `gdrive://{file_id}` |

### `jira`

> RMACD classification for the Jira MCP server (Atlassian). Ships with confluence.

**Version** 1.0.0 · **Family** SaaS / collaboration MCPs · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

**Resolvers** (live tier lookups, fail-closed):

- `jira_project_tier` — Resolve a Jira project key to its data classification (fail-closed default: `confidential`)

| Operation | Tools | Data tier | Target |
|-----------|-------|-----------|--------|
| **R** Read | `jira_search`, `jira_get_issue`, `jira_get_project`, `jira_list_projects`, `jira_get_user`, `jira_get_transitions` | resolver `jira_project_tier` from `project_key`; otherwise `internal` | `jira://{project_key}/{issue_key}` |
| **A** Add | `jira_create_issue`, `jira_add_comment`, `jira_add_attachment`, `jira_create_issue_link` | resolver `jira_project_tier` from `project_key`; otherwise `internal` | `jira://{project_key}` |
| **M** Move | `jira_move_issue` | resolver `jira_project_tier` from `target_project_key`; otherwise `internal` | `jira://{issue_key}->{target_project_key}` |
| **C** Change | `jira_update_issue`, `jira_transition_issue`, `jira_assign_issue`, `jira_edit_comment` | `confidential` when `project_key` matches `^(SEC|HR|LEGAL|FIN)$`; resolver `jira_project_tier` from `project_key`; otherwise `internal` | `jira://{project_key}/{issue_key}` |
| **D** Delete | `jira_delete_issue`, `jira_delete_comment` | resolver `jira_project_tier` from `project_key`; otherwise `confidential` | `jira://{project_key}/{issue_key}` |

### `postgres`

> RMACD classification for a Postgres MCP server: read-only metadata tools plus a passthrough SQL query tool (verb-aware, worst-case ceiling).

**Version** 1.0.0 · **Family** SaaS / collaboration MCPs · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

**Matches tools:** `query`, `read_query`, `execute_query`, `pg_query`, `run_sql`  
**Parses argument:** `sql`  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `select`, `show`, `explain`, `with`, `table` |
| **A** Add | `insert`, `create`, `copy` |
| **C** Change | `update`, `alter`, `grant`, `revoke`, `merge` |
| **D** Delete | `delete`, `drop`, `truncate` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `restricted` when `sql` matches `(?i)(password|ssn|credit[_ ]?card|secret|token|patients?)`; `confidential` when `sql` matches `(?i)(users?|customers?|accounts?|payment|email|salary)`; otherwise `internal`  
**Target template:** `postgres://{sql}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

| Operation | Tools | Data tier | Target |
|-----------|-------|-----------|--------|
| **R** Read | `list_tables`, `describe_table`, `get_schema`, `list_schemas`, `explain_query` | `internal` | `postgres://{table}` |

### `slack`

> RMACD classification for a Slack MCP server.

**Version** 1.0.0 · **Family** SaaS / collaboration MCPs · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

| Operation | Tools | Data tier | Target |
|-----------|-------|-----------|--------|
| **R** Read | `slack_list_channels`, `slack_get_channel_history`, `slack_get_thread_replies`, `slack_get_users`, `slack_get_user_profile`, `slack_search_messages` | `internal` | `slack://{channel_id}` |
| **A** Add | `slack_post_message`, `slack_reply_to_thread`, `slack_add_reaction`, `slack_upload_file` | `internal` | `slack://{channel_id}` |
| **C** Change | `slack_update_message`, `slack_set_topic`, `slack_invite_user` | `internal` | `slack://{channel_id}` |
| **D** Delete | `slack_delete_message`, `slack_remove_reaction`, `slack_archive_channel` | `internal` | `slack://{channel_id}` |

**Tier overlays** (raise the data tier when the command matches; operation comes from the base rule):

| Applies when | Raises tier to |
|--------------|----------------|
| `channel_id` matches `^D` | `confidential` |

## Cloud-provider SDKs & MCPs

### `aws-api-mcp`

> RMACD classification for the AWS API MCP server (awslabs). call_aws executes arbitrary AWS CLI commands — a passthrough whose risk is in the argument; documentation tools are read-only.

**Version** 1.0.0 · **Family** Cloud-provider SDKs & MCPs · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

**Matches tools:** `call_aws`, `execute_aws_command`, `aws_api`  
**Parses argument:** `cli_command`  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `describe`, `get`, `list`, `ls`, `head`, `lookup`, `search`, `scan`, `query`, `select` |
| **M** Move | `mv` |
| **A** Add | `cp`, `create`, `run`, `register`, `add`, `allocate`, `request`, `import`, `upload` |
| **C** Change | `sync`, `put`, `update`, `modify`, `set`, `attach`, `detach`, `associate`, `enable`, `disable`, `start`, `stop`, `reboot`, `tag`, `untag`, `restore`, `reset` |
| **D** Delete | `delete`, `terminate`, `remove`, `deregister`, `release`, `revoke`, `cancel`, `purge`, `rm` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `confidential` when `cli_command` matches `(?i)(iam|kms|secretsmanager|secret|sts|cognito|password|credential)`; `confidential` when `cli_command` matches `(?i)(prod|prd|restricted|pii)`; otherwise `internal`  
**Target template:** `aws-api://{cli_command}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

| Operation | Tools | Data tier | Target |
|-----------|-------|-----------|--------|
| **R** Read | `suggest_aws_commands`, `get_aws_documentation`, `read_documentation`, `search_documentation` | `internal` | `aws-api://docs` |

### `azure-mcp`

> RMACD classification for the Azure MCP Server (40+ services, namespaced azmcp_<service>_<verb> tools) plus a passthrough Azure CLI tool. Glob rules need a discovered tool list (apply_pack(tool_names=...)).

**Version** 1.0.0 · **Family** Cloud-provider SDKs & MCPs · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

**Resolvers** (live tier lookups, fail-closed):

- `azure_resource_tier` — Resolve an Azure resource group / resource id to its tier (fail-closed default: `confidential`)

**Matches tools:** `azmcp_extension_az`, `az_command`  
**Parses argument:** `command` (strips wrappers: `az`)  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `list`, `show`, `get`, `export` |
| **A** Add | `create`, `add`, `import`, `deploy` |
| **C** Change | `set`, `update`, `enable`, `disable`, `start`, `stop`, `restart`, `rotate`, `regenerate` |
| **D** Delete | `delete`, `remove`, `purge` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** resolver `azure_resource_tier` from `command`; otherwise `internal`  
**Target template:** `azure-cli://{command}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

| Operation | Tools | Data tier | Target |
|-----------|-------|-----------|--------|
| **R** Read | `azmcp_*_list`, `azmcp_*_show`, `azmcp_*_get`, `azmcp_*_query` | resolver `azure_resource_tier` from `resource_group`; otherwise `internal` | `azure://{service}/{name}` |
| **A** Add | `azmcp_*_create` | resolver `azure_resource_tier` from `resource_group`; otherwise `internal` | `azure://{service}/{name}` |
| **C** Change | `azmcp_*_update`, `azmcp_*_set` | resolver `azure_resource_tier` from `resource_group`; otherwise `internal` | `azure://{service}/{name}` |
| **D** Delete | `azmcp_*_delete` | resolver `azure_resource_tier` from `resource_group`; otherwise `confidential` | `azure://{service}/{name}` |

**Tier overlays** (raise the data tier when the command matches; operation comes from the base rule):

| Applies when | Raises tier to |
|--------------|----------------|
| `azmcp_keyvault_*` | `restricted` |

### `boto3`

> RMACD classification for a generic boto3 invoker — aws_call(service, operation, params). One verb-prefix table governs the whole AWS Python SDK; passthrough -> worst-case ceiling.

**Version** 1.0.0 · **Family** Cloud-provider SDKs & MCPs · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

**Resolvers** (live tier lookups, fail-closed):

- `aws_resource_tier` — Resolve an AWS resource identifier to its tier (fail-closed default: `confidential`)

**Matches tools:** `aws_call`, `boto3_call`, `call_boto3`  
**Parses argument:** `operation`  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `describe`, `get`, `list`, `head`, `lookup`, `search`, `query`, `scan`, `select`, `estimate` |
| **M** Move | `copy` |
| **A** Add | `create`, `register`, `run`, `import`, `allocate`, `request`, `add`, `publish`, `upload`, `generate` |
| **C** Change | `put`, `update`, `modify`, `set`, `attach`, `detach`, `associate`, `disassociate`, `enable`, `disable`, `start`, `stop`, `reboot`, `tag`, `untag`, `restore`, `reset`, `rotate` |
| **D** Delete | `delete`, `terminate`, `deregister`, `purge`, `release`, `revoke`, `cancel`, `remove` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `confidential` when `service` matches `(?i)(iam|kms|secretsmanager|sts|cognito)`; `confidential` when `params.Bucket` matches `(?i)(prod|pii|restricted)`; resolver `aws_resource_tier` from `params`; otherwise `internal`  
**Target template:** `aws://{service}/{operation}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

### `gcp-toolbox`

> RMACD classification for the Google Cloud MCP Toolbox for Databases (googleapis/mcp-toolbox): read-only metadata plus passthrough SQL execution (verb-aware, worst-case ceiling).

**Version** 1.0.0 · **Family** Cloud-provider SDKs & MCPs · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

**Matches tools:** `execute_sql`, `postgres_query`, `mysql_query`, `bigquery_query`, `spanner_query`, `run_sql`  
**Parses argument:** `sql`  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `select`, `show`, `explain`, `with`, `table` |
| **A** Add | `insert`, `create`, `load`, `copy` |
| **C** Change | `update`, `alter`, `grant`, `revoke`, `merge` |
| **D** Delete | `delete`, `drop`, `truncate` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `restricted` when `sql` matches `(?i)(password|ssn|credit[_ ]?card|secret|token|patients?)`; `confidential` when `sql` matches `(?i)(users?|customers?|accounts?|payment|email|salary)`; otherwise `internal`  
**Target template:** `gcp-db://{sql}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

| Operation | Tools | Data tier | Target |
|-----------|-------|-----------|--------|
| **R** Read | `list_tables`, `list_datasets`, `get_schema`, `describe_table` | `internal` | `gcp-db://{table}` |

## Microsoft 365 MCP

### `ms365`

> RMACD classification for a Microsoft 365 / Graph MCP server (Outlook, Teams, SharePoint, OneDrive, Calendar). Mail and files frequently hold sensitive data — pair with redaction/egress controls.

**Version** 1.0.0 · **Family** Microsoft 365 MCP · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

| Operation | Tools | Data tier | Target |
|-----------|-------|-----------|--------|
| **R** Read | `list_messages`, `get_message`, `search_messages`, `list_events`, `get_event`, `list_files`, `read_file`, `search_files`, `list_chats`, `get_chat_messages`, `list_sites`, `get_contacts` | `confidential` | `ms365://{id}` |
| **A** Add | `send_mail`, `create_event`, `create_draft`, `upload_file`, `post_chat_message`, `create_folder`, `add_contact` | `confidential` | `ms365://{id}` |
| **M** Move | `move_message`, `move_file` | `confidential` | `ms365://{id}` |
| **C** Change | `update_event`, `update_message`, `update_file`, `reply_to_message`, `accept_event`, `decline_event`, `share_file` | `confidential` | `ms365://{id}` |
| **D** Delete | `delete_message`, `delete_event`, `delete_file`, `delete_contact` | `confidential` | `ms365://{id}` |

---

*Generated by `docs/governance-packs/generate_catalog.py` from the built-in pack data in `sdk/python/rmacd/packs/data/`. Do not edit by hand — re-run the script after changing a pack.*
