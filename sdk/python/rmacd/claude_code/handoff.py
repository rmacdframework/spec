"""Decision handoff from the ``PreToolUse`` hook to ``PostToolUse``.

The two hooks are separate processes, so the execution record used to be built
by *re-deriving* everything the decision had already computed: `PostToolUse`
re-bound the session (profile, packs, registry) and re-mapped the tool call.
That was both slow and wrong.

Wrong first, because it is the more serious of the two. The mapping is not a
pure function of the tool call — ``Write`` maps to **Add** when the path does
not exist and **Change** when it does (``mapping.py``). By the time
`PostToolUse` runs, the file exists. Every file creation therefore produced a
decision record saying ``Add`` and an execution record saying ``Change``: two
rows that join on ``tool_use_id`` and contradict each other, in the half of the
product whose entire purpose is evidence.

Slow second: re-binding cost a second full session bind per tool call to answer
a question already answered.

So the decision travels forward instead. `PreToolUse` writes a small JSON
sidecar keyed by ``(session_id, tool_use_id)`` for calls that may actually run;
`PostToolUse` takes it, writes the execution record from it, and unlinks it. The
sidecar carries the resolved audit path too, so `PostToolUse` needs no binding
at all.

Sidecars are best-effort: a failure to write one costs an execution record, not
a decision. The decision half — the half that records denials — is written
inline by `PreToolUse` and never depends on this.

Orphans are expected and bounded. A call routed to ``ask`` that the user
declines never reaches `PostToolUse`, so its sidecar is never taken; a TTL sweep
on write reclaims them.
"""

from __future__ import annotations

import contextlib
import json
import os
import stat
import tempfile
import time
from pathlib import Path
from typing import Any

#: Sidecars older than this are swept. Comfortably longer than any plausible
#: gap between a tool's decision and its execution (an ``ask`` prompt can sit
#: unanswered for a long time), short enough that orphans do not accumulate.
TTL_SECONDS = 24 * 60 * 60

_DIR_PREFIX = "rmacd-handoff-"


def _sanitize(value: object) -> str | None:
    """A filesystem-safe form of an id, or None if it cannot be one.

    Ids come from the hook event, so they are untrusted input on a path: strip
    to an explicit safe alphabet rather than trying to reject bad cases.
    """
    if not isinstance(value, str) or not value:
        return None
    safe = "".join(ch for ch in value if ch.isalnum() or ch in "-_")[:64]
    return safe or None


def _session_dir(session_id: str) -> Path:
    return Path(tempfile.gettempdir()) / f"{_DIR_PREFIX}{session_id}"


def _ensure_dir(path: Path) -> bool:
    """Create the sidecar directory, refusing anything we do not own.

    The parent is a world-writable shared temp directory, so an existing entry
    at this path is not automatically ours — a symlink planted there would
    redirect every sidecar write. Verify with ``lstat`` (which does not follow
    the final component) that it is a real directory belonging to this user.
    """
    try:
        path.mkdir(mode=0o700, exist_ok=True)
        info = os.lstat(path)
    except OSError:
        return False
    if not stat.S_ISDIR(info.st_mode):
        return False
    return not (hasattr(os, "geteuid") and info.st_uid != os.geteuid())


def _sweep(directory: Path, now: float) -> None:
    """Unlink sidecars past their TTL. Never raises."""
    try:
        entries = list(os.scandir(directory))
    except OSError:
        return
    for entry in entries:
        try:
            if now - entry.stat().st_mtime > TTL_SECONDS:
                os.unlink(entry.path)
        except OSError:
            continue


def store(session_id: object, tool_use_id: object, payload: dict[str, Any]) -> bool:
    """Persist one decision for its `PostToolUse` counterpart. Best effort."""
    session = _sanitize(session_id)
    tool_use = _sanitize(tool_use_id)
    if session is None or tool_use is None:
        # Without both ids there is no join key, so an execution record could
        # not be correlated even if it were written.
        return False

    directory = _session_dir(session)
    if not _ensure_dir(directory):
        return False
    _sweep(directory, time.time())

    target = directory / f"{tool_use}.json"
    try:
        # O_NOFOLLOW so a symlink at the final component cannot redirect the
        # write; O_TRUNC rather than O_EXCL so a stale sidecar for a reused id
        # is replaced instead of blocking the current one.
        fd = os.open(
            target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600
        )
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
    except (OSError, TypeError, ValueError):
        return False
    return True


def take(session_id: object, tool_use_id: object) -> dict[str, Any] | None:
    """Read and remove the sidecar for one call, or None when there is none.

    Removal is unconditional once the file is opened: a sidecar that cannot be
    parsed is still consumed, so a malformed entry cannot outlive its session
    and cannot be replayed onto a later call that reuses the id.
    """
    session = _sanitize(session_id)
    tool_use = _sanitize(tool_use_id)
    if session is None or tool_use is None:
        return None

    target = _session_dir(session) / f"{tool_use}.json"
    try:
        fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, encoding="utf-8") as fh:
            raw = fh.read()
    except OSError:
        return None
    finally:
        with contextlib.suppress(OSError):
            os.unlink(target)

    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


__all__ = ["TTL_SECONDS", "store", "take"]
