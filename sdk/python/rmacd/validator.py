"""JSON Schema validator for RMACD Framework profiles."""

import json
from importlib import resources
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator, ValidationError


class SchemaValidationError(Exception):
    """Raised when schema validation fails."""

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or []


class ProfileValidator:
    """Validates RMACD profiles against JSON schemas."""

    # Default schema paths relative to the package
    SCHEMA_2D_PATH = "profile-2d.schema.json"
    SCHEMA_3D_PATH = "profile-3d.schema.json"
    SCHEMA_DC2D_PATH = "profile-dc2d.schema.json"

    def __init__(self, schema_dir: str | Path | None = None):
        """Initialize the validator.

        Args:
            schema_dir: Directory containing schema files. If None, the
                       schemas bundled with the package are used.
        """
        self._schema_dir = Path(schema_dir) if schema_dir else None
        self._schema_2d: dict | None = None
        self._schema_3d: dict | None = None
        self._schema_dc2d: dict | None = None
        self._validator_2d: Draft202012Validator | None = None
        self._validator_3d: Draft202012Validator | None = None
        self._validator_dc2d: Draft202012Validator | None = None

    def _load_schema(self, schema_path: str) -> dict:
        """Load a JSON schema, from schema_dir if given, else from the bundled copies."""
        if self._schema_dir is not None:
            if not self._schema_dir.exists():
                raise SchemaValidationError(f"Schema directory not found: {self._schema_dir}")
            full_path = self._schema_dir / schema_path
            if not full_path.exists():
                raise SchemaValidationError(f"Schema file not found: {full_path}")
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                raise SchemaValidationError(f"Invalid JSON in schema file: {e}") from e

        resource = resources.files("rmacd") / "schemas" / schema_path
        try:
            return json.loads(resource.read_text(encoding="utf-8"))
        except FileNotFoundError as e:
            raise SchemaValidationError(f"Bundled schema not found: {schema_path}") from e
        except json.JSONDecodeError as e:
            raise SchemaValidationError(f"Invalid JSON in bundled schema: {e}") from e

    def _get_validator_2d(self) -> Draft202012Validator:
        """Get or create the 2D schema validator."""
        if self._validator_2d is None:
            self._schema_2d = self._load_schema(self.SCHEMA_2D_PATH)
            self._validator_2d = Draft202012Validator(self._schema_2d)
        return self._validator_2d

    def _get_validator_3d(self) -> Draft202012Validator:
        """Get or create the 3D schema validator."""
        if self._validator_3d is None:
            self._schema_3d = self._load_schema(self.SCHEMA_3D_PATH)
            self._validator_3d = Draft202012Validator(self._schema_3d)
        return self._validator_3d

    def _get_validator_dc2d(self) -> Draft202012Validator:
        """Get or create the DC2D schema validator."""
        if self._validator_dc2d is None:
            self._schema_dc2d = self._load_schema(self.SCHEMA_DC2D_PATH)
            self._validator_dc2d = Draft202012Validator(self._schema_dc2d)
        return self._validator_dc2d

    def validate(self, profile_data: dict | str | Path, model_type: str | None = None) -> bool:
        """Validate a profile against its schema.

        Args:
            profile_data: Profile as dict, JSON string, or path to file
            model_type: Optional model type override ("two-dimensional" or "three-dimensional")

        Returns:
            True if validation passes

        Raises:
            SchemaValidationError: If validation fails
        """
        # Load profile data
        if isinstance(profile_data, (str, Path)):
            path = Path(profile_data)
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                # Assume it's a JSON string
                data = json.loads(str(profile_data))
        else:
            data = profile_data

        # Determine model type
        if model_type is None:
            model_type = data.get("model")

        if model_type == "three-dimensional":
            validator = self._get_validator_3d()
        elif model_type == "two-dimensional":
            validator = self._get_validator_2d()
        elif model_type == "data-classification-2d":
            validator = self._get_validator_dc2d()
        else:
            raise SchemaValidationError(f"Unknown or missing model type: {model_type}")

        # Validate
        errors = list(validator.iter_errors(data))
        if errors:
            error_messages = [self._format_error(e) for e in errors]
            raise SchemaValidationError(
                f"Schema validation failed with {len(errors)} error(s)",
                errors=error_messages,
            )

        return True

    def validate_file(self, path: str | Path) -> bool:
        """Validate a profile file against its schema.

        Args:
            path: Path to the profile JSON file

        Returns:
            True if validation passes

        Raises:
            SchemaValidationError: If validation fails
        """
        return self.validate(Path(path))

    def get_errors(self, profile_data: dict | str | Path) -> list[str]:
        """Get validation errors without raising an exception.

        Args:
            profile_data: Profile as dict, JSON string, or path to file

        Returns:
            List of error messages (empty if valid)
        """
        try:
            self.validate(profile_data)
            return []
        except SchemaValidationError as e:
            return e.errors

    def is_valid(self, profile_data: dict | str | Path) -> bool:
        """Check if a profile is valid without raising exceptions.

        Args:
            profile_data: Profile as dict, JSON string, or path to file

        Returns:
            True if valid, False otherwise
        """
        try:
            self.validate(profile_data)
            return True
        except (SchemaValidationError, json.JSONDecodeError, OSError):
            return False

    def _format_error(self, error: ValidationError) -> str:
        """Format a validation error for display."""
        path = ".".join(str(p) for p in error.absolute_path) if error.absolute_path else "<root>"
        return f"{path}: {error.message}"

    def get_schema(self, model_type: str) -> dict:
        """Get the raw JSON schema for a model type.

        Args:
            model_type: "two-dimensional", "three-dimensional", or "data-classification-2d"

        Returns:
            The JSON schema as a dictionary
        """
        if model_type == "three-dimensional":
            if self._schema_3d is None:
                self._schema_3d = self._load_schema(self.SCHEMA_3D_PATH)
            return self._schema_3d
        elif model_type == "two-dimensional":
            if self._schema_2d is None:
                self._schema_2d = self._load_schema(self.SCHEMA_2D_PATH)
            return self._schema_2d
        elif model_type == "data-classification-2d":
            if self._schema_dc2d is None:
                self._schema_dc2d = self._load_schema(self.SCHEMA_DC2D_PATH)
            return self._schema_dc2d
        else:
            raise SchemaValidationError(f"Unknown model type: {model_type}")
