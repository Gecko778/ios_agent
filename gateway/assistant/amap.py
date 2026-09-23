import math
from urllib.parse import urlencode

import httpx

from .models import Location, Place, Route, TravelMode


class AmapError(Exception):
    pass


def distance_m(a: Location, b: Location) -> int:
    r = 6371000
    p1, p2 = math.radians(a.latitude), math.radians(b.latitude)
    dp = p2 - p1
    dl = math.radians(b.longitude - a.longitude)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(min(1, math.sqrt(h))))


def _coordinate(value: str) -> Location:
    longitude, latitude = value.split(",")
    return Location(longitude=float(longitude), latitude=float(latitude))


def _number(value: object) -> float | None:
    if value in (None, "", "[]") or isinstance(value, (dict, list)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class AmapClient:
    def __init__(self, key: str, client: httpx.AsyncClient):
        self.key = key
        self.client = client

    async def _get(self, path: str, params: dict[str, object]) -> dict:
        try:
            response = await self.client.get(
                f"https://restapi.amap.com{path}",
                params={**params, "key": self.key, "output": "JSON"},
                timeout=8,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AmapError("高德接口暂时不可用") from exc
        if str(payload.get("status")) != "1":
            raise AmapError(f"高德接口返回错误：{payload.get('info', 'unknown')}")
        return payload

    async def to_gcj02(self, location: Location, coordinate_system: str) -> Location:
        if coordinate_system == "gcj02":
            return location
        payload = await self._get(
            "/v3/assistant/coordinate/convert",
            {"locations": f"{location.longitude:.6f},{location.latitude:.6f}", "coordsys": "gps"},
        )
        return _coordinate(payload["locations"])

    async def search_nearby(
        self, query: str, center: Location, radius_m: int, ranking: str
    ) -> tuple[list[Place], bool]:
        places: list[Place] = []
        complete = True
        for page in range(1, 11):
            payload = await self._get(
                "/v3/place/around",
                {
                    "location": f"{center.longitude:.6f},{center.latitude:.6f}",
                    "keywords": query,
                    "radius": radius_m,
                    "sortrule": "distance",
                    "extensions": "all",
                    "offset": 25,
                    "page": page,
                },
            )
            batch = payload.get("pois", [])
            for raw in batch:
                try:
                    point = _coordinate(raw["location"])
                    actual_distance = distance_m(center, point)
                    if actual_distance > radius_m:
                        continue
                    rating = _number((raw.get("biz_ext") or {}).get("rating"))
                    places.append(
                        Place(
                            id=raw["id"],
                            name=raw["name"],
                            address=str(raw.get("address") or ""),
                            longitude=point.longitude,
                            latitude=point.latitude,
                            distance_m=actual_distance,
                            rating=rating,
                            citycode=str(raw.get("citycode")) if raw.get("citycode") else None,
                        )
                    )
                except (KeyError, TypeError, ValueError):
                    continue
            total = int(payload.get("count") or 0)
            if len(batch) < 25 or page * 25 >= total:
                break
        else:
            complete = False

        unique = {place.id: place for place in places}
        result = list(unique.values())
        if ranking == "rating":
            result = [place for place in result if place.rating is not None]
            result.sort(key=lambda place: (-place.rating, place.distance_m))
        else:
            result.sort(key=lambda place: place.distance_m)
        return result, complete

    async def route(self, start: Location, end: Location, mode: TravelMode, city: str | None) -> Route:
        route_mode = TravelMode.drive if mode == TravelMode.taxi else mode
        path = {
            TravelMode.walk: "/v5/direction/walking",
            TravelMode.drive: "/v5/direction/driving",
            TravelMode.transit: "/v5/direction/transit/integrated",
            TravelMode.bicycle: "/v5/direction/bicycling",
        }[route_mode]
        params: dict[str, object] = {
            "origin": f"{start.longitude:.6f},{start.latitude:.6f}",
            "destination": f"{end.longitude:.6f},{end.latitude:.6f}",
            "show_fields": "cost",
        }
        if route_mode == TravelMode.transit:
            if not city:
                raise AmapError("公交路线需要目标地点的城市代码")
            params["city1"] = city
            params["city2"] = city
        payload = await self._get(path, params)
        route = payload.get("route") or {}
        options = route.get("transits" if route_mode == TravelMode.transit else "paths") or []
        if not options:
            raise AmapError("高德没有返回可用路线")
        first = options[0]
        cost = first.get("cost") or {}
        return Route(
            mode=mode,
            distance_m=int(float(first["distance"])) if _number(first.get("distance")) is not None else None,
            duration_s=int(float(cost.get("duration") or first.get("duration")))
            if _number(cost.get("duration") or first.get("duration")) is not None else None,
            estimated_taxi_yuan=_number(route.get("taxi_cost") or cost.get("taxi_fee")) if mode == TravelMode.taxi else None,
        )


def route_url(place: Place, mode: TravelMode) -> str:
    travel = {"walk": 2, "drive": 0, "taxi": 0, "transit": 1, "bicycle": 3}[mode.value]
    return "iosamap://path?" + urlencode(
        {
            "sourceApplication": "LocalAssistant",
            "did": place.id,
            "dlat": f"{place.latitude:.6f}",
            "dlon": f"{place.longitude:.6f}",
            "dname": place.name,
            "dev": 0,
            "t": travel,
            "m": 0,
        }
    )
