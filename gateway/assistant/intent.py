import re

from .models import MapPlan, TravelMode


def parse_map_request(text: str) -> MapPlan | None:
    """Handle clear Chinese map requests without spending a model call."""
    if not any(token in text for token in ("导航", "附近", "最近", "怎么走", "步行", "打车", "地铁", "多远", "多久")):
        return None

    match = re.search(r"(?:附近)?([一二三四五六七八九十\d]+)\s*(公里|千米|km|米)(?:内|以内)?", text, re.I)
    radius = 5000
    if match:
        chinese = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
        number = int(match.group(1)) if match.group(1).isdigit() else chinese.get(match.group(1))
        if number is None:
            return None
        radius = number * (1000 if match.group(2).lower() in ("公里", "千米", "km") else 1)
    if not 1 <= radius <= 50000:
        return None

    if "地铁站" in text:
        query = "地铁站"
    elif "星巴克" in text:
        query = "星巴克"
    else:
        candidate = re.search(r"(?:最近的|附近的|到|去)([^，。？?]+?)(?:怎么走|要多久|有多远|进行导航|导航|$)", text)
        if not candidate:
            return None
        query = candidate.group(1).strip("的 ")
        if not query:
            return None

    mode = TravelMode.walk
    if "打车" in text:
        mode = TravelMode.taxi
    elif "公交" in text or "地铁" in text and "地铁站" not in text:
        mode = TravelMode.transit
    elif "骑行" in text or "骑车" in text:
        mode = TravelMode.bicycle
    elif "驾车" in text or "开车" in text:
        mode = TravelMode.drive

    action = "taxi_handoff" if mode == TravelMode.taxi else "navigate" if "导航" in text or "怎么走" in text else "route" if "多久" in text or "多远" in text else "search"
    ranking = "rating" if "评分最高" in text else "nearest"
    return MapPlan(action=action, query=query, radius_m=radius, ranking=ranking, travel_mode=mode)
