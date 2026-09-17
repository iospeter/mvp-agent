from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from tools import BaseTool


class GetCurrentTimeTool(BaseTool):
    name = "get_current_time"
    description = "获取指定时区的当前日期和时间"
    class Input(BaseModel):
        timezone:str = "Asia/Shanghai"
    def run(self, timezone:str = "Asia/Shanghai") -> str:
        try:
            tz = ZoneInfo(timezone)
        except Exception:
            return f"时区错误: {timezone} ，请使用 IANA 时区名（如 Asia/Shanghai、America/New_York）"
        now = datetime.now(tz)
        return f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S %Z')} （时区: {timezone} ）"