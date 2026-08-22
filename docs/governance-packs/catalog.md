# Governance Pack Catalog

> The built-in governance packs that ship with `rmacd-framework` (34 packs). Each maps a tool call to RMACD terms **(operation, data tier, target)** as data — no hand-written classifier. Load one by name with `load_pack("aws")` or several with `load_packs(["aws", "kubectl", "github"])`.

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
| [`docker`](#docker) | Developer toolchain | 7 | 6 | Docker CLI (docker, docker compose), both as a direct tool and inside shell c… |
| [`filesystem`](#filesystem) | Dev tools | 17 | 6 | a filesystem MCP server (read/write/move/delete file tools) |
| [`gcloud`](#gcloud) | Cloud CLIs | 1 | 1 | Google Cloud CLI (gcloud) |
| [`gcp-iam`](#gcp-iam) | Identity & access (focused) | 1 | 4 | Google Cloud CLI focused on identity, access, and secrets (Cloud IAM, service… |
| [`gcp-toolbox`](#gcp-toolbox) | Cloud-provider SDKs & MCPs | 10 | 2 | Google Cloud MCP Toolbox for Databases (googleapis/mcp-toolbox): read-only me… |
| [`gh`](#gh) | Developer toolchain | 7 | 11 | GitHub CLI (gh), both as a direct tool and inside shell commands. A finer-gra… |
| [`git`](#git) | Developer toolchain | 7 | 13 | git CLI, both as a direct tool and inside shell commands. Reads (status/log/d… |
| [`github`](#github) | Dev tools | 1 | 1 | GitHub CLI (gh) |
| [`gitlab`](#gitlab) | Dev tools | 1 | 1 | GitLab CLI (glab) |
| [`google-drive`](#google-drive) | SaaS / collaboration MCPs | 15 | 5 | a Google Drive MCP server. Documents frequently hold sensitive data — pair wi… |
| [`helm`](#helm) | Enterprise operations | 7 | 10 | Helm CLI (Kubernetes package manager), both as a direct tool and inside shell… |
| [`jira`](#jira) | SaaS / collaboration MCPs | 17 | 5 | Jira MCP server (Atlassian). Ships with confluence |
| [`kubectl`](#kubectl) | Cloud CLIs | 1 | 1 | kubectl CLI tool |
| [`make`](#make) | Developer toolchain | 8 | 10 | GNU make (make/gmake), both as a direct tool and inside shell commands. Make… |
| [`ms365`](#ms365) | Microsoft 365 MCP | 32 | 5 | a Microsoft 365 / Graph MCP server (Outlook, Teams, SharePoint, OneDrive, Cal… |
| [`npm`](#npm) | Developer toolchain | 8 | 10 | npm CLI (and npx), both as direct tools and inside shell commands. Reads (ls/… |
| [`pip-uv`](#pip-uv) | Developer toolchain | 10 | 6 | Python packaging toolchain — pip/pip3, uv, and twine — both as direct tools a… |
| [`postgres`](#postgres) | SaaS / collaboration MCPs | 10 | 2 | a Postgres MCP server: read-only metadata tools plus a passthrough SQL query… |
| [`servicenow`](#servicenow) | Enterprise operations | 46 | 10 | ServiceNow MCP/REST tool surfaces (ITSM, change management, CMDB). There is n… |
| [`shell`](#shell) | Shell | 6 | 1 | shell/bash command tools. ADVISORY ONLY — this data pack does NOT have parity… |
| [`slack`](#slack) | SaaS / collaboration MCPs | 16 | 5 | a Slack MCP server |
| [`sql`](#sql) | Dev tools | 6 | 1 | a generic SQL execution tool — a passthrough whose risk is in the statement (… |
| [`ssh-transfer`](#ssh-transfer) | Enterprise operations | 14 | 8 | remote shells and file transfer: ssh, scp, sftp, rsync, and the SSH credentia… |
| [`stripe`](#stripe) | Enterprise operations | 7 | 10 | Stripe CLI, both as a direct tool and inside shell commands. Payment data is… |
| [`terraform`](#terraform) | Developer toolchain | 8 | 10 | Terraform CLI (terraform; OpenTofu 'tofu' is matched as a drop-in alias), bot… |
| [`vault`](#vault) | Enterprise operations | 7 | 10 | HashiCorp Vault CLI, both as a direct tool and inside shell commands. This pa… |

## Shell

### `shell`

> RMACD classification for shell/bash command tools. ADVISORY ONLY — this data pack does NOT have parity with the hand-tuned rmacd.registry.bash engine, which remains the enforcing classifier for shell commands. The declarative engine has no redirect detection, no `-c`/`eval` recursion, no flag-elevation primitive and no prefix binary matching, so it under-classifies constructs such as `echo x > /etc/passwd` (R vs C), `bash -c "rm -rf /"` (C vs D), `find . -delete` (R vs D) and `curl -X DELETE` (C vs D). Use it as the portable, signable representation of the common cases; do not rely on it alone to gate a shell tool.

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

Focused, security-hardened variants of the cloud CLI packs. Each is a drop-in standalone pack (load it *instead of* the general `aws` / `az` / `gcloud` pack for agents whose role touches identity or secrets): a general verb-table fallback governs ordinary commands, while scoped overlays raise the whole identity surface to **confidential** and privileged identity mutations and secret/credential access to **restricted**. Because the §12.5 floor makes Add/Change/Delete on `restricted` *prohibited* for autonomous agents, these packs make destructive identity and RBAC changes (deleting users/roles, rewriting policies, purging Key Vault keys) structurally impossible to perform autonomously — while reads of the identity surface and secret access require elevated approval rather than running silently.

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

## Developer toolchain

The surfaces enterprise coding-agent sessions actually touch: `load_packs(["git", "gh", "docker", "terraform", "npm", "pip-uv", "make"])` is one line. Each pack governs its CLI both as a direct tool name and inside shell commands (`bash`/`sh`/... with the CLI's binary in the command line). Routine development flows normally (reads are Read on `internal`, installs/commits are Add, builds and lifecycle changes are Change), while destructive, credential, publish, and IAM-adjacent operations — force pushes, `terraform apply`/state surgery, registry publishing, `docker login`/`--privileged`, secret and token management — land on the **restricted** tier, so the §12.5 floor makes them structurally impossible to perform autonomously. Packs that share a shell tool name (`bash`, `sh`, ...) **compose**: `apply_pack` chains them in load order instead of replacing, and per call the pack whose rules match governs — with *its own* capability ceiling, never a union across packs — falling through on no-match to the next pack and finally to any tool registered before the packs. A pack's broad tool-name-only fallback rule (e.g. the shell pack's coreutils table) never shadows another pack's specific claim, so loading all seven toolchain packs plus `shell` over the same `bash` tool just works.

### `docker`

> RMACD classification for the Docker CLI (docker, docker compose), both as a direct tool and inside shell commands. Reads (ps/images/logs/inspect) stay internal; image builds and pulls are Add; container lifecycle (run/start/stop/restart) is Change; removals and prunes are Delete on confidential. Registry credential operations (login), image publishing (push), and sandbox-escape flags (--privileged, host namespaces, host-root bind mounts) land on the restricted tier, so the §12.5 floor prohibits them for autonomous agents.

**Version** 1.0.0 · **Family** Developer toolchain · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

**Matches tools:** `docker`  
**Parses argument:** `command` (strips wrappers: `sudo`, `env`)  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `ps`, `images`, `logs`, `inspect`, `version`, `info`, `history`, `top`, `port`, `stats`, `events`, `diff`, `search`, `wait`, `help` |
| **M** Move | `rename` |
| **A** Add | `build`, `pull`, `tag`, `create`, `commit`, `save`, `export`, `import`, `load`, `cp` |
| **C** Change | `run`, `start`, `stop`, `restart`, `pause`, `unpause`, `kill`, `exec`, `attach`, `update`, `scale`, `up` |
| **D** Delete | `rm`, `rmi`, `prune`, `down` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `confidential` when `command` matches `(secret|password|credential|token|/var/run/docker\.sock)`; otherwise `internal`  
**Target template:** `docker://{command}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

**Matches tools:** `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command`  
**Parses argument:** `command` (strips wrappers: `sudo`, `env`)  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `ps`, `images`, `logs`, `inspect`, `version`, `info`, `history`, `top`, `port`, `stats`, `events`, `diff`, `search`, `wait`, `help` |
| **M** Move | `rename` |
| **A** Add | `build`, `pull`, `tag`, `create`, `commit`, `save`, `export`, `import`, `load`, `cp` |
| **C** Change | `run`, `start`, `stop`, `restart`, `pause`, `unpause`, `kill`, `exec`, `attach`, `update`, `scale`, `up` |
| **D** Delete | `rm`, `rmi`, `prune`, `down` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `confidential` when `command` matches `(secret|password|credential|token|/var/run/docker\.sock)`; otherwise `internal`  
**Target template:** `docker://{command}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

| Operation | Tools | Data tier | Target |
|-----------|-------|-----------|--------|
| **C** Change | `docker`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |
| **C** Change | `docker`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |
| **C** Change | `docker`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |

**Tier overlays** (raise the data tier when the command matches; operation comes from the base rule):

| Applies when | Raises tier to |
|--------------|----------------|
| `command` matches `(^|\s)(rm|rmi|prune)\b` | `confidential` |

### `gh`

> RMACD classification for the GitHub CLI (gh), both as a direct tool and inside shell commands. A finer-grained successor to the coarse 'github' pack (load one or the other, not both): pr/issue/run reads stay internal; pr create/comment are Add; pr merge and release create are Change on confidential. Repo deletion, Actions secret/variable writes, SSH/GPG key management, and credential access (auth login/token) land on the restricted tier, so the §12.5 floor prohibits the mutations for autonomous agents.

**Version** 1.0.0 · **Family** Developer toolchain · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

**Matches tools:** `gh`  
**Parses argument:** `command` (strips wrappers: `sudo`, `env`)  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `list`, `view`, `status`, `diff`, `checks`, `browse`, `search`, `clone`, `checkout`, `download`, `watch`, `token`, `help`, `version` |
| **A** Add | `create`, `fork`, `comment`, `review`, `upload` |
| **C** Change | `edit`, `merge`, `close`, `reopen`, `ready`, `rename`, `lock`, `unlock`, `pin`, `unpin`, `transfer`, `sync`, `push`, `rerun`, `approve`, `enable`, `disable`, `set`, `set-default`, `cancel`, `login`, `logout`, `refresh`, `api` |
| **D** Delete | `delete`, `remove` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `confidential` when `command` matches `(secret|token|password|credential|ssh-key|gpg-key)`; otherwise `internal`  
**Target template:** `github://{command}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

**Matches tools:** `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command`  
**Parses argument:** `command` (strips wrappers: `sudo`, `env`)  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `list`, `view`, `status`, `diff`, `checks`, `browse`, `search`, `clone`, `checkout`, `download`, `watch`, `token`, `help`, `version` |
| **A** Add | `create`, `fork`, `comment`, `review`, `upload` |
| **C** Change | `edit`, `merge`, `close`, `reopen`, `ready`, `rename`, `lock`, `unlock`, `pin`, `unpin`, `transfer`, `sync`, `push`, `rerun`, `approve`, `enable`, `disable`, `set`, `set-default`, `cancel`, `login`, `logout`, `refresh`, `api` |
| **D** Delete | `delete`, `remove` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `confidential` when `command` matches `(secret|token|password|credential|ssh-key|gpg-key)`; otherwise `internal`  
**Target template:** `github://{command}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

| Operation | Tools | Data tier | Target |
|-----------|-------|-----------|--------|
| **C** Change | `gh`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `confidential` | — |
| **D** Delete | `gh`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `confidential` | — |
| **D** Delete | `gh`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |
| **C** Change | `gh`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |
| **C** Change | `gh`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |
| **C** Change | `gh`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |
| **D** Delete | `gh`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `confidential` | — |

**Tier overlays** (raise the data tier when the command matches; operation comes from the base rule):

| Applies when | Raises tier to |
|--------------|----------------|
| `command` matches `(^|\s)(secret|variable)\s+(set|delete|remove|list)\b` | `restricted` |
| `command` matches `(^|\s)auth\s+token\b` | `restricted` |

### `git`

> RMACD classification for the git CLI, both as a direct tool and inside shell commands. Reads (status/log/diff/show/fetch) stay internal; local mutations (add/commit/stash) are Add; history-integrating operations (merge/rebase/pull) are Change; push is Change on confidential. Destructive or history-rewriting operations (push --force, branch -D, reset --hard, clean -f, filter-branch/filter-repo) and credential access land on the restricted tier, so the §12.5 floor prohibits them for autonomous agents.

**Version** 1.0.0 · **Family** Developer toolchain · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

**Matches tools:** `git`  
**Parses argument:** `command` (strips wrappers: `sudo`, `env`)  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `status`, `log`, `diff`, `show`, `fetch`, `clone`, `ls-files`, `ls-remote`, `ls-tree`, `blame`, `describe`, `reflog`, `shortlog`, `grep`, `rev-parse`, `rev-list`, `show-ref`, `cat-file`, `branch`, `tag`, `remote`, `help`, `version`, `var`, `archive` |
| **M** Move | `mv` |
| **A** Add | `add`, `commit`, `stash`, `init`, `worktree`, `notes`, `format-patch`, `bundle` |
| **C** Change | `merge`, `rebase`, `pull`, `checkout`, `switch`, `restore`, `revert`, `cherry-pick`, `reset`, `config`, `am`, `apply`, `submodule`, `gc`, `bisect`, `push` |
| **D** Delete | `clean`, `rm`, `prune`, `drop` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `confidential` when `command` matches `(credential|askpass|\.netrc|token|password)`; otherwise `internal`  
**Target template:** `git://{command}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

**Matches tools:** `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command`  
**Parses argument:** `command` (strips wrappers: `sudo`, `env`)  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `status`, `log`, `diff`, `show`, `fetch`, `clone`, `ls-files`, `ls-remote`, `ls-tree`, `blame`, `describe`, `reflog`, `shortlog`, `grep`, `rev-parse`, `rev-list`, `show-ref`, `cat-file`, `branch`, `tag`, `remote`, `help`, `version`, `var`, `archive` |
| **M** Move | `mv` |
| **A** Add | `add`, `commit`, `stash`, `init`, `worktree`, `notes`, `format-patch`, `bundle` |
| **C** Change | `merge`, `rebase`, `pull`, `checkout`, `switch`, `restore`, `revert`, `cherry-pick`, `reset`, `config`, `am`, `apply`, `submodule`, `gc`, `bisect`, `push` |
| **D** Delete | `clean`, `rm`, `prune`, `drop` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `confidential` when `command` matches `(credential|askpass|\.netrc|token|password)`; otherwise `internal`  
**Target template:** `git://{command}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

| Operation | Tools | Data tier | Target |
|-----------|-------|-----------|--------|
| **C** Change | `git`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `confidential` | — |
| **C** Change | `git`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |
| **D** Delete | `git`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |
| **D** Delete | `git`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `internal` | — |
| **D** Delete | `git`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |
| **C** Change | `git`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |
| **D** Delete | `git`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |
| **C** Change | `git`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |
| **C** Change | `git`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `confidential` | — |
| **C** Change | `git`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `confidential` | — |

**Tier overlays** (raise the data tier when the command matches; operation comes from the base rule):

| Applies when | Raises tier to |
|--------------|----------------|
| `command` matches `(^|\s)credential(-store|-cache)?\b|credential\.helper` | `restricted` |

### `make`

> RMACD classification for GNU make (make/gmake), both as a direct tool and inside shell commands. Make recipes are opaque — an arbitrary target executes arbitrary commands that this pack cannot classify — so unrecognised targets fail closed to Change on internal and the capability ceiling applies; govern the underlying commands with the 'shell' pack where possible. Dry-run/query invocations (-n/--dry-run, -q, --help, --version) are Read; clean/distclean targets are Delete; install/uninstall touch system locations and are Change/Delete on confidential.

**Version** 1.0.0 · **Family** Developer toolchain · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

| Operation | Tools | Data tier | Target |
|-----------|-------|-----------|--------|
| **R** Read | `make`, `gmake` | — | — |
| **R** Read | `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | — | — |
| **D** Delete | `make`, `gmake` | `internal` | — |
| **D** Delete | `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `internal` | — |
| **C** Change | `make`, `gmake` | `confidential` | — |
| **C** Change | `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `confidential` | — |
| **D** Delete | `make`, `gmake` | `confidential` | — |
| **D** Delete | `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `confidential` | — |

**Tier overlays** (raise the data tier when the command matches; operation comes from the base rule):

| Applies when | Raises tier to |
|--------------|----------------|
| `make`, `gmake` | `internal` |
| `command` matches `(^|\s)g?make(\s|$)` | `internal` |

### `npm`

> RMACD classification for the npm CLI (and npx), both as direct tools and inside shell commands. Reads (ls/view/outdated/audit) stay internal; install/ci are Add; update/link and script execution (run/exec — opaque, fail-closed to Change) are Change; uninstall is Delete. Registry-facing operations — publish/unpublish, token management, owner/access/deprecate, and login — land on the restricted tier, so the §12.5 floor prohibits them for autonomous agents. npx executes arbitrary packages and is classified Change fail-closed.

**Version** 1.0.0 · **Family** Developer toolchain · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

**Matches tools:** `npm`  
**Parses argument:** `command` (strips wrappers: `sudo`, `env`)  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `ls`, `list`, `ll`, `view`, `info`, `show`, `outdated`, `audit`, `search`, `explain`, `doctor`, `ping`, `root`, `prefix`, `whoami`, `help`, `docs`, `repo`, `fund`, `get` |
| **A** Add | `install`, `i`, `ci`, `pack`, `init`, `create` |
| **C** Change | `update`, `upgrade`, `link`, `dedupe`, `rebuild`, `run`, `run-script`, `start`, `restart`, `stop`, `test`, `exec`, `version`, `set`, `edit`, `fix` |
| **D** Delete | `uninstall`, `remove`, `rm`, `un`, `unlink`, `prune` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `confidential` when `command` matches `(_authToken|token|password|credential|secret)`; otherwise `internal`  
**Target template:** `npm://{command}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

**Matches tools:** `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command`  
**Parses argument:** `command` (strips wrappers: `sudo`, `env`)  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `ls`, `list`, `ll`, `view`, `info`, `show`, `outdated`, `audit`, `search`, `explain`, `doctor`, `ping`, `root`, `prefix`, `whoami`, `help`, `docs`, `repo`, `fund`, `get` |
| **A** Add | `install`, `i`, `ci`, `pack`, `init`, `create` |
| **C** Change | `update`, `upgrade`, `link`, `dedupe`, `rebuild`, `run`, `run-script`, `start`, `restart`, `stop`, `test`, `exec`, `version`, `set`, `edit`, `fix` |
| **D** Delete | `uninstall`, `remove`, `rm`, `un`, `unlink`, `prune` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `confidential` when `command` matches `(_authToken|token|password|credential|secret)`; otherwise `internal`  
**Target template:** `npm://{command}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

| Operation | Tools | Data tier | Target |
|-----------|-------|-----------|--------|
| **C** Change | `npx` | `internal` | `npm://npx {command}` |
| **C** Change | `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `internal` | `npm://{command}` |
| **C** Change | `npm`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |
| **D** Delete | `npm`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |
| **C** Change | `npm`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |
| **C** Change | `npm`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |
| **C** Change | `npm`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |
| **C** Change | `npm`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `confidential` | — |

### `pip-uv`

> RMACD classification for the Python packaging toolchain — pip/pip3, uv, and twine — both as direct tools and inside shell commands. Reads (pip list/show/download, uv lock/tree) stay internal; pip/uv install and uv sync/add are Add; uninstall/remove are Delete. Publishing to a package index (uv publish, twine upload) and credential material (index tokens, .pypirc, keyring writes) land on the restricted tier, so the §12.5 floor prohibits them for autonomous agents. Alternate-index flags raise the tier to confidential (supply-chain surface).

**Version** 1.0.0 · **Family** Developer toolchain · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

**Matches tools:** `pip`, `pip3`, `uv`, `twine`  
**Parses argument:** `command` (strips wrappers: `sudo`, `env`)  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `list`, `show`, `download`, `freeze`, `check`, `search`, `index`, `inspect`, `debug`, `help`, `hash`, `cache`, `lock`, `tree`, `export`, `version`, `config`, `dir`, `info` |
| **A** Add | `install`, `wheel`, `add`, `sync`, `venv`, `init`, `build` |
| **C** Change | `run`, `pin`, `upgrade`, `update`, `register`, `upload` |
| **D** Delete | `uninstall`, `remove`, `purge`, `prune`, `clean` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `confidential` when `command` matches `(index-url|extra-index-url|trusted-host|find-links|keyring)`; otherwise `internal`  
**Target template:** `pip://{command}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

**Matches tools:** `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command`  
**Parses argument:** `command` (strips wrappers: `sudo`, `env`)  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `list`, `show`, `download`, `freeze`, `check`, `search`, `index`, `inspect`, `debug`, `help`, `hash`, `cache`, `lock`, `tree`, `export`, `version`, `config`, `dir`, `info` |
| **A** Add | `install`, `wheel`, `add`, `sync`, `venv`, `init`, `build` |
| **C** Change | `run`, `pin`, `upgrade`, `update`, `register`, `upload` |
| **D** Delete | `uninstall`, `remove`, `purge`, `prune`, `clean` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `confidential` when `command` matches `(index-url|extra-index-url|trusted-host|find-links|keyring)`; otherwise `internal`  
**Target template:** `pip://{command}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

| Operation | Tools | Data tier | Target |
|-----------|-------|-----------|--------|
| **C** Change | `pip`, `pip3`, `uv`, `twine`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |
| **C** Change | `pip`, `pip3`, `uv`, `twine`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `confidential` | — |

**Tier overlays** (raise the data tier when the command matches; operation comes from the base rule):

| Applies when | Raises tier to |
|--------------|----------------|
| `command` matches `(--password|--username|--token|pypirc|keyring\s+set)` | `restricted` |
| `command` matches `--break-system-packages\b` | `confidential` |

### `terraform`

> RMACD classification for the Terraform CLI (terraform; OpenTofu 'tofu' is matched as a drop-in alias), both as a direct tool and inside shell commands. Reads (fmt/validate/show/output) stay internal; plan and state reads are confidential because they can reveal state contents. init/import are Add. Infrastructure mutation is the danger surface: apply, destroy, state surgery (state rm/mv/push), workspace delete, force-unlock, and login all land on the restricted tier, so the §12.5 floor prohibits them for autonomous agents — an agent can plan, but a human applies.

**Version** 1.0.0 · **Family** Developer toolchain · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

**Matches tools:** `terraform`, `tofu`  
**Parses argument:** `command` (strips wrappers: `sudo`, `env`)  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `fmt`, `list`, `validate`, `show`, `output`, `graph`, `providers`, `version`, `console`, `test`, `plan`, `help` |
| **A** Add | `init`, `import`, `get`, `new` |
| **C** Change | `apply`, `refresh`, `taint`, `untaint`, `select`, `login`, `logout` |
| **D** Delete | `destroy`, `delete` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `confidential` when `command` matches `(^|\s)plan\b`; `confidential` when `command` matches `(secret|password|credential|token|vault)`; otherwise `internal`  
**Target template:** `terraform://{command}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

**Matches tools:** `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command`  
**Parses argument:** `command` (strips wrappers: `sudo`, `env`)  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `fmt`, `list`, `validate`, `show`, `output`, `graph`, `providers`, `version`, `console`, `test`, `plan`, `help` |
| **A** Add | `init`, `import`, `get`, `new` |
| **C** Change | `apply`, `refresh`, `taint`, `untaint`, `select`, `login`, `logout` |
| **D** Delete | `destroy`, `delete` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `confidential` when `command` matches `(^|\s)plan\b`; `confidential` when `command` matches `(secret|password|credential|token|vault)`; otherwise `internal`  
**Target template:** `terraform://{command}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

| Operation | Tools | Data tier | Target |
|-----------|-------|-----------|--------|
| **C** Change | `terraform`, `tofu`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |
| **D** Delete | `terraform`, `tofu`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |
| **C** Change | `terraform`, `tofu`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |
| **D** Delete | `terraform`, `tofu`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |
| **D** Delete | `terraform`, `tofu`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |
| **C** Change | `terraform`, `tofu`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |
| **C** Change | `terraform`, `tofu`, `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |

**Tier overlays** (raise the data tier when the command matches; operation comes from the base rule):

| Applies when | Raises tier to |
|--------------|----------------|
| `command` matches `(^|\s)state\s+(list|show|pull)\b` | `confidential` |

## Enterprise operations

One pack per enterprise control domain: change management (`servicenow` — ITSM/CAB via MCP tool names), Kubernetes deployment (`helm`), regulated file transfer and remote execution (`ssh-transfer` — the canonical **Move** pack; an upload is potential egress, which DC2D deployments should pair with egress controls), financial rails (`stripe` — payment data is never internal, and money movement is restricted), and identity/secrets (`vault` — the §12.5 showcase, where reading a secret is itself the exfiltration risk and classifies as Read on `restricted`). Restricted-tier *reads* are profile-gated (they need an explicit Read grant on `restricted`), while restricted-tier Change/Delete rows are floor-blocked outright. The CLI-shaped packs (`helm`, `ssh-transfer`, `stripe`, `vault`) govern their binaries both as direct tools and inside shell commands; as with the developer-toolchain family, packs sharing a shell tool name (`bash`, `sh`, ...) **compose** in a single registry — per call, the pack whose rules match governs with its own capability ceiling, falling through to the next pack on no-match — so these packs can be loaded alongside the developer-toolchain (and `shell`) packs on the same `bash` tool without one overwriting another.

### `helm`

> RMACD classification for the Helm CLI (Kubernetes package manager), both as a direct tool and inside shell commands. Read-only chart and release inspection (list/status/get/history/search/show/template/lint) stays internal; repo add and chart pulls are Add on internal; install creates a release and is Add on confidential; upgrade and rollback mutate a running release and are Change on confidential. Uninstall deletes a release — Delete on restricted, so the §12.5 floor prohibits it autonomously. Registry login, chart push, and plugin management (plugins execute arbitrary code) land on the restricted tier.

**Version** 1.0.0 · **Family** Enterprise operations · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

**Matches tools:** `helm`  
**Parses argument:** `command` (strips wrappers: `sudo`, `env`)  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `list`, `ls`, `status`, `get`, `history`, `hist`, `search`, `show`, `inspect`, `template`, `lint`, `verify`, `version`, `env`, `help`, `completion` |
| **A** Add | `install`, `create`, `package`, `pull`, `fetch`, `add` |
| **C** Change | `upgrade`, `rollback`, `update`, `push`, `login`, `logout` |
| **D** Delete | `uninstall`, `delete`, `del` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `internal`  
**Target template:** `helm://{command}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

**Matches tools:** `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command`  
**Parses argument:** `command` (strips wrappers: `sudo`, `env`)  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `list`, `ls`, `status`, `get`, `history`, `hist`, `search`, `show`, `inspect`, `template`, `lint`, `verify`, `version`, `env`, `help`, `completion` |
| **A** Add | `install`, `create`, `package`, `pull`, `fetch`, `add` |
| **C** Change | `upgrade`, `rollback`, `update`, `push`, `login`, `logout` |
| **D** Delete | `uninstall`, `delete`, `del` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `internal`  
**Target template:** `helm://{command}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

| Operation | Tools | Data tier | Target |
|-----------|-------|-----------|--------|
| **A** Add | `helm` | `confidential` | — |
| **A** Add | `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `confidential` | — |
| **C** Change | `helm` | `confidential` | — |
| **C** Change | `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `confidential` | — |
| **D** Delete | `helm` | `restricted` | — |
| **D** Delete | `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |

**Tier overlays** (raise the data tier when the command matches; operation comes from the base rule):

| Applies when | Raises tier to |
|--------------|----------------|
| `command` matches `(^|\s)(registry\s+(login|logout)|plugin\s+(install|uninstall|update)|push)\b` | `restricted` |
| `command` matches `\bhelm\b[^|;&]*\s(registry\s+(login|logout)|plugin\s+(install|uninstall|update)|push)\b` | `restricted` |

### `servicenow`

> RMACD classification for ServiceNow MCP/REST tool surfaces (ITSM, change management, CMDB). There is no canonical ServiceNow CLI, so this pack targets the common MCP/REST tool names, mirroring the 'jira'/'confluence' pack shape. Record queries and gets are Read on internal (generic table access consults the servicenow_table_tier resolver, fail-closed to confidential); incident/request creation and work notes are Add on internal; incident update/assign/resolve is Change on confidential. Change management is the control point: creating a change request is Add on confidential, but approving one or forcing its state transition is Change on restricted — CAB approval is a human act, and an agent approving its own change requests must never happen autonomously, so the §12.5 floor prohibits it. Record deletion and CMDB CI deletion are Delete on restricted.

**Version** 1.0.0 · **Family** Enterprise operations · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

**Resolvers** (live tier lookups, fail-closed):

- `servicenow_table_tier` — Resolve a ServiceNow table name to its data classification (fail-closed default: `confidential`)

| Operation | Tools | Data tier | Target |
|-----------|-------|-----------|--------|
| **R** Read | `search_records`, `get_record`, `query_records`, `list_records` | resolver `servicenow_table_tier` from `table`; otherwise `internal` | `servicenow://{table}/{sys_id}` |
| **R** Read | `get_incident`, `search_incidents`, `list_incidents`, `get_request`, `list_requests`, `get_user`, `list_users`, `get_change_request`, `list_change_requests`, `get_knowledge_article`, `search_knowledge_base` | `internal` | `servicenow://{number}` |
| **A** Add | `create_incident`, `create_request`, `add_comment`, `add_work_note`, `create_knowledge_article` | `internal` | `servicenow://{number}` |
| **A** Add | `create_record` | resolver `servicenow_table_tier` from `table`; otherwise `internal` | `servicenow://{table}` |
| **C** Change | `update_record` | resolver `servicenow_table_tier` from `table`; otherwise `internal` | `servicenow://{table}/{sys_id}` |
| **C** Change | `update_incident`, `assign_incident`, `resolve_incident`, `close_incident`, `update_request`, `close_request` | `confidential` | `servicenow://incident/{number}` |
| **A** Add | `create_change_request`, `add_change_task`, `submit_change_for_approval` | `confidential` | `servicenow://change_request/{number}` |
| **C** Change | `update_change_request`, `update_change_task`, `schedule_change_request` | `confidential` | `servicenow://change_request/{number}` |
| **C** Change | `approve_change`, `reject_change`, `approve_change_request`, `reject_change_request`, `transition_change_state` | `restricted` | `servicenow://change_request/{number}` |
| **D** Delete | `delete_record`, `delete_incident`, `delete_request`, `delete_change_request`, `delete_cmdb_ci`, `delete_ci`, `delete_knowledge_article` | `restricted` | `servicenow://{table}/{sys_id}` |

### `ssh-transfer`

> RMACD classification for remote shells and file transfer: ssh, scp, sftp, rsync, and the SSH credential tooling (ssh-keygen/ssh-copy-id/ssh-agent/ssh-add), both as direct tools and inside shell commands. This is the canonical Move pack: scp/sftp/rsync transfers relocate data across a host boundary and classify as Move on confidential — note the direction, an upload is potential egress, so DC2D deployments should pair this pack with egress controls. rsync --delete (and --remove-source-files) is Delete on confidential. A plain 'ssh host cmd' executes an opaque remote command this pack cannot parse — it fails closed to Change on confidential and the capability ceiling applies (mirror of the 'make' pack's opaque-execution posture); govern the remote side with its own agent profile where possible. Key generation, key installation, and agent operations are the credential surface: Change on restricted, so the §12.5 floor prohibits them autonomously.

**Version** 1.0.0 · **Family** Enterprise operations · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

| Operation | Tools | Data tier | Target |
|-----------|-------|-----------|--------|
| **M** Move | `scp`, `sftp`, `rsync` | `confidential` | `transfer://{command}` |
| **M** Move | `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `confidential` | `transfer://{command}` |
| **D** Delete | `rsync` | `confidential` | — |
| **D** Delete | `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `confidential` | — |
| **C** Change | `ssh` | `confidential` | `ssh://{command}` |
| **C** Change | `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `confidential` | `ssh://{command}` |
| **C** Change | `ssh-keygen`, `ssh-copy-id`, `ssh-agent`, `ssh-add` | `restricted` | `ssh://{command}` |
| **C** Change | `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | `ssh://{command}` |

### `stripe`

> RMACD classification for the Stripe CLI, both as a direct tool and inside shell commands. Payment data is never internal: reads of live resources (customers, charges, invoices — list/get/retrieve) are Read on confidential, resource creation (customers, products, prices, invoices) is Add on confidential, and updates (subscriptions, webhook endpoints) are Change on confidential. Money movement — refunds, payouts, transfers, top-ups, reversals — is the financial rail: mutations there are Change on restricted so the §12.5 floor prohibits them autonomously, and even reads of that surface are restricted (profile-gated). Credential operations (login/logout/config, API keys) and connected-account mutations are restricted. Local test-mode tooling (listen, trigger, samples, fixtures) stays on internal.

**Version** 1.0.0 · **Family** Enterprise operations · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

**Matches tools:** `stripe`  
**Parses argument:** `command` (strips wrappers: `sudo`, `env`)  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `list`, `retrieve`, `get`, `search`, `status`, `version`, `help`, `open`, `listen`, `logs`, `tail` |
| **A** Add | `create`, `add`, `trigger` |
| **C** Change | `update`, `confirm`, `capture`, `attach`, `detach`, `finalize`, `pay`, `send`, `login`, `logout`, `config` |
| **D** Delete | `delete`, `cancel`, `void`, `close` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `internal` when `command` matches `(^|\s)(listen|trigger|samples|fixtures)\b`; otherwise `confidential`  
**Target template:** `stripe://{command}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

**Matches tools:** `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command`  
**Parses argument:** `command` (strips wrappers: `sudo`, `env`)  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `list`, `retrieve`, `get`, `search`, `status`, `version`, `help`, `open`, `listen`, `logs`, `tail` |
| **A** Add | `create`, `add`, `trigger` |
| **C** Change | `update`, `confirm`, `capture`, `attach`, `detach`, `finalize`, `pay`, `send`, `login`, `logout`, `config` |
| **D** Delete | `delete`, `cancel`, `void`, `close` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `internal` when `command` matches `(^|\s)(listen|trigger|samples|fixtures)\b`; otherwise `confidential`  
**Target template:** `stripe://{command}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

| Operation | Tools | Data tier | Target |
|-----------|-------|-----------|--------|
| **C** Change | `stripe` | `restricted` | — |
| **C** Change | `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |
| **C** Change | `stripe` | `restricted` | — |
| **C** Change | `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |

**Tier overlays** (raise the data tier when the command matches; operation comes from the base rule):

| Applies when | Raises tier to |
|--------------|----------------|
| `command` matches `(^|\s)(refunds?|payouts?|transfers?|topups?|reversals?)\b` | `restricted` |
| `command` matches `\bstripe\b[^|;&]*\s(refunds?|payouts?|transfers?|topups?|reversals?)\b` | `restricted` |
| `command` matches `(^|\s)accounts?\s+(create|update|delete|reject)\b` | `restricted` |
| `command` matches `\bstripe\b[^|;&]*\saccounts?\s+(create|update|delete|reject)\b` | `restricted` |

### `vault`

> RMACD classification for the HashiCorp Vault CLI, both as a direct tool and inside shell commands. This pack is the §12.5 showcase: every Vault operation lands on at least the confidential tier, because everything Vault touches is a secret or the machinery that guards one. Reading a secret (kv get, read, unwrap) is Read on restricted — the read IS the exfiltration risk, so it is profile-gated rather than floor-blocked. Writing/patching secrets (kv put/patch) is Change on restricted and deleting/destroying them (kv delete/destroy, secrets disable) is Delete on restricted, so the §12.5 immutable floor makes them structurally impossible for autonomous agents. Policy writes, auth-method changes, token create/revoke, login, and operator commands (seal/unseal/rekey/raft) are likewise restricted-tier mutations. Benign surface (status, token lookup-self, list) stays Read on confidential.

**Version** 1.0.0 · **Family** Enterprise operations · **Default operation** C · **Review status** ai-drafted · **LLM-assisted** yes

**Matches tools:** `vault`  
**Parses argument:** `command` (strips wrappers: `sudo`, `env`)  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `status`, `read`, `get`, `list`, `lookup`, `unwrap`, `help`, `version`, `path-help` |
| **C** Change | `write`, `put`, `patch`, `login`, `enable`, `tune`, `rotate`, `renew`, `rekey` |
| **D** Delete | `delete`, `destroy`, `disable`, `revoke` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `confidential`  
**Target template:** `vault://{command}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

**Matches tools:** `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command`  
**Parses argument:** `command` (strips wrappers: `sudo`, `env`)  

| Operation | Verbs |
|-----------|-------|
| **R** Read | `status`, `read`, `get`, `list`, `lookup`, `unwrap`, `help`, `version`, `path-help` |
| **C** Change | `write`, `put`, `patch`, `login`, `enable`, `tune`, `rotate`, `renew`, `rekey` |
| **D** Delete | `delete`, `destroy`, `disable`, `revoke` |
| *(unrecognised verb)* | defaults to **C** Change |

**Data tier:** `confidential`  
**Target template:** `vault://{command}`  
**Capability ceiling:** `R`, `M`, `A`, `C`, `D`  

| Operation | Tools | Data tier | Target |
|-----------|-------|-----------|--------|
| **C** Change | `vault` | `restricted` | — |
| **C** Change | `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |
| **D** Delete | `vault` | `restricted` | — |
| **D** Delete | `bash`, `sh`, `shell`, `zsh`, `run_command`, `execute_command` | `restricted` | — |

**Tier overlays** (raise the data tier when the command matches; operation comes from the base rule):

| Applies when | Raises tier to |
|--------------|----------------|
| `command` matches `(^|\s)(kv\s+get|read|unwrap)\b` | `restricted` |
| `command` matches `\bvault\b[^|;&]*\s(kv\s+get|read|unwrap)\b` | `restricted` |
| `command` matches `(^|\s)(policy\s+(write|delete)|auth\s+(enable|disable|tune)|secrets\s+(enable|disable|move|tune)|token\s+(create|revoke|renew)|operator|lease\s+revoke|audit\s+(enable|disable)|plugin\s+(register|deregister)|login|agent)\b` | `restricted` |
| `command` matches `\bvault\b[^|;&]*\s(policy\s+(write|delete)|auth\s+(enable|disable|tune)|secrets\s+(enable|disable|move|tune)|token\s+(create|revoke|renew)|operator|lease\s+revoke|audit\s+(enable|disable)|plugin\s+(register|deregister)|login|agent)\b` | `restricted` |

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
