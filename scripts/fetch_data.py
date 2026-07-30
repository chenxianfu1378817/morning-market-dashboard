import json
import urllib.parse
import urllib.request
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

UA = "morning-market-dashboard/1.0"
LOCATIONS = [("南宁",22.817,108.366),("桂林",25.274,110.290),("广州",23.130,113.264),("深圳",22.543,114.058)]
OIL = [("WTI 原油", "CL=F"), ("Brent 原油", "BZ=F")]

def get_json(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req,timeout=25) as r:return json.load(r)
        except Exception:
            if attempt==2: raise
            time.sleep(2)

def weather():
    out=[]
    for name,lat,lon in LOCATIONS:
        q=urllib.parse.urlencode({"latitude":lat,"longitude":lon,"current":"temperature_2m,apparent_temperature,weather_code","daily":"temperature_2m_max,temperature_2m_min,precipitation_probability_max","timezone":"Asia/Shanghai","forecast_days":1})
        d=get_json("https://api.open-meteo.com/v1/forecast?"+q)
        out.append({"name":name,"temperature":d["current"]["temperature_2m"],"feels_like":d["current"]["apparent_temperature"],"code":d["current"]["weather_code"],"max":d["daily"]["temperature_2m_max"][0],"min":d["daily"]["temperature_2m_min"][0],"rain_probability":d["daily"]["precipitation_probability_max"][0]})
    return out

def oil():
    out=[]
    for name,symbol in OIL:
        url="https://query1.finance.yahoo.com/v8/finance/chart/"+urllib.parse.quote(symbol)+"?range=2d&interval=1m"
        try:
            d=get_json(url)["chart"]["result"][0]; meta=d["meta"]; price=meta.get("previousClose") or meta.get("chartPreviousClose"); prev=meta.get("chartPreviousClose"); change=(price-prev) if price is not None and prev is not None else None
            out.append({"name":name,"symbol":symbol,"price":price,"current_price":meta.get("regularMarketPrice"),"previous_close":prev,"change":change,"change_pct":change/prev*100 if change is not None and prev else None,"market_time":datetime.fromtimestamp(meta.get("regularMarketTime",0),timezone.utc).astimezone().strftime("%m-%d %H:%M") if meta.get("regularMarketTime") else None})
        except Exception as e: out.append({"name":name,"symbol":symbol,"error":str(e)})
    return out

def news():
    try:
        req=urllib.request.Request("https://www.chinanews.com.cn/rss/world.xml",headers={"User-Agent":UA})
        with urllib.request.urlopen(req,timeout=25) as r: root=ET.fromstring(r.read())
        return [{"title":item.findtext("title",""),"link":item.findtext("link",""),"published":item.findtext("pubDate","")} for item in root.findall("./channel/item")[:6]]
    except Exception as e:
        return [{"title":"国际新闻暂时无法更新","link":"https://www.bbc.com/news/world","published":"","error":str(e)}]

now=datetime.now().astimezone()
data={"updated_at":now.strftime("%Y-%m-%d %H:%M"),"timezone":"Asia/Shanghai","weather":weather(),"oil":oil(),"news":news()}
history_path=Path("data/history.json")
try: history=json.loads(history_path.read_text(encoding="utf-8"))
except (FileNotFoundError,json.JSONDecodeError): history=[]
history.append({"time":now.strftime("%Y-%m-%d %H:%M"),"oil":[{"symbol":x.get("symbol"),"price":x.get("price")} for x in data["oil"] if x.get("price") is not None]})
history=history[-672:]
with open("data/latest.json","w",encoding="utf-8") as f:json.dump(data,f,ensure_ascii=False,indent=2)
with open(history_path,"w",encoding="utf-8") as f:json.dump(history,f,ensure_ascii=False,indent=2)
