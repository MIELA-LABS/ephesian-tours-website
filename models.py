"""Pydantic models for every content file in content/.

The build fails loudly if any YAML file does not match these models.

Provenance
----------
Any price, term, or fact that is not yet confirmed carries a status:

    confirmed  final; shown as-is
    pending    sample value awaiting an answer (resolves_by -> pending.yaml id)
    proposed   a whole offering that is still being confirmed (e.g. a new journey)

`Tracked[T]` wraps a value with that provenance. In YAML a plain value is
shorthand for a confirmed one:

    highlights:
      - Tarsus, Paul's birthplace                 # confirmed
      - value: Antioch, where believers were first called Christians
        status: pending
        resolves_by: Q-ANTAKYA-01
"""

from __future__ import annotations

import re
from datetime import date
from typing import Annotated, Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, field_validator, model_validator

T = TypeVar("T")

Status = Literal["confirmed", "pending", "proposed"]
SlugId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$")]
QuestionId = Annotated[str, StringConstraints(pattern=r"^(Q|ET)-[A-Z]+-\d{2}$")]

# Scripture references, e.g. "Rev 2–3", "Acts 13:13–14", "1 Pet 1:1". En dashes only.
SCRIPTURE_BOOKS = {"Acts", "Rev", "Eph", "Col", "John", "1 Pet"}
SCRIPTURE_RE = re.compile(r"^(?P<book>(?:[1-3] )?[A-Z][a-z]+) \d+(?:–\d+|:\d+(?:–\d+)?)?$")


class Strict(BaseModel):
    """Base model: unknown keys are errors, so typos in YAML never pass silently."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def _check_refs(refs: list[str]) -> list[str]:
    for ref in refs:
        m = SCRIPTURE_RE.match(ref)
        if not m or m["book"] not in SCRIPTURE_BOOKS:
            raise ValueError(
                f"bad scripture reference {ref!r}: use e.g. 'Acts 13:13–14' (en dash) "
                f"with a book from {sorted(SCRIPTURE_BOOKS)}"
            )
    return refs


# --- provenance ------------------------------------------------------------


class Provenance(Strict):
    status: Status = "confirmed"
    resolves_by: QuestionId | None = None

    @model_validator(mode="after")
    def _needs_question(self) -> Provenance:
        if self.status != "confirmed" and not self.resolves_by:
            raise ValueError(f"status '{self.status}' requires resolves_by (an id from pending.yaml)")
        return self

    @property
    def sample(self) -> bool:
        """True when the value is not final and should carry a "Sample" badge in preview mode."""
        return self.status != "confirmed"


class Tracked(Provenance, Generic[T]):
    value: T

    @model_validator(mode="before")
    @classmethod
    def _wrap_plain_value(cls, data: Any) -> Any:
        return data if isinstance(data, dict) else {"value": data}


class Price(Provenance):
    value: int = Field(gt=0)
    currency: Literal["USD"] = "USD"
    basis: str

    @property
    def display(self) -> str:
        return f"${self.value:,}"


class Link(Strict):
    label: str
    href: str


# --- site.yaml -------------------------------------------------------------


class SiteSettings(Strict):
    brand_name: str
    descriptor: str
    domain: str
    base_url: HttpUrl
    lang: str = "en-US"
    preview_mode: bool = True
    preview_banner: str
    brand_line: str
    brand_line_ref: str
    partner_line: str
    scripture_notice: str
    form_endpoint: Tracked[HttpUrl]
    seo_title: str
    seo_description: str = Field(max_length=170)
    og_image: str
    og_image_alt: str

    @field_validator("brand_line_ref")
    @classmethod
    def _ref(cls, v: str) -> str:
        return _check_refs([v])[0]


class Hero(Strict):
    tagline: str
    value_prop: str
    image: str
    cta_primary: Link
    cta_secondary: Link


class Verse(Strict):
    text: str
    ref: str
    image: str

    @field_validator("ref")
    @classmethod
    def check_ref(cls, v: str) -> str:
        return _check_refs([v])[0]


class SectionCopy(Strict):
    eyebrow: str
    heading: str
    intro: str | None = None


class Sections(Strict):
    why_turkey: SectionCopy
    tours: SectionCopy
    sites: SectionCopy
    how_it_works: SectionCopy
    partner: SectionCopy
    booking: SectionCopy
    faq: SectionCopy
    host: SectionCopy
    contact: SectionCopy


class WhyPoint(Strict):
    place: str
    title: str
    body: str
    refs: list[str]
    @field_validator("refs")
    @classmethod
    def check_refs(cls, v: list[str]) -> list[str]:
        return _check_refs(v)


class Step(Provenance):
    title: str
    body: str
    note: str | None = None  # explanatory note shown when the step is a sample


class HowItWorks(Strict):
    steps: list[Step] = Field(min_length=5, max_length=5)
    leader_note: Tracked[str]


class Partner(Strict):
    name: str
    location: str
    founded: int
    license_no: Tracked[str]
    license_body: str
    verify_url: HttpUrl
    summary: str
    facts: list[Tracked[str]]


class Host(Strict):
    name: str
    role: str
    bio: Tracked[str]
    photo: Tracked[str | None]  # image id once a real photo exists


class FormOptions(Strict):
    roles: list[str]
    group_sizes: list[str]
    seasons: list[str]


class Contact(Strict):
    email: Tracked[str]
    phone: Tracked[str]
    location: str
    info_packet: Tracked[str]  # CTA label; becomes a PDF link once published
    packet_text: str
    form_options: FormOptions
    form_fallback: str  # shown instead of submitting while the form endpoint is a sample
    form_success: str
    form_error: str


class SiteFile(Strict):
    site: SiteSettings
    hero: Hero
    verse: Verse
    nav: list[Link]
    sections: Sections
    why_turkey: list[WhyPoint] = Field(min_length=3, max_length=4)
    how_it_works: HowItWorks
    partner: Partner
    host: Host
    contact: Contact


# --- sites.yaml ------------------------------------------------------------


class Place(Strict):
    id: SlugId
    name: str
    modern_name: str | None = None
    kind: Literal["site", "stop"] = "site"  # stops are route waypoints only (hotels, airports)
    group: Literal["seven_churches", "paul", "more"] | None = None
    featured: bool = False  # shown in "The Sites" grid
    lat: float = Field(ge=35, le=43)  # Türkiye + Patmos bounding box
    lng: float = Field(ge=25, le=45)
    refs: list[str] = []
    history: str | None = None
    image: str | None = None
    note: Tracked[str] | None = None

    @field_validator("refs")
    @classmethod
    def check_refs(cls, v: list[str]) -> list[str]:
        return _check_refs(v)

    @model_validator(mode="after")
    def _featured_needs_history(self) -> Place:
        if self.featured and not self.history:
            raise ValueError(f"featured site '{self.id}' needs history text")
        if self.featured and self.kind != "site":
            raise ValueError(f"'{self.id}' is a stop and cannot be featured")
        return self


class SiteGroup(Strict):
    id: Literal["seven_churches", "paul", "more"]
    label: str
    intro: str | None = None


class SitesFile(Strict):
    groups: list[SiteGroup]
    sites: list[Place]


# --- journeys.yaml ---------------------------------------------------------


class RouteStop(Strict):
    site: str
    by: Literal["road", "air", "sea"] = "road"  # how the group arrives at this stop

    @model_validator(mode="before")
    @classmethod
    def _wrap_plain(cls, data: Any) -> Any:
        return data if isinstance(data, dict) else {"site": data}


class Day(Provenance):
    n: int = Field(ge=1)
    title: str
    body: str
    overnight: str | None = None
    refs: list[str] = []
    note: Tracked[str] | None = None

    @field_validator("refs")
    @classmethod
    def check_refs(cls, v: list[str]) -> list[str]:
        return _check_refs(v)


class Journey(Provenance):
    id: SlugId
    title: str
    subtitle: str
    tag: str | None = None
    duration_days: int = Field(ge=1)
    duration_nights: int | None = None
    from_price: Price
    image: str
    summary: str
    highlights: list[Tracked[str]] = Field(min_length=3, max_length=3)
    route: list[RouteStop] = Field(min_length=2)
    days: list[Day]
    included: Tracked[list[str]]
    excluded: Tracked[list[str]]
    notes: list[Tracked[str]] = []
    video: str | None = None

    @model_validator(mode="after")
    def _days_in_order(self) -> Journey:
        numbers = [d.n for d in self.days]
        if numbers != list(range(1, self.duration_days + 1)):
            raise ValueError(
                f"journey '{self.id}': days must be numbered 1..{self.duration_days}, got {numbers}"
            )
        return self


class Extension(Strict):
    title: str
    length: str
    body: str


class Extensions(Provenance):
    heading: str
    intro: str
    items: list[Extension]


class JourneysFile(Strict):
    journeys: list[Journey]
    extensions: Extensions


# --- faq.yaml --------------------------------------------------------------


class FaqItem(Provenance):
    id: SlugId
    question: str
    answer: str  # paragraphs separated by blank lines; [text](url) and **bold** allowed


class FaqFile(Strict):
    faq: list[FaqItem]


# --- booking.yaml ----------------------------------------------------------


class Milestone(Strict):
    id: SlugId
    label: str
    when: Tracked[str]
    amount: Tracked[str] | None = None
    body: str | None = None


class Booking(Strict):
    milestones: list[Milestone]
    payment_methods: Tracked[list[str]]
    minimum_group: Tracked[str]
    cancellation: Tracked[str]
    insurance_note: Tracked[str]


class BookingFile(Strict):
    booking: Booking


# --- media.yaml ------------------------------------------------------------


class Image(Strict):
    id: SlugId
    subject: str
    alt: str
    file: str | None = None  # basename in assets/img/ without width suffix; None = not sourced yet
    widths: list[int] = [480, 960, 1600]
    width: int | None = None  # intrinsic size of the largest rendition (set by fetch_images.py)
    height: int | None = None
    position: str = "center"  # CSS object-position for cropping
    source_url: HttpUrl | None = None
    author: str | None = None
    license: str | None = None
    license_url: HttpUrl | None = None

    @model_validator(mode="after")
    def _sourced_needs_credit(self) -> Image:
        if self.file and not (self.source_url and self.author and self.license):
            raise ValueError(f"image '{self.id}' has a file but no source_url/author/license")
        return self

    @property
    def ready(self) -> bool:
        return self.file is not None


class Video(Provenance):
    id: SlugId
    provider: Literal["vimeo"] = "vimeo"
    video_id: str = Field(pattern=r"^\d+$")
    title: str
    duration_seconds: int
    poster: str  # image id; our own licensed photo, so nothing loads from Vimeo before a click
    author: str
    source_url: HttpUrl
    credit: str
    license: str


class MediaFile(Strict):
    images: list[Image]
    videos: list[Video] = []


# --- pending.yaml ----------------------------------------------------------


class PendingItem(Strict):
    id: QuestionId
    owner: Literal["operator", "ephesian"]  # who provides the answer
    topic: str
    question: str
    asked_on: date | None = None
    answer: str | None = None
    answered_on: date | None = None
    updates: list[str] = Field(min_length=1)  # content paths, e.g. journeys.*.from_price

    @property
    def resolved(self) -> bool:
        return self.answer is not None


class PendingFile(Strict):
    pending: list[PendingItem]


# file stem -> model, in load order
CONTENT_FILES: dict[str, type[Strict]] = {
    "site": SiteFile,
    "sites": SitesFile,
    "journeys": JourneysFile,
    "faq": FaqFile,
    "booking": BookingFile,
    "media": MediaFile,
    "pending": PendingFile,
}
