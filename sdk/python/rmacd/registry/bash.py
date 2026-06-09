"""RMACD classifier for shell commands invoked through a ``Bash`` tool.

``bash`` is the hard case for governance: one tool, an opaque command string,
any action. The Claude Agent SDK's own answer is command-prefix scoping
(``Bash(npm *)``); this module adds the RMACD *semantics* on top — it parses a
command line and decides whether it is a Read, Move, Add, Change, or Delete.

How it classifies:

1. Split the line on shell operators (``|``, ``&&``, ``||``, ``;``, newlines)
   and pull out any ``$(...)`` / backtick sub-commands.
2. For each segment, strip wrappers (``sudo``, ``env VAR=v``, ``nice``,
   ``nohup``, ``time``, ``xargs``), then read ``(binary, subcommand, flags)``.
3. Look the binary up in a curated table. A binary may classify as a fixed
   operation (``rm`` → Delete), by **subcommand** (``git commit`` → Change,
   ``git log`` → Read), or be elevated by a **flag** (``sed`` → Read, but
   ``sed -i`` → Change).
4. A shell **redirect** (``>`` / ``>>``) is itself a write, so it raises the
   segment to at least Change.
5. The result is the **maximum** operation across every segment and
   sub-command — a pipeline is as risky as its riskiest element.
6. An **unknown binary fails closed** to a configurable default (Change), so an
   unrecognised command is never silently treated as a harmless Read.

This is a heuristic for governance and audit, **not** a security sandbox: it
does not execute the command and can be fooled by sufficiently creative
shell. Pair it with OS-level controls (the RMACD decision is defence in depth).
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field

from rmacd.models import Operation

# Operation risk ordering (R < M < A < C < D); higher = stronger.
_RANK = {
    Operation.READ: 0,
    Operation.MOVE: 1,
    Operation.ADD: 2,
    Operation.CHANGE: 3,
    Operation.DELETE: 4,
}
R, M, A, C, D = (
    Operation.READ,
    Operation.MOVE,
    Operation.ADD,
    Operation.CHANGE,
    Operation.DELETE,
)


def _max_op(a: Operation, b: Operation) -> Operation:
    return a if _RANK[a] >= _RANK[b] else b


@dataclass
class CmdRule:
    """Classification rule for one binary."""

    base: Operation
    # subcommand (first non-flag token) → operation, e.g. git/kubectl/aws.
    subcommands: dict[str, Operation] = field(default_factory=dict)
    # a flag whose presence raises the operation to at least this level
    # (e.g. sed -i → Change, find -delete → Delete).
    elevate_flags: dict[str, Operation] = field(default_factory=dict)
    # a flag whose presence FORCES the command to read-only, overriding the
    # base (e.g. pico -v / --view; vim -R). Scoped per-binary because the same
    # short flag means different things elsewhere (cp -v / rm -v = verbose).
    view_flags: set[str] = field(default_factory=set)

    def classify(self, subcommand: str | None, flags: set[str]) -> Operation:
        op = self.base
        if subcommand and subcommand in self.subcommands:
            op = self.subcommands[subcommand]
        for flag, level in self.elevate_flags.items():
            if flag in flags:
                op = _max_op(op, level)
        if self.view_flags & flags:
            op = Operation.READ  # view/read-only mode overrides
        return op


# Wrappers to strip from the front of a segment before reading the real binary.
_WRAPPERS = {
    "sudo", "doas", "env", "nice", "nohup", "time", "ionice", "stdbuf",
    "command", "builtin", "exec", "xargs", "nohup", "setsid", "timeout",
    "watch", "strace", "ltrace",
}

# Read-only binaries (observe / query — no state change).
_READ = {
    "cat", "less", "more", "head", "tail", "tac", "nl", "od", "hexdump", "xxd",
    "ls", "dir", "vdir", "stat", "file", "wc", "sort", "uniq", "cut", "tr",
    "column", "fold", "fmt", "pwd", "whoami", "id", "groups", "env", "printenv",
    "date", "cal", "uptime", "df", "du", "free", "ps", "top", "htop", "who",
    "w", "last", "uname", "hostname", "arch", "which", "type", "whereis",
    "locate", "grep", "egrep", "fgrep", "rg", "ag", "ack", "basename",
    "dirname", "realpath", "readlink", "md5sum", "sha1sum", "sha256sum",
    "cksum", "b2sum", "diff", "cmp", "comm", "ping", "ping6", "traceroute",
    "tracepath", "mtr", "dig", "nslookup", "host", "whois", "getent",
    "netstat", "ss", "lsof", "ip", "ifconfig", "route", "arp", "jq", "yq",
    "echo", "printf", "true", "false", "test", "seq", "yes", "tty", "lsblk",
    "lscpu", "lsusb", "lspci", "blkid", "man", "info", "help",
    "history", "alias", "cd", "pushd", "popd", "dirs", "export", "set",
}

# Single-operation binaries (the whole command is this op regardless of flags).
_FIXED: dict[str, Operation] = {
    # Move
    "mv": M, "rename": M, "scp": M, "sftp": M,
    # Add (create)
    "cp": A, "mkdir": A, "touch": A, "ln": A, "tee": A, "install": A,
    "mktemp": A, "gzip": A, "gunzip": A, "bzip2": A, "xz": A,
    "zip": A, "unzip": A, "tar": A,
    # Change (mutate existing state)
    "chmod": C, "chown": C, "chgrp": C, "ed": C, "emacs": C, "dd": C,
    "truncate": C,
    "patch": C, "kill": C, "pkill": C, "killall": C, "mount": C, "umount": C,
    "sysctl": C, "crontab": C, "iptables": C, "setfacl": C, "usermod": C,
    "passwd": C, "nsupdate": C,
    # Delete
    "rm": D, "rmdir": D, "shred": D, "unlink": D, "wipe": D,
}

# Subcommand- and flag-driven binaries.
_RULES: dict[str, CmdRule] = {
    "git": CmdRule(
        base=R,
        subcommands={
            "clone": A, "init": A, "add": A, "mv": M, "rm": D, "commit": C,
            "push": C, "pull": C, "fetch": R, "log": R, "show": R,
            "status": R, "diff": R, "branch": R, "remote": R, "config": C,
            "checkout": C, "switch": C, "restore": C, "reset": C, "merge": C,
            "rebase": C, "stash": C, "tag": A, "clean": D, "revert": C,
            "cherry-pick": C, "apply": C, "blame": R, "describe": R,
            "rev-parse": R, "ls-files": R, "grep": R, "worktree": C,
        },
    ),
    "kubectl": CmdRule(
        base=C,  # conservative default for an unknown kubectl verb
        subcommands={
            "get": R, "describe": R, "logs": R, "top": R, "explain": R,
            "api-resources": R, "version": R, "config": R, "cluster-info": R,
            "port-forward": R, "cp": M, "create": A, "run": A, "apply": C,
            "edit": C, "patch": C, "scale": C, "set": C, "label": C,
            "annotate": C, "rollout": C, "drain": C, "cordon": C,
            "uncordon": C, "taint": C, "exec": C, "delete": D,
        },
    ),
    "docker": CmdRule(
        base=C,
        subcommands={
            "ps": R, "images": R, "logs": R, "inspect": R, "version": R,
            "info": R, "stats": R, "pull": A, "build": A, "create": A,
            "run": A, "tag": A, "start": C, "stop": C, "restart": C,
            "exec": C, "commit": C, "push": C, "cp": M, "rm": D, "rmi": D,
            "prune": D, "kill": C, "pause": C, "unpause": C,
        },
    ),
    "systemctl": CmdRule(
        base=C,
        subcommands={
            "status": R, "show": R, "list-units": R, "list-unit-files": R,
            "is-active": R, "is-enabled": R, "cat": R, "start": C, "stop": C,
            "restart": C, "reload": C, "enable": C, "disable": C, "mask": C,
            "unmask": C, "kill": C, "daemon-reload": C,
        },
    ),
    "service": CmdRule(base=C, subcommands={"status": R}),
    "apt": CmdRule(
        base=C,
        subcommands={
            "install": A, "remove": D, "purge": D, "autoremove": D,
            "update": R, "upgrade": C, "list": R, "search": R, "show": R,
            "policy": R,
        },
    ),
    "pip": CmdRule(
        base=C,
        subcommands={
            "install": A, "uninstall": D, "list": R, "show": R, "freeze": R,
            "download": A, "check": R,
        },
    ),
    "npm": CmdRule(
        base=C,
        subcommands={
            "install": A, "i": A, "ci": A, "uninstall": D, "remove": D,
            "rm": D, "update": C, "run": C, "ls": R, "view": R, "audit": R,
            "test": R, "publish": C,
        },
    ),
    # sed: prints (Read) unless editing in place.
    "sed": CmdRule(base=R, elevate_flags={"-i": C, "--in-place": C}),
    # find: Read unless it deletes or executes.
    "find": CmdRule(base=R, elevate_flags={"-delete": D, "-exec": C, "-execdir": C, "-ok": C}),
    # rsync: Move unless it deletes at the destination.
    "rsync": CmdRule(base=M, elevate_flags={"--delete": D, "--delete-after": D, "--delete-before": D}),
    # wget: downloads/writes files; --spider only checks existence.
    "wget": CmdRule(base=A, view_flags={"--spider"}),
    # text editors: edit & save → Change, unless opened in view/read-only mode.
    # (pico/nano: -v/--view; vim/vi: -R read-only, -M no-modify.)
    "pico": CmdRule(base=C, view_flags={"-v", "--view"}),
    "nano": CmdRule(base=C, view_flags={"-v", "--view"}),
    "vim": CmdRule(base=C, view_flags={"-R", "-M"}),
    "vi": CmdRule(base=C, view_flags={"-R", "-M"}),
    "nvim": CmdRule(base=C, view_flags={"-R", "-M"}),
    "view": CmdRule(base=R),  # vim read-only alias
    # ssh runs an opaque remote command — conservatively a Change.
    "ssh": CmdRule(base=C),
    # package managers (yum/dnf mirror apt; brew too)
    "yum": CmdRule(base=C, subcommands={
        "install": A, "remove": D, "erase": D, "update": C, "upgrade": C,
        "downgrade": C, "list": R, "search": R, "info": R, "check-update": R,
        "history": R,
    }),
    "dnf": CmdRule(base=C, subcommands={
        "install": A, "remove": D, "erase": D, "update": C, "upgrade": C,
        "downgrade": C, "list": R, "search": R, "info": R, "history": R,
    }),
    "brew": CmdRule(base=C, subcommands={
        "install": A, "uninstall": D, "remove": D, "rm": D, "upgrade": C,
        "update": R, "list": R, "info": R, "search": R, "cleanup": D,
        "tap": A, "untap": D, "doctor": R,
    }),
    # infrastructure-as-code / orchestration
    "terraform": CmdRule(base=C, subcommands={
        "validate": R, "plan": R, "show": R, "output": R, "providers": R,
        "version": R, "graph": R, "console": R, "get": R, "fmt": C, "init": A,
        "apply": C, "destroy": D, "import": C, "taint": C, "untaint": C,
        "refresh": C, "state": C,
    }),
    "helm": CmdRule(base=C, subcommands={
        "install": A, "upgrade": C, "uninstall": D, "delete": D, "rollback": C,
        "list": R, "get": R, "status": R, "history": R, "show": R,
        "template": R, "lint": R, "repo": R, "search": R, "pull": A,
        "package": A, "test": R,
    }),
    "ansible": CmdRule(base=C, view_flags={"--check"}),
    "ansible-playbook": CmdRule(base=C, view_flags={"--check"}),
    "make": CmdRule(base=C, view_flags={"-n", "--dry-run", "--just-print", "--recon"}),
    # database clients: SQL is opaque, so conservatively Change. A pure export
    # (mysqldump / pg_dump) is a Read.
    "psql": CmdRule(base=C),
    "mysql": CmdRule(base=C),
    "sqlite3": CmdRule(base=C),
    "mongo": CmdRule(base=C),
    "mongosh": CmdRule(base=C),
    "redis-cli": CmdRule(base=C),
    "mysqldump": CmdRule(base=R),
    "pg_dump": CmdRule(base=R),
}

# Cloud-CLI verbs (aws/gcloud/az/...): map a recognised verb to an operation.
_CLOUD_VERB = {
    # Read
    "ls": R, "list": R, "describe": R, "get": R, "show": R, "head": R,
    "read": R, "view": R, "status": R, "logs": R, "tail": R, "watch": R,
    "export": R, "diff": R, "validate": R, "check": R, "wait": R,
    # Move / Add
    "cp": A, "copy": A, "mv": M, "mb": A, "rb": D, "create": A, "new": A,
    "add": A, "deploy": A, "import": C, "provision": A, "init": A,
    "sync": C, "apply": C, "submit": A, "push": C, "publish": C,
    # Change
    "put": C, "update": C, "modify": C, "patch": C, "set": C, "edit": C,
    "replace": C, "enable": C, "disable": C, "start": C, "stop": C,
    "restart": C, "scale": C, "rollback": C, "tag": A, "label": C,
    "attach": C, "detach": C, "ssh": C, "exec": C, "run": A, "invoke": C,
    "rotate": C, "reset": C,
    # Delete
    "delete": D, "remove": D, "destroy": D, "rm": D, "terminate": D,
    "purge": D, "uninstall": D, "drop": D, "deregister": D,
}

# Redirect / append → a write (Change). 2>file, >file, >>file all count.
_REDIRECT_RE = re.compile(r"(?<![0-9<>])\d*>>?")
_SUBSHELL_RE = re.compile(r"\$\(([^()]*)\)|`([^`]*)`")
_SPLIT_RE = re.compile(r"\|\||&&|[|;\n]")


@dataclass
class BashClassification:
    """Result of classifying a shell command line."""

    operation: Operation
    binary: str  # the riskiest binary that drove the decision
    detail: str  # human-readable explanation

    def as_tuple(self) -> tuple[Operation, None, str]:
        """Shape for a ToolDefinition classifier: (operation, tier, target)."""
        return (self.operation, None, f"bash:{self.binary}")


def classify_bash_command(
    command: str,
    *,
    default: Operation = Operation.CHANGE,
) -> BashClassification:
    """Classify a shell command line into a single RMACD operation.

    Returns the **maximum** operation across all segments, sub-shells, and
    redirects. Unknown binaries classify as ``default`` (Change) — fail closed.
    """
    if not command or not command.strip():
        return BashClassification(Operation.READ, "", "empty command")

    best_op = Operation.READ
    best_bin = ""
    best_detail = "no recognised action"
    saw_anything = False

    # Pull out and recurse into $(...) / `...` sub-commands first.
    inner = [g for pair in _SUBSHELL_RE.findall(command) for g in pair if g]
    stripped = _SUBSHELL_RE.sub(" ", command)

    for segment in _SPLIT_RE.split(stripped):
        seg = segment.strip()
        if not seg:
            continue
        saw_anything = True
        op, binary, detail = _classify_segment(seg, default)
        if _RANK[op] >= _RANK[best_op]:
            best_op, best_bin, best_detail = op, binary, detail

    for sub in inner:
        c = classify_bash_command(sub, default=default)
        if _RANK[c.operation] >= _RANK[best_op]:
            best_op, best_bin = c.operation, c.binary
            best_detail = f"sub-command: {c.detail}"

    if not saw_anything and not inner:
        return BashClassification(Operation.READ, "", "empty command")
    return BashClassification(best_op, best_bin, best_detail)


def _classify_segment(seg: str, default: Operation) -> tuple[Operation, str, str]:
    # A redirect makes the segment at least a write.
    redirect = bool(_REDIRECT_RE.search(seg))

    try:
        tokens = shlex.split(seg, comments=True)
    except ValueError:
        tokens = seg.split()
    # drop env assignments (VAR=value) and wrapper commands from the front
    while tokens:
        t = tokens[0]
        base = t.rsplit("/", 1)[-1]
        if "=" in t and re.match(r"^\w+=", t):
            tokens = tokens[1:]
            continue
        if base in _WRAPPERS:
            tokens = tokens[1:]
            continue
        break

    if not tokens:
        if redirect:
            return (Operation.CHANGE, "redirect", "shell redirect (>) writes a file")
        return (Operation.READ, "", "no command")

    binary = tokens[0].rsplit("/", 1)[-1]
    rest = tokens[1:]
    flags = {t for t in rest if t.startswith("-")}
    non_flags = [t for t in rest if not t.startswith("-")]

    op, detail = _classify_binary(binary, non_flags, flags, default)
    if redirect:
        op = _max_op(op, Operation.CHANGE)
        detail += " + redirect(>)"
    return (op, binary, detail)


def _classify_binary(
    binary: str, non_flags: list[str], flags: set[str], default: Operation
) -> tuple[Operation, str]:
    subcommand = non_flags[0] if non_flags else None

    # --help / --version / --dry-run never mutate — print-and-exit or simulate.
    # (Only the long forms are safe to treat globally: short -h/-v/-V/-n mean
    # other things for many commands, e.g. ls -h, cp -v, cat -n.)
    if flags & {"--help", "--version", "--dry-run"}:
        return (Operation.READ, f"{binary} ({(flags & {'--help', '--version', '--dry-run'}).pop()} → no mutation)")

    # Cloud CLIs are "<tool> <group…> <verb> [args]" — scan the path tokens for
    # the strongest recognised verb (list/create/update/delete → R/A/C/D).
    if binary in ("aws", "gcloud", "az", "oci", "ibmcloud"):
        verbs = [(t, _CLOUD_VERB[t]) for t in non_flags if t in _CLOUD_VERB]
        if verbs:
            tok, op = max(verbs, key=lambda pair: _RANK[pair[1]])
            return (op, f"{binary} … {tok}")
        return (Operation.CHANGE, f"{binary} (verb unmapped → Change)")

    # curl: Read (GET) unless it writes a local file or mutates a remote.
    if binary == "curl":
        op = Operation.READ
        if flags & {"-o", "-O", "--output", "--remote-name"}:
            op = _max_op(op, Operation.ADD)
        if flags & {"-T", "--upload-file", "-d", "--data", "--data-raw",
                    "--data-binary", "-F", "--form"}:
            op = _max_op(op, Operation.CHANGE)  # request body ⇒ POST/PUT-style
        if flags & {"-X", "--request"}:
            methods = {t.upper() for t in non_flags}
            if "DELETE" in methods:
                op = _max_op(op, Operation.DELETE)
            elif methods & {"POST", "PUT", "PATCH"}:
                op = _max_op(op, Operation.CHANGE)
        return (op, "curl")

    # awk/gawk: Read unless the program writes a file or shells out.
    if binary in ("awk", "gawk", "mawk"):
        program = " ".join(non_flags)
        if "system(" in program or ">" in program or "print" in program and ">>" in program:
            return (Operation.CHANGE, "awk (writes a file / shells out)")
        return (Operation.READ, "awk")

    if binary in _RULES:
        rule = _RULES[binary]
        op = rule.classify(subcommand, flags)
        return (op, f"{binary} {subcommand or ''}".strip())

    if binary in _FIXED:
        return (_FIXED[binary], binary)

    if binary in _READ:
        return (Operation.READ, binary)

    # Unknown binary: fail closed.
    return (default, f"{binary} (unrecognised → fail-closed {default.value})")


def make_bash_classifier(default: Operation = Operation.CHANGE):
    """Return a ToolDefinition-compatible classifier for a Bash tool.

    Usage::

        from rmacd.registry import ToolDefinition, make_bash_classifier
        registry.register_tool(ToolDefinition(
            "Bash", "Shell", Operation.CHANGE,   # nominal level for indexing
            classifier=make_bash_classifier(),
        ))
        enforcer.enforce_tool_call("Bash", {"command": "rm -rf build/"})
    """

    def classify(args: dict) -> tuple[Operation, None, str]:
        command = ""
        if isinstance(args, dict):
            command = str(args.get("command") or args.get("cmd") or "")
        return classify_bash_command(command, default=default).as_tuple()

    return classify


__all__ = [
    "BashClassification",
    "classify_bash_command",
    "make_bash_classifier",
]
