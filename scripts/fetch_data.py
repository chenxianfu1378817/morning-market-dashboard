import html
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


UA = "morning-market-dashboard/1.0"
SHANGHAI = ZoneInfo("Asia/Shanghai")
LOCATIONS = [("南宁", 22.817, 108.366), ("桂林", 25.274, 110.290), ("广州", 23.130, 113.264), ("深圳", 22.543, 114.058)]
OIL = [("WTI 原油", "CL=F"), ("Brent 原油", "BZ=F")]
LATEST_PATH = Path("data/latest.json")
HISTORY_PATH = Path("data/history.json")


def get_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=18) as response:
                return json.load(response)
        except Exception as error:
            last_error = error
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    raise last_error


def load_json(path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return fallback


def weather(previous):
    previous_by_city = {item.get("name"): item for item in previous if item.get("name")}
    results, errors = [], []
    for name, latitude, longitude in LOCATIONS:
        query = urllib.parse.urlencode({
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,apparent_temperature,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "Asia/Shanghai",
            "forecast_days": 1,
        })
        try:
            data = get_json("https://api.open-meteo.com/v1/forecast?" + query)
            current, daily = data["current"], data["daily"]
            results.append({
                "name": name,
                "temperature": current["temperature_2m"],
                "feels_like": current["apparent_temperature"],
                "code": current["weather_code"],
                "max": daily["temperature_2m_max"][0],
                "min": daily["temperature_2m_min"][0],
                "rain_probability": daily["precipitation_probability_max"][0],
                "stale": False,
            })
        except Exception as error:
            old = previous_by_city.get(name)
            if old:
                results.append({**old, "stale": True})
            else:
                results.append({"name": name, "stale": True, "unavailable": True})
            errors.append({"source": f"天气·{name}", "message": str(error)[:240]})
    return results, errors


def oil(previous):
    previous_by_symbol = {item.get("symbol"): item for item in previous if item.get("symbol")}
    results, errors = [], []
    for name, symbol in OIL:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(symbol) + "?range=2d&interval=1m"
        try:
            chart = get_json(url)["chart"]["result"][0]
            meta = chart["meta"]
            timestamps = chart.get("timestamp") or []
            closes = chart.get("indicators", {}).get("quote", [{}])[0].get("close", [])
            latest_chart_price = next((value for value in reversed(closes) if value is not None), None)
            latest_price = meta.get("regularMarketPrice") or latest_chart_price
            previous_close = meta.get("previousClose") or meta.get("chartPreviousClose")
            change = latest_price - previous_close if latest_price is not None and previous_close is not None else None
            market_timestamp = meta.get("regularMarketTime") or (timestamps[-1] if timestamps else None)
            results.append({
                "name": name,
                "symbol": symbol,
                "price": latest_price,
                "current_price": latest_price,
                "previous_close": previous_close,
                "change": change,
                "change_pct": change / previous_close * 100 if change is not None and previous_close else None,
                "market_time": datetime.fromtimestamp(market_timestamp, timezone.utc).astimezone(SHANGHAI).strftime("%m-%d %H:%M") if market_timestamp else None,
                "stale": False,
            })
        except Exception as error:
            old = previous_by_symbol.get(symbol)
            if old:
                results.append({**old, "stale": True})
            else:
                results.append({"name": name, "symbol": symbol, "stale": True, "unavailable": True})
            errors.append({"source": name, "message": str(error)[:240]})
    return results, errors


def news(previous):
    try:
        request = urllib.request.Request("https://www.chinanews.com.cn/rss/world.xml", headers={"User-Agent": UA})
        with urllib.request.urlopen(request, timeout=18) as response:
            root = ET.fromstring(response.read())
        items = [{"title": item.findtext("title", ""), "link": item.findtext("link", ""), "published": item.findtext("pubDate", ""), "stale": False}
                 for item in root.findall("./channel/item")[:6]]
        if not items:
            raise ValueError("新闻源未返回内容")
        return items, []
    except Exception as error:
        return ([{**item, "stale": True} for item in previous] or [{"title": "国际新闻暂时无法更新", "link": "https://www.chinanews.com.cn/world/", "published": "", "stale": True}]), [{"source": "国际新闻", "message": str(error)[:240]}]


def translate(text):
    try:
        query = urllib.parse.urlencode({"q": text[:450], "langpair": "en|zh-CN"})
        data = get_json("https://api.mymemory.translated.net/get?" + query)
        return data.get("responseData", {}).get("translatedText") or text
    except Exception:
        return text


def truth_posts(previous):
    try:
        request = urllib.request.Request("https://trumpstruth.org/feed", headers={"User-Agent": UA})
        with urllib.request.urlopen(request, timeout=18) as response:
            root = ET.fromstring(response.read())
        items = []
        for item in root.findall("./channel/item")[:5]:
            title = html.unescape(item.findtext("title", "")).strip()
            raw = re.sub("<[^>]+>", " ", item.findtext("description", "") or "")
            original = html.unescape(re.sub(r"\s+", " ", raw)).strip() or title
            items.append({"original": original, "translated": translate(original), "link": item.findtext("link", ""), "published": item.findtext("pubDate", ""), "stale": False})
        if not items:
            raise ValueError("动态源未返回内容")
        return items, []
    except Exception as error:
        fallback = [{**item, "stale": True} for item in previous] or [{"original": "暂时无法读取 Truth Social 镜像数据", "translated": "暂时无法读取 Truth Social 镜像数据", "link": "https://trumpstruth.org/", "published": "", "stale": True}]
        return fallback, [{"source": "特朗普动态", "message": str(error)[:240]}]


def main():
    previous_data = load_json(LATEST_PATH, {})
    now = datetime.now(SHANGHAI)
    weather_data, weather_errors = weather(previous_data.get("weather", []))
    oil_data, oil_errors = oil(previous_data.get("oil", []))
    news_data, news_errors = news(previous_data.get("news", []))
    truth_data, truth_errors = truth_posts(previous_data.get("truth_posts", []))
    errors = weather_errors + oil_errors + news_errors + truth_errors
    data = {
        "updated_at": now.strftime("%Y-%m-%d %H:%M"),
        "updated_at_iso": now.isoformat(timespec="seconds"),
        "timezone": "Asia/Shanghai",
        "weather": weather_data,
        "oil": oil_data,
        "news": news_data,
        "truth_posts": truth_data,
        "errors": errors,
    }

    history = load_json(HISTORY_PATH, [])
    history.append({"time": now.strftime("%Y-%m-%d %H:%M"), "oil": [{"symbol": item.get("symbol"), "price": item.get("price")} for item in oil_data if item.get("price") is not None and not item.get("stale")]})
    history = history[-672:]
    LATEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    LATEST_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
