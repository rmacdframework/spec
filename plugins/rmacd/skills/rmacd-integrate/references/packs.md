# Governance packs

A governance pack is a declarative, versionable, signable set of rules that classifies
a family of tools into RMACD terms: each rule matches tools (exact name, glob, or
regex) and arguments, and yields `(operation, tier, target)` plus a capability ceiling.
Packs replace hand-written classifier lambdas and survive tool-surface drift.

## Built-in packs

The SDK bundles packs as wheel data (`rmacd/packs/data/`). Enumerate the installed
set — it grows across releases:

```python
from rmacd.packs import builtin_pack_names
print(builtin_pack_names())
```

As of SDK 0.13 there are 34 built-ins: `aws`, `aws-api-mcp`, `aws-iam`, `az`,
`az-identity`, `azure-mcp`, `boto3`, `confluence`, `docker`, `filesystem`, `gcloud`,
`gcp-iam`, `gcp-toolbox`, `gh`, `git`, `github`, `gitlab`, `google-drive`, `helm`,
`jira`, `kubectl`, `make`, `ms365`, `npm`, `pip-uv`, `postgres`, `servicenow`,
`shell`, `slack`, `sql`, `ssh-transfer`, `stripe`, `terraform`, `vault`.

## Loading packs — the one-liner

```python
from rmacd.packs import load_packs
from rmacd import PolicyEnforcer

registry = load_packs(["shell", "github", "./packs/internal-mcp.json"])
enforcer = PolicyEnforcer(profile, agent_id="my-agent", registry=registry)
```

`load_packs` accepts built-in names, file paths (`.json`, or `.yaml`/`.yml` with the
`[yaml]` extra), dicts, or `GovernancePack` objects, and returns a `ToolsRegistry`
ready for `enforce_tool_call`. Pass `registry=` to extend an existing registry.

**Packs that share a tool name compose.** Several packs legitimately govern the same
shell tool (`git`, `docker`, `terraform`, `make`, `shell` all overlay `bash`);
`apply_pack` chains them in load order instead of replacing. Per call, the pack whose
rules match governs — with *its own* capability ceiling, never a union across packs —
falling through on no-match to the next pack and finally to any tool registered before
the packs. A pack's broad tool-name-only fallback rule never shadows another pack's
specific claim, so `load_packs(["shell", "git", "docker", "terraform"])` just works.
Re-loading a pack replaces its own chain entry (idempotent); a direct
`registry.register_tool` still replaces outright.

**Glob/regex rules register nothing by themselves** — a pack that matches
`repos_*` cannot know which concrete tools exist. Supply the live tool list:

```python
from rmacd.packs import load_pack, apply_pack
pack = load_pack("github")
apply_pack(registry, pack, tool_names=[t["name"] for t in tools_list["tools"]])
```

Otherwise only the pack's exact-named tools are registered (the loader logs a warning
listing the glob rules that governed nothing).

## Production posture: require signed packs

Built-in packs ship unsigned. In production, load only packs signed by keys you trust:

```python
registry = load_packs(
    ["./packs/internal-mcp.json"],
    require_signed=True,
    trusted_keys=open("keys/pack-signing.pub.pem").read(),
)
```

An unsigned or tampered pack raises `PackSignatureError` — the agent fails to start
rather than running under unreviewed rules.

## Authoring a pack for an internal MCP server

The classify → review → sign flow:

```bash
# 1. Capture the server's tools/list response to tools.json, then AI-compile a pack.
#    --llm uses the Claude classifier (rmacd-framework[llm], reads ANTHROPIC_API_KEY);
#    omit it for the deterministic keyword heuristic only.
rmacd classify tools.json -n internal-mcp --llm -o packs/internal-mcp.json

# 2. Review what the compiler was unsure about (low-confidence or delete-capable
#    rules are flagged). Edit the pack until this list is empty or accepted.
rmacd pack review packs/internal-mcp.json

# 3. Validate (schema + regex/ReDoS safety lint).
rmacd pack validate packs/internal-mcp.json

# 4. Freeze and Ed25519-sign.
rmacd pack sign packs/internal-mcp.json -k keys/pack-signing.pem
rmacd pack verify packs/internal-mcp.json -k keys/pack-signing.pub.pem

# Later: detect drift when the server's tool surface changes.
rmacd pack diff packs/internal-mcp.json tools.json
```

The LLM step is **advisory and authoring-time only**: it proposes rules that a human
reviews and signs. At runtime, enforcement is deterministic — the signed pack's rules,
the tool capability ceiling, the profile, and the §12.5 floor decide; no model is
consulted.

## Quick alternative: MCPRegistryBridge

For prototyping, skip pack authoring and auto-classify at startup:

```python
from rmacd.registry import MCPRegistryBridge
bridge = MCPRegistryBridge(registry=registry)
bridge.register_mcp_tools(tools_list["tools"])
bridge.low_confidence_tools()   # review this tail by hand
```

Same classification engines, but nothing is reviewed or signed — prefer a signed pack
once the tool surface stabilises.
