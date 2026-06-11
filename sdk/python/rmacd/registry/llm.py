"""
RMACD Tools Registry - LLM Classifier
======================================

Classify a tool definition into RMACD terms with a Claude model.

The keyword heuristic in ``rmacd.registry.mcp`` is deterministic and free, but
it only sees surface strings: it cannot tell that ``archive_user`` removes an
account (Delete-adjacent) or that ``run_query`` with a ``sql`` argument can
mutate anything. This module asks a Claude model to read the *whole* tool
definition — name, description, input schema, declared operations — and return
a structured RMACD classification with a rationale and a confidence score.

It is an **optional** dependency surface: ``pip install rmacd-framework[llm]``
(or just ``pip install anthropic``). Importing this module is safe without the
SDK installed; only constructing a client requires it. Plug an instance into
``MCPRegistryBridge(llm_classifier=...)`` to upgrade MCP auto-classification,
or call ``classify()`` directly for any tool.

The classification an LLM produces is advisory input to governance, not the
governance itself: the §12.5 safety floor, the agent profile, and the tool
capability ceiling are still enforced deterministically by the evaluator.

Author: Kash Kashyap
License: CC BY 4.0
"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

#: Default classification model. Fable is Anthropic's most capable tier —
#: classification runs once per tool at registration time, so the per-call cost
#: is negligible next to the cost of a misclassified Delete.
DEFAULT_MODEL = "claude-fable-5"


class ToolClassification(BaseModel):
    """Structured output schema the model must return."""

    rmacd_level: Literal["R", "M", "A", "C", "D"] = Field(
        description="Worst-case RMACD operation the tool can perform: "
        "R=Read, M=Move, A=Add, C=Change, D=Delete."
    )
    data_access: Literal["public", "internal", "confidential", "restricted"] = Field(
        description="Most sensitive data classification the tool plausibly touches."
    )
    required_hitl: Literal[
        "autonomous", "logged", "notification", "approval", "elevated_approval", "prohibited"
    ] = Field(description="Minimum human-in-the-loop control this tool warrants.")
    rationale: str = Field(description="One or two sentences justifying the classification.")
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="0.0-1.0 confidence; below 0.7 flags the tool for human review.",
    )


_SYSTEM_PROMPT = """\
You classify software tools for the RMACD governance framework, which gates what \
autonomous AI agents may do. For each tool definition you receive, determine:

1. rmacd_level — the WORST-CASE operation the tool can perform:
   - R (Read): observe, query, search, analyze. No state change anywhere.
   - M (Move): relocate or transfer existing data without altering content.
   - A (Add): create new resources without touching existing ones.
   - C (Change): modify existing state (files, configs, records, processes).
   - D (Delete): remove or destroy data or resources.
   Judge by capability, not by typical use: a tool that executes arbitrary SQL,
   shell commands, or code must be classified by the most destructive thing
   that input could do (usually C or D), regardless of its friendly name.

2. data_access — the most sensitive tier the tool plausibly touches:
   public < internal < confidential < restricted. Anything handling
   credentials, secrets, keys, tokens, PII, health, or payment data is
   restricted. Default to internal when nothing indicates otherwise.

3. required_hitl — the minimum oversight warranted, consistent with the
   risk: Read-only tools are typically "logged"; Move "notification";
   Add/Change "approval"; Delete "elevated_approval". Escalate (never relax)
   when the tool is irreversible, touches restricted data, or reaches
   external systems.

Be conservative: when the definition is ambiguous, classify at the HIGHER
risk level and lower your confidence score. Set confidence below 0.7 whenever
you are guessing from a vague name alone."""


class LLMToolClassifier:
    """Claude-backed tool classifier.

    Usage::

        from rmacd.registry import MCPRegistryBridge
        from rmacd.registry.llm import LLMToolClassifier

        bridge = MCPRegistryBridge(
            registry=registry,
            llm_classifier=LLMToolClassifier(),  # reads ANTHROPIC_API_KEY
            llm_mode="fallback",                 # LLM only when keywords are unsure
        )

    ``client`` may be injected (tests, custom base URL); otherwise an
    ``anthropic.Anthropic()`` client is created lazily on first use, resolving
    credentials from the environment.
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        *,
        client: Any | None = None,
        max_tokens: int = 1024,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover - environment dependent
                raise ImportError(
                    "LLMToolClassifier requires the 'anthropic' package. "
                    "Install it with: pip install rmacd-framework[llm]"
                ) from exc
            self._client = anthropic.Anthropic()
        return self._client

    def classify(
        self,
        *,
        name: str,
        description: str = "",
        input_schema: dict[str, Any] | None = None,
        operations: list[str] | None = None,
    ) -> ToolClassification:
        """Classify one tool definition. Raises on API/credential failure —
        callers that want graceful degradation (e.g. ``MCPRegistryBridge``)
        catch and fall back to the keyword heuristic."""
        tool_doc = {
            "name": name,
            "description": description,
            "input_schema": input_schema or {},
            "declared_operations": operations or [],
        }
        response = self._get_client().messages.parse(
            model=self.model,
            max_tokens=self.max_tokens,
            system=_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": "Classify this tool definition:\n\n"
                    + json.dumps(tool_doc, indent=2, sort_keys=True),
                }
            ],
            output_format=ToolClassification,
        )
        result: ToolClassification = response.parsed_output
        logger.debug(
            "LLM classified '%s' as %s/%s/%s (confidence %.2f)",
            name, result.rmacd_level, result.data_access,
            result.required_hitl, result.confidence,
        )
        return result


__all__ = ["DEFAULT_MODEL", "LLMToolClassifier", "ToolClassification"]
