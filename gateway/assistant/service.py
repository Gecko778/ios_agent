import uuid

from .amap import AmapClient, AmapError, route_url
from .intent import parse_map_request
from .models import Action, Location, MapPlan, TurnRequest, TurnResponse, TravelMode
from .providers import ProviderClient, ProviderError


class AssistantService:
    def __init__(self, amap: AmapClient, provider: ProviderClient):
        self.amap = amap
        self.provider = provider

    async def turn(self, request: TurnRequest) -> TurnResponse:
        plan = parse_map_request(request.text)
        if plan is None and request.provider:
            try:
                plan = await self.provider.plan(request.provider, request.model, request.text)
            except ProviderError as exc:
                return TurnResponse(status="failed", spoken=str(exc))
        if plan is None:
            return TurnResponse(status="unsupported", spoken="目前只能处理地点搜索、路线和导航。请说出地点和想做的事。")
        if request.location is None:
            return TurnResponse(status="needs_clarification", spoken="请允许定位，或告诉我你所在的地点。")

        try:
            center = await self.amap.to_gcj02(request.location, request.location_system)
            places, complete = await self.amap.search_nearby(plan.query, center, plan.radius_m, plan.ranking)
            if not places:
                condition = f"{plan.radius_m / 1000:g} 公里内"
                qualifier = "有评分的" if plan.ranking == "rating" else ""
                return TurnResponse(
                    status="needs_clarification",
                    spoken=f"{condition}没有找到{qualifier}{plan.query}。要不要扩大范围？",
                )
            selected = places[0]
            route = None
            if plan.action in ("route", "navigate", "taxi_handoff"):
                destination = Location(longitude=selected.longitude, latitude=selected.latitude)
                route = await self.amap.route(center, destination, plan.travel_mode, selected.citycode or request.city)
            return self._reply(plan, places[:5], route, complete)
        except AmapError as exc:
            return TurnResponse(status="failed", spoken=str(exc))

    @staticmethod
    def _reply(plan: MapPlan, places: list, route, complete: bool) -> TurnResponse:
        first = places[0]
        ranked = ("评分最高的" if complete else "已检索地点中评分最高的") if plan.ranking == "rating" else "最近的"
        spoken = f"找到{ranked}{first.name}，距离约 {first.distance_m} 米。"
        if first.rating is not None and plan.ranking == "rating":
            spoken += f"高德评分 {first.rating:g}。"
        if route and route.duration_s is not None:
            spoken += f"预计 {round(route.duration_s / 60)} 分钟。"
        if route and route.estimated_taxi_yuan is not None:
            spoken += f"预计出租车费用约 {route.estimated_taxi_yuan:g} 元。"
        detail = None if complete else "高德结果超过本次检索上限；排序仅覆盖已返回的地点。"
        if plan.action not in ("navigate", "taxi_handoff"):
            return TurnResponse(status="completed", spoken=spoken, places=places, route=route, detail=detail)
        if plan.action == "taxi_handoff":
            spoken += "我可以打开高德，车型选择和叫车需要你在高德完成。"
        else:
            spoken += "要打开高德继续导航吗？"
        action = Action(
            id=str(uuid.uuid4()),
            kind="handoff",
            title=f"用高德前往{first.name}",
            url=route_url(first, TravelMode.drive if plan.travel_mode == TravelMode.taxi else plan.travel_mode),
        )
        return TurnResponse(status="needs_confirmation", spoken=spoken, places=places, route=route, action=action, detail=detail)
