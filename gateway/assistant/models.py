from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class TravelMode(str, Enum):
    walk = "walk"
    drive = "drive"
    transit = "transit"
    bicycle = "bicycle"
    taxi = "taxi"


class Location(BaseModel):
    longitude: float = Field(ge=73, le=135)
    latitude: float = Field(ge=3, le=54)
    accuracy_m: float | None = Field(default=None, ge=0)


class TurnRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    location: Location | None = None
    location_system: Literal["wgs84", "gcj02"] = "wgs84"
    city: str | None = None
    provider: str | None = None
    model: str | None = None


class MapPlan(BaseModel):
    action: Literal["search", "route", "navigate", "taxi_handoff"]
    query: str = Field(min_length=1, max_length=80)
    radius_m: int = Field(default=5000, ge=1, le=50000)
    ranking: Literal["nearest", "rating"] = "nearest"
    travel_mode: TravelMode = TravelMode.walk


class Place(BaseModel):
    id: str
    name: str
    address: str = ""
    longitude: float
    latitude: float
    distance_m: int
    rating: float | None = None
    citycode: str | None = None


class Route(BaseModel):
    mode: TravelMode
    distance_m: int | None = None
    duration_s: int | None = None
    estimated_taxi_yuan: float | None = None


class Action(BaseModel):
    id: str
    kind: Literal["handoff"]
    title: str
    url: str
    requires_confirmation: bool = True


class TurnResponse(BaseModel):
    status: Literal["completed", "needs_clarification", "needs_confirmation", "unsupported", "failed"]
    spoken: str
    places: list[Place] = Field(default_factory=list)
    route: Route | None = None
    action: Action | None = None
    detail: str | None = None
