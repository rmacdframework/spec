"""The likelihood weight table (spec §5.4).

Every weight is a non-negative number of escalation steps; a negative weight
is refused at load (N-18, N-19). The table carries a version that is stamped
into every decision record, and any precedent age bound lives here and
nowhere else (N-61).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WeightTable(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = "default-1.0.0"
    unprecedented: int = Field(default=1, ge=0)
    reversibility: int = Field(default=1, ge=0)
    environment: int = Field(default=1, ge=0)
    budget_standing: int = Field(default=2, ge=0)
    blast_radius_over_cap: int = Field(default=2, ge=0)
    blast_radius_near_cap: int = Field(default=1, ge=0)
    near_cap_fraction: float = Field(default=0.8, ge=0, le=1)
    #: Precedent expires after this many days, or never when None (N-61).
    precedent_max_age_days: int | None = Field(default=None, ge=1)


DEFAULT_WEIGHTS = WeightTable()
