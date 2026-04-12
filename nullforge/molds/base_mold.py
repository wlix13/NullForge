from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict


REDACTED_VALUE = "***"


class BaseMold(BaseModel):
    """Base model class with JSON serialization support for pyinfra."""

    model_config = ConfigDict(extra="forbid")

    _sensitive_fields: ClassVar[tuple[str, ...]] = ()
    """Field names whose values are redacted by `to_json`."""

    @property
    def is_active(self) -> bool:
        raise NotImplementedError(
            f"{type(self).__name__}.is_active must be implemented as @property that "
            "returns True when rune for this mold should be deployed."
        )

    def to_json(self) -> dict[str, Any]:
        """JSON-serializable representation for pyinfra's debug-inventory.

        Uses JSON mode so that complex internal types (e.g. IPvAnyAddress, UUID, enums)
        are serialized to simple primitives (str etc) while keeping rich types inside the model.
        """

        data = self.model_dump(mode="json")
        return self._redact(self, data)

    @classmethod
    def _redact(cls, model: BaseModel, data: dict[str, Any]) -> dict[str, Any]:
        """Redact model's sensitive fields and recurse into nested molds."""

        sensitive = getattr(type(model), "_sensitive_fields", ())
        for key in sensitive:
            if data.get(key):
                data[key] = REDACTED_VALUE

        for name in type(model).model_fields:
            value = getattr(model, name)
            if name in data:
                data[name] = cls._redact_value(value, data[name])
        return data

    @classmethod
    def _redact_value(cls, value: Any, dumped: Any) -> Any:
        """Mirror dumped value against live counterpart, redacting nested molds."""

        if isinstance(value, BaseMold) and isinstance(dumped, dict):
            return cls._redact(value, dumped)
        if isinstance(value, (list, tuple)) and isinstance(dumped, list):
            return [cls._redact_value(v, d) for v, d in zip(value, dumped)]
        if isinstance(value, dict) and isinstance(dumped, dict):
            return {k: cls._redact_value(value[k], d) for k, d in dumped.items() if k in value}
        return dumped
