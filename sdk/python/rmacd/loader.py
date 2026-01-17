"""Profile loader for RMACD Framework profiles."""

import json
from pathlib import Path
from typing import Union

from rmacd.models import Profile2D, Profile3D


class ProfileLoadError(Exception):
    """Raised when a profile cannot be loaded."""

    pass


class ProfileLoader:
    """Loads RMACD profiles from files or dictionaries."""

    def load_file(self, path: str | Path) -> Union[Profile2D, Profile3D]:
        """Load a profile from a JSON file.

        Args:
            path: Path to the JSON profile file

        Returns:
            Profile2D or Profile3D depending on the model type

        Raises:
            ProfileLoadError: If the file cannot be loaded or parsed
        """
        path = Path(path)

        if not path.exists():
            raise ProfileLoadError(f"Profile file not found: {path}")

        if not path.suffix.lower() == ".json":
            raise ProfileLoadError(f"Profile must be a JSON file: {path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ProfileLoadError(f"Invalid JSON in profile file: {e}") from e
        except OSError as e:
            raise ProfileLoadError(f"Error reading profile file: {e}") from e

        return self.load_dict(data, source=str(path))

    def load_dict(
        self, data: dict, source: str = "<dict>"
    ) -> Union[Profile2D, Profile3D]:
        """Load a profile from a dictionary.

        Args:
            data: Profile data as a dictionary
            source: Source identifier for error messages

        Returns:
            Profile2D or Profile3D depending on the model type

        Raises:
            ProfileLoadError: If the data cannot be parsed as a valid profile
        """
        if not isinstance(data, dict):
            raise ProfileLoadError(f"Profile must be a dictionary, got {type(data).__name__}")

        model_type = data.get("model")

        if model_type == "three-dimensional":
            return self._load_3d(data, source)
        elif model_type == "two-dimensional":
            return self._load_2d(data, source)
        elif model_type is None:
            raise ProfileLoadError(f"Profile missing 'model' field: {source}")
        else:
            raise ProfileLoadError(f"Unknown model type '{model_type}': {source}")

    def load_json(self, json_string: str, source: str = "<json>") -> Union[Profile2D, Profile3D]:
        """Load a profile from a JSON string.

        Args:
            json_string: Profile data as a JSON string
            source: Source identifier for error messages

        Returns:
            Profile2D or Profile3D depending on the model type

        Raises:
            ProfileLoadError: If the JSON cannot be parsed
        """
        try:
            data = json.loads(json_string)
        except json.JSONDecodeError as e:
            raise ProfileLoadError(f"Invalid JSON: {e}") from e

        return self.load_dict(data, source)

    def _load_3d(self, data: dict, source: str) -> Profile3D:
        """Load a 3D profile."""
        try:
            # Convert permission keys from strings to DataClassification if needed
            if "permissions" in data and isinstance(data["permissions"], dict):
                # Keep as-is, Pydantic will handle conversion
                pass

            return Profile3D.model_validate(data)
        except Exception as e:
            raise ProfileLoadError(f"Invalid 3D profile ({source}): {e}") from e

    def _load_2d(self, data: dict, source: str) -> Profile2D:
        """Load a 2D profile."""
        try:
            return Profile2D.model_validate(data)
        except Exception as e:
            raise ProfileLoadError(f"Invalid 2D profile ({source}): {e}") from e

    def detect_model_type(self, path: str | Path) -> str:
        """Detect the model type of a profile without fully loading it.

        Args:
            path: Path to the JSON profile file

        Returns:
            "two-dimensional" or "three-dimensional"

        Raises:
            ProfileLoadError: If the model type cannot be determined
        """
        path = Path(path)

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            raise ProfileLoadError(f"Cannot read profile: {e}") from e

        model_type = data.get("model")
        if model_type not in ("two-dimensional", "three-dimensional"):
            raise ProfileLoadError(f"Unknown or missing model type: {model_type}")

        return model_type
