"""Pydantic models for every content file in content/.

The build fails loudly if any YAML file does not match these models.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, HttpUrl


class Strict(BaseModel):
    """Base model: unknown keys are errors, so typos in YAML never pass silently."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Site(Strict):
    brand_name: str
    descriptor: str
    domain: str
    base_url: HttpUrl
    lang: str = "en-US"
    preview_mode: bool = True
