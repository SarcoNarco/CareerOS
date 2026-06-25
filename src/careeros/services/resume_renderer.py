from __future__ import annotations

from html import escape
from typing import Any

from jinja2 import Environment, select_autoescape


DEFAULT_TEMPLATE_NAME = "default_html_v1"
DEFAULT_TEMPLATE_PATH = "builtin://default_html_v1"

DEFAULT_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{{ profile_name }} - Tailored Resume</title>
  <style>
    body { font-family: Arial, sans-serif; color: #111827; margin: 32px; line-height: 1.45; }
    header { border-bottom: 2px solid #111827; margin-bottom: 20px; padding-bottom: 12px; }
    h1 { font-size: 28px; margin: 0 0 4px; }
    h2 { font-size: 16px; margin: 22px 0 8px; text-transform: uppercase; letter-spacing: 0.08em; }
    .target { color: #374151; font-size: 13px; }
    ul { margin: 0; padding-left: 20px; }
    li { margin-bottom: 6px; }
    .trace { color: #6b7280; font-size: 11px; margin-top: 24px; }
  </style>
</head>
<body>
  <header>
    <h1>{{ profile_name }}</h1>
    {% if headline %}<div>{{ headline }}</div>{% endif %}
    {% if target_label %}<div class="target">Target: {{ target_label }}</div>{% endif %}
  </header>
  {% for section in sections %}
  <section>
    <h2>{{ section.name }}</h2>
    <ul>
      {% for item in section.claims %}
      <li>{{ item.rendered_text }}</li>
      {% endfor %}
    </ul>
  </section>
  {% endfor %}
  <div class="trace">Generated deterministically from approved CareerOS claims only.</div>
</body>
</html>
"""


def render_resume_html(context: dict[str, Any]) -> str:
    environment = Environment(autoescape=select_autoescape(default=True))
    template = environment.from_string(DEFAULT_HTML_TEMPLATE)
    return template.render(**context)


def render_plain_fallback(context: dict[str, Any]) -> str:
    lines = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        f"<title>{escape(context['profile_name'])} - Tailored Resume</title>",
        "</head><body>",
        f"<h1>{escape(context['profile_name'])}</h1>",
    ]
    if context.get("headline"):
        lines.append(f"<p>{escape(context['headline'])}</p>")
    for section in context["sections"]:
        lines.append(f"<h2>{escape(section['name'])}</h2><ul>")
        for item in section["claims"]:
            lines.append(f"<li>{escape(item['rendered_text'])}</li>")
        lines.append("</ul>")
    lines.append("<p>Generated deterministically from approved CareerOS claims only.</p>")
    lines.append("</body></html>")
    return "\n".join(lines)
