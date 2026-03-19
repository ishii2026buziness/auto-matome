"""Generate text-only link cards for source articles (no image embedding)."""
from __future__ import annotations
from urllib.parse import urlparse


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return url


def make_link_card(title: str, url: str, description: str = "", source_label: str = "") -> str:
    """Generate a text-only link card in Markdown.

    Format:
        > **[Title](URL)**
        > source_label | description
        > URL
    """
    label = source_label or _domain(url)
    lines = [f"> **[{title}]({url})**"]
    if description:
        lines.append(f"> {label} | {description[:120]}")
    else:
        lines.append(f"> {label} | {_domain(url)}")
    return "\n".join(lines)
