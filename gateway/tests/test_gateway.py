import json

import httpx
import pytest

from assistant.amap import AmapClient, route_url
from assistant.intent import parse_map_request
from assistant.models import Location, Place, TurnRequest
from assistant.providers import ProviderClient
from assistant.service import AssistantService


ORIGIN = Location(longitude=116.400000, latitude=39.900000)


def test_given_examples_parse_to_intended_actions():
    first = parse_map_request("用高德导航导航到最近的星巴克")
    assert first.action == "navigate" and first.query == "星巴克"
    second = parse_map_request("帮我导航到最近的星巴克")
    assert second.action == "navigate" and second.query == "星巴克"
    third = parse_map_request("帮我找出附近三公里内评分最高的星巴克")
    assert third.radius_m == 3000 and third.ranking == "rating"
    assert parse_map_request("步行到最近的星巴克要多久").action == "route"
    assert parse_map_request("最近的地铁站该怎么走").query == "地铁站"
    assert parse_map_request("帮我用比较低的价格打车到最近的星巴克").action == "taxi_handoff"


@pytest.mark.asyncio
async def test_amap_filters_outside_radius_and_ranks_rated_places():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v3/place/around"
        assert request.url.params["radius"] == "3000"
        return httpx.Response(
            200,
            json={
                "status": "1",
                "count": "3",
                "pois": [
                    {"id": "near", "name": "星巴克 A", "location": "116.401,39.900", "biz_ext": {"rating": "4.5"}},
                    {"id": "far", "name": "星巴克 B", "location": "116.500,39.900", "biz_ext": {"rating": "5.0"}},
                    {"id": "best", "name": "星巴克 C", "location": "116.402,39.900", "biz_ext": {"rating": "4.8"}},
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        places, complete = await AmapClient("fixture-key", http).search_nearby("星巴克", ORIGIN, 3000, "rating")
    assert complete
    assert [place.id for place in places] == ["best", "near"]
    assert all(place.distance_m <= 3000 for place in places)


@pytest.mark.asyncio
async def test_service_returns_confirmed_handoff_without_claiming_completion():
    class FakeAmap:
        async def to_gcj02(self, location, coordinate_system):
            return location

        async def search_nearby(self, query, center, radius_m, ranking):
            return [Place(id="poi", name="星巴克 A", longitude=116.401, latitude=39.9, distance_m=85)], True

        async def route(self, start, end, mode, city):
            from assistant.models import Route

            return Route(mode=mode, duration_s=600)

    response = await AssistantService(FakeAmap(), None).turn(
        TurnRequest(text="用高德导航导航到最近的星巴克", location=ORIGIN, location_system="gcj02")
    )
    assert response.status == "needs_confirmation"
    assert response.action.requires_confirmation
    assert response.action.url.startswith("iosamap://path?")


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["openai", "deepseek", "anthropic", "glm", "kimi"])
async def test_five_provider_wire_formats(monkeypatch, provider):
    monkeypatch.setenv("LOCAL_ASSISTANT_TEST_MODE", "1")
    monkeypatch.setenv(f"LOCAL_ASSISTANT_{provider.upper()}", "fixture-key")
    plan = {"action": "search", "query": "星巴克", "radius_m": 3000, "ranking": "rating", "travel_mode": "walk"}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"]
        if provider == "openai":
            assert body["store"] is False
            result = {"output": [{"type": "function_call", "name": "plan_map_request", "arguments": json.dumps(plan)}]}
        elif provider == "anthropic":
            result = {"content": [{"type": "tool_use", "name": "plan_map_request", "input": plan}]}
        else:
            result = {"choices": [{"message": {"tool_calls": [{"function": {"name": "plan_map_request", "arguments": json.dumps(plan)}}]}}]}
        return httpx.Response(200, json=result)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        parsed = await ProviderClient(http).plan(provider, None, "帮我找3公里内评分最高的星巴克")
    assert parsed.query == "星巴克" and parsed.radius_m == 3000
