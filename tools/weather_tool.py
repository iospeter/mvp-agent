import json
import urllib.request
import urllib.parse
import urllib.error

from pydantic import BaseModel

from tools import BaseTool

_EN_ZH_WEATHER = {
    "Clear": "晴", "Sunny": "晴", "Partly cloudy": "多云", "Partly Cloudy": "多云",
    "Cloudy": "阴", "Overcast": "阴", "Mist": "薄雾", "Fog": "雾",
    "Light rain": "小雨", "Moderate rain": "中雨", "Heavy rain": "大雨",
    "Light snow": "小雪", "Moderate snow": "中雪", "Heavy snow": "大雪",
    "Thunderstorm": "雷阵雨", "Drizzle": "毛毛雨", "Light drizzle": "小毛毛雨", "Heavy drizzle": "大毛毛雨",
    "Light rain shower": "阵雨", "Heavy rain shower": "大阵雨",
    "Light snow shower": "阵雪", "Heavy snow shower": "大阵雪",
    "Haze": "霾",
    "Smoky haze": "烟霾", "Smoke": "烟", "Dust": "扬沙", "Sand": "沙尘",
    "Patchy rain nearby": "局部小雨", "Patchy snow nearby": "局部小雪",
    "Patchy light rain": "零星小雨", "Patchy light snow": "零星小雪",
}

def _to_zh(desc: str) -> str:
    if not desc:
        return "未知"
    return _EN_ZH_WEATHER.get(desc.strip(), desc)


class WeatherQueryTool(BaseTool):
    name = "weather_query"
    description = "查询指定城市的实时天气（温度、天气状况、湿度、风速）"
    class Input(BaseModel):
        city: str

    def run(self, city: str) -> str:
        try:
            # 用 zh-cn 让 wttr.in 返回 lang_zh 字段；同时 format=j1 拿结构化 JSON
            url = f"https://wttr.in/{urllib.parse.quote(city)}?format=j1&lang=zh-cn"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            # 只拦请求端乱码（包含 ? 占位符），不再比对返回的 areaName
            # 因为 wttr.in 会把中文翻译成英文/拼音返回，纯字符串匹配会误判
            city_norm = city.strip()
            if "?" in city_norm:
                return f"城市名包含乱码占位符（可能是编码问题）: {city}"

            current = data["current_condition"][0]
            temp = current["temp_C"]
            feels = current["FeelsLikeC"]
            # 优先用 lang_zh，其次用中文映射表兜底，最后原样返回
            raw_desc = (current.get("lang_zh") or [{}])[0].get("value", "") if current.get("lang_zh") else ""
            if not raw_desc:
                raw_desc = (current.get("weatherDesc") or [{}])[0].get("value", "") if current.get("weatherDesc") else ""
            desc = _to_zh(raw_desc)
            humidity = current["humidity"]
            wind = current["windspeedKmph"]

            return (
                f"【 {city} 实时天气】\n" 
                f"天气: {desc} \n" 
                f"温度: {temp} °C（体感 {feels} °C）\n" 
                f"湿度: {humidity} %\n" 
                f"风速: {wind} km/h"
            )
        except urllib.error.URLError as e:
            return f"天气查询失败（网络错误）: {e} "
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            return f"天气查询失败（数据解析错误）: {e} "
        except Exception as e:
            return f"天气查询异常: {e} "

