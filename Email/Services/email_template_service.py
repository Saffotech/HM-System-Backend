"""Jinja2 HTML emails. Document lists are loops, never hardcoded counts."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

_TEMPLATES = Path(__file__).resolve().parents[1] / "Templates"
_ENV = Environment(
    loader=FileSystemLoader(str(_TEMPLATES)),
    autoescape=select_autoescape(["html"]),
    undefined=StrictUndefined,
)


def render(template_name: str, context: dict) -> str:
    template = _ENV.get_template(template_name)
    return template.render(**context)
