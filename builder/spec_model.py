"""Strict typed model of the spec (builder/spec_doc.md), checked at build time with Pydantic.

extract.validate() checks the spec against the tool API (fields, enums, required fields) and the line rules.
This model checks what the engine silently assumes: types, ranges, time and date formats, and rules across
fields (bands without gaps or overlaps, a callback window that starts before it ends). Errors are worded for the
repair round. The engine itself never imports this (the code node only has json/re/datetime).
"""
import datetime
import re
from typing import Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"


class Loose(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)


class Calendar(Loose):
    workdays: List[int] = Field(min_length=1, max_length=7)
    holidays: List[str] = []

    @field_validator("workdays")
    @classmethod
    def _days(cls, v):
        if any(d < 0 or d > 6 for d in v) or len(set(v)) != len(v):
            raise ValueError("workdays must be distinct Python weekday numbers 0 (Monday) to 6 (Sunday)")
        return v

    @field_validator("holidays")
    @classmethod
    def _iso(cls, v):
        for h in v:
            try:
                datetime.date.fromisoformat(h)
            except ValueError:
                raise ValueError(f"holiday '{h}' is not a YYYY-MM-DD date")
        return v


class Callback(Loose):
    days: List[str] = Field(min_length=1)
    start: str = Field(pattern=HHMM)
    end: str = Field(pattern=HHMM)
    after_now: bool = True
    business_days_only: bool = False
    max_asks: int = Field(default=2, ge=1)

    @model_validator(mode="after")
    def _window(self):
        if self.start >= self.end:
            raise ValueError(f"callback window start {self.start} must be before end {self.end}")
        return self


class Question(Loose):
    field: str = Field(min_length=1)
    kind: Literal["date", "digits", "year", "upper", "text", "email"]
    length: Optional[int] = Field(default=None, ge=1, le=40)
    format: Optional[str] = None
    ask: str = Field(min_length=1)


class Identity(Loose):
    questions: List[Question] = Field(min_length=1)
    max_wrong: Optional[int] = Field(default=None, ge=1)
    max_wrong_per_question: Optional[int] = Field(default=None, ge=1)
    date_order: Literal["dmy", "mdy"] = "dmy"
    hints: Dict[str, str] = {}
    response: Dict[str, Union[str, List[str]]] = {}


class Products(Loose):
    names: Dict[str, str] = Field(min_length=1)
    amount_field: str = Field(default="past_due", min_length=1)
    days_field: str = Field(default="days_late", min_length=1)
    floor_field: Dict[str, str] = {}
    floor_pct: Optional[Union[int, float]] = Field(default=None, ge=0, le=100)
    floor_names: Dict[str, str] = {}
    amount_scale: Union[int, float] = Field(default=1, gt=0)


class Deadline(Loose):
    kind: str
    n: Optional[int] = Field(default=None, ge=0, le=366)
    value: Optional[str] = None


class Step(Loose):
    amount: str = Field(pattern=r"^(full|floor|full_or_floor|pct:\d+(\.\d+)?)$")
    date: str = "deadline"


class Band(Loose):
    name: str = ""
    min: int = Field(ge=0)
    max: int = Field(ge=0)
    deadline: Deadline
    attempts: int = Field(ge=1, le=10)
    ladder: Optional[List[Step]] = None

    @model_validator(mode="after")
    def _bounds(self):
        if self.min > self.max:
            raise ValueError(f"band {self.name}: min {self.min} is above max {self.max}")
        return self


class Event(Loose):
    outcome: str = Field(min_length=1)
    reason: Optional[str] = ""
    queue: Optional[str] = None
    note: Optional[str] = None


class Spec(Loose):
    currency_word: str = Field(min_length=1)
    calendar: Calendar
    callback: Callback
    confirm: Dict[str, int]
    identity: Identity
    products: Products
    bands: List[Band] = Field(min_length=1)
    ladder: List[Step] = Field(min_length=1)
    events: Dict[str, Event]
    tool_bodies: Dict[str, Dict[str, str]]
    lines: Dict[str, str]
    max_not_talk: int = Field(default=2, ge=1)

    @field_validator("confirm")
    @classmethod
    def _confirm(cls, v):
        if v.get("max_asks", 0) < 1:
            raise ValueError("confirm.max_asks must be an integer of at least 1")
        return v

    @model_validator(mode="after")
    def _bands(self):
        bs = sorted(self.bands, key=lambda b: b.min)
        for a, b in zip(bs, bs[1:]):
            if b.min <= a.max:
                raise ValueError(f"bands {a.name} ({a.min}-{a.max}) and {b.name} ({b.min}-{b.max}) overlap")
            if b.min > a.max + 1:
                raise ValueError(f"days_late {a.max + 1}-{b.min - 1} fall in no band (between {a.name} and {b.name})")
        most = max(b.attempts for b in self.bands if not b.ladder)if any(not b.ladder for b in self.bands) else 0
        if most > len(self.ladder):
            raise ValueError(f"a band allows {most} persuasion attempts but the ladder has only {len(self.ladder)} step(s)")
        return self


def check(spec):
    """List of readable problems (empty when the spec fits the model)."""
    try:
        Spec.model_validate(spec)
        return []
    except ValidationError as e:
        out = []
        for err in e.errors():
            where = ".".join(str(x) for x in err["loc"]) or "spec"
            msg = re.sub(r"^Value error, ", "", err["msg"])
            out.append(f"{where}: {msg}" + (f" (got {err['input']!r})" if err.get("type", "").endswith(("_type", "_parsing", "pattern_mismatch")) else ""))
        return out
