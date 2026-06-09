"""Direct tests for Pydantic models (validation + helpers)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from rmacd.models import (
    AutonomyLevel,
    DataAccess,
    DataClassification,
    Operation,
    Profile2D,
    Profile3D,
    TierPolicy,
)


class TestProfileIdPatterns:
    def test_2d_id_pattern_enforced(self) -> None:
        with pytest.raises(ValidationError):
            Profile2D(
                profile_id="bad-id",
                profile_name="X",
                model="two-dimensional",
                version="1.0",
                permissions=[Operation.READ],
            )

    def test_3d_id_pattern_enforced(self) -> None:
        with pytest.raises(ValidationError):
            Profile3D(
                profile_id="rmacd-2d-wrong-prefix",
                profile_name="X",
                model="three-dimensional",
                version="1.0",
                permissions={DataClassification.PUBLIC: [Operation.READ]},
            )

    def test_valid_ids_accepted(self) -> None:
        p = Profile2D(
            profile_id="rmacd-2d-ok",
            profile_name="X",
            model="two-dimensional",
            version="1.0",
            permissions=[Operation.READ],
        )
        assert p.profile_id == "rmacd-2d-ok"


class TestDataAccess:
    def _data_access(self) -> DataAccess:
        return DataAccess(
            public=TierPolicy(allowed=True, autonomy=AutonomyLevel.AUTONOMOUS),
            internal=TierPolicy(allowed=True, autonomy=AutonomyLevel.LOGGED),
            confidential=TierPolicy(allowed=True, autonomy=AutonomyLevel.APPROVAL),
            restricted=TierPolicy(allowed=False, autonomy=AutonomyLevel.PROHIBITED),
        )

    @pytest.mark.parametrize(
        "tier,allowed",
        [
            (DataClassification.PUBLIC, True),
            (DataClassification.INTERNAL, True),
            (DataClassification.CONFIDENTIAL, True),
            (DataClassification.RESTRICTED, False),
        ],
    )
    def test_for_tier_returns_right_policy(
        self, tier: DataClassification, allowed: bool
    ) -> None:
        assert self._data_access().for_tier(tier).allowed is allowed

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            DataAccess(
                public=TierPolicy(allowed=True, autonomy=AutonomyLevel.AUTONOMOUS),
                internal=TierPolicy(allowed=True, autonomy=AutonomyLevel.LOGGED),
                confidential=TierPolicy(allowed=True, autonomy=AutonomyLevel.APPROVAL),
                restricted=TierPolicy(allowed=False, autonomy=AutonomyLevel.PROHIBITED),
                top_secret=TierPolicy(allowed=False, autonomy=AutonomyLevel.PROHIBITED),
            )
