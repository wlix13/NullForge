"""NullForge templates package."""

from pathlib import Path
from typing import Any

from pyinfra.api.util import get_template


BLOCK_TRIM_ENV: dict[str, Any] = {"trim_blocks": True, "lstrip_blocks": True}
"""Jinja options for line-oriented templates."""


def get_template_path(template_name: str) -> str:
    """Get the full path to a template file."""

    templates_dir = Path(__file__).parent
    template_path = templates_dir / template_name

    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_name}")

    return str(template_path)


def render_template(
    template_name: str,
    jinja_env_kwargs: dict[str, Any] | None = None,
    **data: Any,
) -> str:
    """Render a template on the control node, for operations that take content instead of a source file."""

    return get_template(get_template_path(template_name), jinja_env_kwargs).render(data)
