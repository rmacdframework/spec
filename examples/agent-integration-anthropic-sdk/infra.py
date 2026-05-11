"""Mock infrastructure the demo agent operates on.

In-memory only. The point is to give each tool something concrete to read and
mutate so the RMACD enforcement layer has a realistic target string to log and
classify. None of this would exist in a real integration — replace with the
caller's actual platform APIs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class Server:
    """One mock host. ``classification`` drives RMACD tier lookup."""

    server_id: str
    role: str
    environment: str
    classification: str  # "public" | "internal" | "confidential" | "restricted"
    config: dict[str, Any] = field(default_factory=dict)
    decommissioned: bool = False


@dataclass
class AuditEntry:
    """In-memory audit ledger entry — separate from the RMACD audit log."""

    when: datetime
    actor: str
    action: str
    target: str
    detail: str


class MockInfra:
    """In-memory fleet plus an op-log so the demo can show before/after state."""

    def __init__(self) -> None:
        self.servers: dict[str, Server] = {
            "web-stage-01": Server(
                server_id="web-stage-01",
                role="web",
                environment="staging",
                classification="internal",
                config={"workers": 4, "timeout_s": 30},
            ),
            "web-stage-02": Server(
                server_id="web-stage-02",
                role="web",
                environment="staging",
                classification="internal",
                config={"workers": 4, "timeout_s": 30},
            ),
            "db-prod-01": Server(
                server_id="db-prod-01",
                role="database",
                environment="production",
                classification="confidential",
                config={"max_connections": 200, "backup_schedule": "hourly"},
            ),
            "vault-prod-01": Server(
                server_id="vault-prod-01",
                role="secrets-vault",
                environment="production",
                classification="restricted",
                config={"seal_status": "unsealed"},
            ),
        }
        self.audit_ledger: list[AuditEntry] = []

    def get(self, server_id: str) -> Server | None:
        return self.servers.get(server_id)

    def list_servers(self) -> list[Server]:
        return [s for s in self.servers.values() if not s.decommissioned]

    def record(self, actor: str, action: str, target: str, detail: str = "") -> None:
        self.audit_ledger.append(
            AuditEntry(
                when=datetime.now(timezone.utc),
                actor=actor,
                action=action,
                target=target,
                detail=detail,
            )
        )


# Module-level singleton for the demo. Real integrations should inject an
# instance rather than rely on a global, but this keeps the tool functions
# small and focused on illustrating the RMACD wiring.
infra = MockInfra()
