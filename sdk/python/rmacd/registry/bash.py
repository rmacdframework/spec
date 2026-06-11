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
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

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

    def classify(self, non_flags: list[str], flags: set[str]) -> Operation:
        op = self.base
        if self.subcommands:
            # Scan *all* non-flag tokens (not just the first) for the strongest
            # matching subcommand. This is robust to a global option preceding
            # the verb — e.g. `git -C dir commit` or `kubectl -n ns delete`,
            # where the flag's value would otherwise be mistaken for the verb
            # and under-classify the call.
            matched = [self.subcommands[t] for t in non_flags if t in self.subcommands]
            if matched:
                op = max(matched, key=lambda o: _RANK[o])
        for flag, level in self.elevate_flags.items():
            if flag in flags:
                op = _max_op(op, level)
        if self.view_flags & flags:
            op = Operation.READ  # view/read-only mode overrides
        return op


# Wrappers to strip from the front of a segment before reading the real binary.
_WRAPPERS = {
    "sudo", "doas", "env", "nice", "nohup", "time", "ionice", "stdbuf",
    "command", "builtin", "exec", "xargs", "setsid", "timeout",
    "watch", "strace", "ltrace", "chrt",
}
# Shell control keywords that *precede* a real command in the same segment
# (`if grep …`, `then rm …`, `do mv …`, `! test …`). Stripped like wrappers —
# critical: without this, `do rm $f` reads `do` as an unknown binary and
# fail-closes to Change, *hiding* the Delete behind it.
_SHELL_KEYWORD_PREFIX = {"if", "elif", "while", "until", "then", "else", "do", "!"}
# Keywords/segments that carry no command of their own: loop/branch closers and
# the `for`/`case`/`select` headers (`for f in a b c` — the body arrives in a
# later `;`-split segment; any $(...) in the header was already extracted).
_SHELL_KEYWORD_NOOP = {"fi", "done", "esac", "{", "}", "break", "continue"}
# Segments that are a complete read-only construct by themselves: loop/case
# headers (`for f in a b c` — the body arrives in a later split segment) and
# test expressions (`[ -f x ]`, `[[ … ]]`, `:`), whose arguments must not be
# misread as a binary.
_SHELL_TERMINAL_READ = {"for", "case", "select", "function", "[", "[[", ":"}
# Wrappers that take a leading positional value before the command (a duration,
# priority, etc.) — `timeout 5 cmd`, `nice 10 cmd`, `chrt 1 cmd`.
_WRAPPER_TAKES_VALUE = {"timeout", "nice", "ionice", "chrt", "setsid"}
# Per-wrapper option flags that consume a separate value token (so the value is
# not mistaken for the wrapped binary, e.g. `sudo -u root rm` → -u eats `root`).
_WRAPPER_VALUE_FLAGS = {
    "sudo": {"-u", "-g", "-p", "-C", "-r", "-t", "-T", "-U", "-R", "-h",
             "--user", "--group", "--prompt", "--chdir", "--chroot"},
    "doas": {"-u", "-C"},
    "timeout": {"-s", "-k", "--signal", "--kill-after"},
    "nice": {"-n", "--adjustment"},
    "ionice": {"-c", "-n", "--class", "--classdata"},
    "env": {"-u", "--unset", "-C", "--chdir"},
    "stdbuf": {"-i", "-o", "-e", "--input", "--output", "--error"},
    "chrt": {"-p"},
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
    "zip": A, "unzip": A,
    # Change (mutate existing state)
    "chmod": C, "chown": C, "chgrp": C, "ed": C, "emacs": C, "dd": C,
    "truncate": C,
    "patch": C, "kill": C, "pkill": C, "killall": C, "mount": C, "umount": C,
    "sysctl": C, "crontab": C, "iptables": C, "setfacl": C, "usermod": C,
    "passwd": C, "nsupdate": C,
    # Delete
    "rm": D, "rmdir": D, "shred": D, "unlink": D, "wipe": D,
    # Accounts: creating is Add, removing is Delete.
    "useradd": A, "adduser": A, "groupadd": A, "addgroup": A,
    "userdel": D, "deluser": D, "groupdel": D, "delgroup": D,
    # Disk/filesystem destruction and host-level state changes.
    "mkswap": D, "wipefs": D, "cfdisk": D,
    "swapon": C, "swapoff": C,
    "shutdown": C, "reboot": C, "halt": C, "poweroff": C,
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
    "rsync": CmdRule(
        base=M,
        elevate_flags={"--delete": D, "--delete-after": D, "--delete-before": D},
    ),
    # wget: downloads/writes files; --spider only checks existence.
    "wget": CmdRule(base=A, view_flags={"--spider"}),
    # tar: creates/extracts (Add), but --remove-files / --delete destroy data.
    "tar": CmdRule(base=A, elevate_flags={"--remove-files": D, "--delete": D}),
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
    # partition editors: rewriting a partition table destroys data, but the
    # ubiquitous `-l` / `--list` invocation is a pure Read.
    "fdisk": CmdRule(base=D, view_flags={"-l", "--list"}),
    "sfdisk": CmdRule(base=D, view_flags={"-l", "--list", "-d", "--dump"}),
    "gdisk": CmdRule(base=D, view_flags={"-l"}),
    "parted": CmdRule(base=D, view_flags={"-l", "--list"}),
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

# A redirect *token* → a write (Change): `>`, `>f`, `>>`, `2>`, `&>` (matched
# at the start of a post-shlex token, so a quoted `>` or a `->` arrow — which
# stay mid-token after quote removal — are not mistaken for redirects).
_REDIRECT_RE = re.compile(r"(?:\d*|&)>>?")
# Command substitution ($(...) / `...`) and process substitution (<(...) / >(...))
# — all run an inner command that must be classified.
_SUBSHELL_RE = re.compile(r"\$\(([^()]*)\)|`([^`]*)`|[<>]\(([^()]*)\)")
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

    # Pull out and recurse into $(...) / `...` sub-commands first. Extract
    # iteratively from the innermost out so nested substitutions are not
    # silently dropped (the regex can't match an outer $(...) that still
    # contains parens).
    inner, stripped = _extract_subshells(command)

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


def _extract_subshells(command: str) -> tuple[list[str], str]:
    """Iteratively extract `$(...)` / backtick sub-commands, innermost first.

    Returns (inner_commands, command_with_subshells_blanked). Repeating until
    no match means a nested ``$(outer $(inner))`` is fully unwrapped rather than
    left embedded (which would hide a dangerous inner binary from the parser).
    """
    inner: list[str] = []
    prev = None
    while prev != command:
        prev = command
        found = [g for pair in _SUBSHELL_RE.findall(command) for g in pair if g]
        if not found:
            break
        inner.extend(found)
        command = _SUBSHELL_RE.sub(" ", command)
    return inner, command


def _classify_segment(seg: str, default: Operation) -> tuple[Operation, str, str]:
    try:
        tokens = shlex.split(seg, comments=True)
    except ValueError:
        tokens = seg.split()

    # A redirect (a token like `>`, `>>`, `2>`, `&>`) writes a file → the
    # segment is at least a Change. Detect from *tokens* (after quote removal)
    # so a `>` inside a quoted string or a `->` arrow is not a false positive.
    redirect = any(_REDIRECT_RE.match(t) for t in tokens)
    tokens = [t for t in tokens if not _REDIRECT_RE.match(t)]

    # drop env assignments (VAR=value) and wrapper commands from the front. Some
    # wrappers take their own options and/or a value before the real command
    # (`timeout 5 cmd`, `nice -n 10 cmd`, `ionice -c2 cmd`) — consume those too,
    # otherwise the wrapper's argument is mistaken for the binary and the real
    # command (e.g. `rm`) is never classified.
    while tokens:
        t = tokens[0]
        base = t.rsplit("/", 1)[-1]
        if "=" in t and re.match(r"^\w+=", t):
            tokens = tokens[1:]
            continue
        if base in _SHELL_TERMINAL_READ:
            # `for f in a b c` / `case $x in` / `[ -f x ]` — no command here.
            return (Operation.READ, base, f"shell '{base}' construct (no command)")
        if base in _SHELL_KEYWORD_PREFIX or base in _SHELL_KEYWORD_NOOP:
            # control keyword — the real command (if any) follows it.
            tokens = tokens[1:]
            continue
        if base in _WRAPPERS:
            tokens = tokens[1:]
            valflags = _WRAPPER_VALUE_FLAGS.get(base, set())
            while tokens and tokens[0].startswith("-"):  # the wrapper's own flags
                f = tokens[0]
                tokens = tokens[1:]
                # a wrapper flag that takes a separate value (sudo -u root,
                # timeout -s TERM): consume the value so it isn't read as the
                # binary. `=`-joined values are already part of the flag token.
                if f.split("=", 1)[0] in valflags and "=" not in f \
                        and tokens and not tokens[0].startswith("-"):
                    tokens = tokens[1:]
            # a leading duration/value for timeout/nice/etc. (e.g. `timeout 5`)
            if base in _WRAPPER_TAKES_VALUE and tokens and re.match(r"^[0-9]", tokens[0]):
                tokens = tokens[1:]
            continue
        break

    if not tokens:
        if redirect:
            return (Operation.CHANGE, "redirect", "shell redirect (>) writes a file")
        return (Operation.READ, "", "no command")

    binary = tokens[0].rsplit("/", 1)[-1]
    rest = tokens[1:]
    non_flags = [t for t in rest if not t.startswith("-")]
    # Build the flag set keeping whole tokens (so long flags like -delete /
    # --in-place match) AND expanding bundled short flags (-ni → -n, -i) so a
    # rule keyed on -i still fires. Critical: without this, `sed -ni` would
    # miss the -i elevation and under-classify an in-place edit as Read.
    flags: set[str] = set()
    for t in rest:
        if not t.startswith("-"):
            continue
        flags.add(t)
        if "=" in t:
            flags.add(t.split("=", 1)[0])  # --in-place=.bak → --in-place
        if not t.startswith("--") and len(t) > 2 and not t[1].isdigit():
            flags.update(f"-{ch}" for ch in t[1:] if ch.isalpha())

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
    noop = flags & {"--help", "--version", "--dry-run"}
    if noop:
        return (Operation.READ, f"{binary} ({sorted(noop)[0]} → no mutation)")

    # Cloud CLIs are "<tool> <group…> <verb> [args]" — scan the path tokens for
    # the strongest recognised verb (list/create/update/delete → R/A/C/D).
    if binary in ("aws", "gcloud", "az", "oci", "ibmcloud"):
        verbs: list[tuple[str, Operation]] = []
        for t in non_flags:
            if t in _CLOUD_VERB:
                verbs.append((t, _CLOUD_VERB[t]))
            else:
                # AWS uses hyphenated `verb-noun` verbs (terminate-instances,
                # delete-bucket, create-stack) — match the leading verb.
                head = t.split("-", 1)[0]
                if "-" in t and head in _CLOUD_VERB:
                    verbs.append((t, _CLOUD_VERB[head]))
        if verbs:
            tok, op = max(verbs, key=lambda pair: _RANK[pair[1]])
            return (op, f"{binary} … {tok}")
        return (Operation.CHANGE, f"{binary} (verb unmapped → Change)")

    # shell wrappers: classify the -c command string rather than treating the
    # whole `bash -c "rm -rf /"` as an opaque Change (which would under-classify
    # the Delete). Recurse into each non-flag arg and take the strongest.
    if binary in ("bash", "sh", "zsh", "dash", "ksh", "ash"):
        if flags & {"-c"} and non_flags:
            ops = [classify_bash_command(a, default=default).operation for a in non_flags]
            return (max(ops, key=lambda o: _RANK[o]), f"{binary} -c")
        return (default, binary)

    # eval runs its (joined) arguments as a command — classify them.
    if binary == "eval":
        sub = " ".join(non_flags)
        if sub:
            return (classify_bash_command(sub, default=default).operation, "eval")
        return (default, "eval")

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

    # awk/gawk: Read unless the program writes a file (print/printf > target),
    # appends (>>), or shells out (system()). A bare ">" is *not* enough — it is
    # usually a comparison (e.g. `$1 > 5`), so only a redirect off print/printf
    # counts, avoiding a false Change on read-only comparisons.
    if binary in ("awk", "gawk", "mawk"):
        program = " ".join(non_flags)
        writes = (
            "system(" in program
            or ">>" in program
            or re.search(r"\b(?:print|printf)\b[^;{}\n]*?>", program) is not None
        )
        if writes:
            return (Operation.CHANGE, "awk (writes a file / shells out)")
        return (Operation.READ, "awk")

    # mkfs and its dotted variants (mkfs.ext4, mkfs.xfs, …) format a device —
    # destroys everything on it. Prefix-matched so new variants are covered.
    if binary == "mkfs" or binary.startswith("mkfs."):
        return (Operation.DELETE, f"{binary} (formats a device)")

    if binary in _RULES:
        rule = _RULES[binary]
        op = rule.classify(non_flags, flags)
        verb = next((t for t in non_flags if t in rule.subcommands), subcommand)
        return (op, f"{binary} {verb or ''}".strip())

    if binary in _FIXED:
        return (_FIXED[binary], binary)

    if binary in _READ:
        return (Operation.READ, binary)

    # Unknown binary: fail closed.
    return (default, f"{binary} (unrecognised → fail-closed {default.value})")


def make_bash_classifier(
    default: Operation = Operation.CHANGE,
) -> Callable[[dict[str, Any]], tuple[Operation, None, str]]:
    """Return a ToolDefinition-compatible classifier for a Bash tool.

    Usage::

        from rmacd.registry import ToolDefinition, make_bash_classifier
        registry.register_tool(ToolDefinition(
            "Bash", "Shell", Operation.CHANGE,   # nominal level for indexing
            classifier=make_bash_classifier(),
        ))
        enforcer.enforce_tool_call("Bash", {"command": "rm -rf build/"})
    """

    def classify(args: dict[str, Any]) -> tuple[Operation, None, str]:
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
