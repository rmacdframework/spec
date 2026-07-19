"""Dispatching entry point: ``python3 -m rmacd.claude_code [hook|status]``.

The submodules are also directly invocable (``python3 -m rmacd.claude_code.hook``
and ``python3 -m rmacd.claude_code.status``); this dispatcher exists so the
package name alone is a valid entry point too.
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    command = args[0] if args else "hook"
    if command == "hook":
        from rmacd.claude_code import hook

        return hook.main()
    if command == "status":
        from rmacd.claude_code import status

        return status.main()
    print(
        f"unknown command '{command}' — usage: python3 -m rmacd.claude_code [hook|status]",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
