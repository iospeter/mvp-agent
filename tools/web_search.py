import html
import re
import urllib.request
import urllib.parse
import urllib.error

from bs4 import BeautifulSoup
from openpyxl.styles.builtins import title
from pydantic import BaseModel

from tools import BaseTool

class _Result:
    def __init__(self, title:str, snippet:str,url:str):
        self.title = title
        self.snippet = snippet
        self.url = url

    def format(self):
        return f"- {self.title} \n {self.snippet} \n {self.url} "

def _parse_ddg_lite(html_text, max_results):
    """从 DuckDuckGo Lite 的 HTML 抓前 N 条结果。

        DDG Lite 的结构稳定：每条结果由 <a class="result-link" href="URL">TITLE</a>
        和紧随其后的 <a class="result-snippet" ...>SNIPPET</a> 组成。
        用正则抽取，避免引入 BeautifulSoup 依赖。
        """
    results = []
    pattern = re.compile(
        r'<a[^>]+class="result-link"[^>]*href="([^"]+)"[^>]*>(.*?)</a>' 
        r'.*?<a[^>]+class="result-snippet"[^>]*>(.*?)</a>',
        re.DOTALL,
    )

    for m in pattern.finditer(html_text):
        url = html.unescape(m.group(1))
        title = html.unescape(re.sub(r'<[^>]+>', '', m.group(2)).strip())
        snippet = html.unescape(re.sub(r'<[^>]+>', '', m.group(3)).strip())

        if title and url:
            results.append(_Result(title, snippet, url))
        if len(results) >= max_results:
            break
    return  results


class WebSearchTool(BaseTool):
    name = "Web Search"
    description = "联网搜索，返回前 5 条结果（标题+摘要+链接）。用于获取实时信息或回答需要联网的问题。"
    class Input(BaseModel):
        query: str

    def run(self, query:str) -> str:
        if not query or not query.strip():
            return "搜索失败：query 不能为空"
        if "?" in query:
            return f"搜索失败：query 含乱码占位符（可能是编码问题）: {query} "

        try:
            url = "https://lite.duckduckgo.com/lite/?q=" + urllib.parse.quote(query) + "&kl=cn-zh"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(url, timeout=10) as resp:
                raw =resp.read()
                try:
                    html_text = raw.decode("utf8")
                except UnicodeDecodeError:
                    html_text = raw.decode("utf-8",errors="replace")
            results = _parse_ddg_lite(html_text, max_results=5)
            if not results:
                return f"未找到与 ' {query} ' 相关的结果（可能被限流或页面结构变化）"

            lines = [f"【Web 搜索结果】query= {query}"]
            for r in results:
                lines.append(r.format())
            return "\n".join(lines)
        except urllib.error.URLError as e:
            return f"搜索失败（网络错误）: {e} "
        except Exception as e:
            return f"搜索异常: {e} "

