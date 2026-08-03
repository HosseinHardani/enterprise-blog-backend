"""
Slug generation helpers. Uses python-slugify for robust unicode handling.
"""

import uuid

from slugify import slugify as _slugify


def generate_slug(text: str) -> str:
    return _slugify(text)


def generate_unique_slug(text: str) -> str:
    """Appends a short random suffix -- used when uniqueness can't be
    guaranteed purely from the source text (e.g. two posts titled the same)."""
    base = _slugify(text)
    suffix = uuid.uuid4().hex[:8]
    return f"{base}-{suffix}"
