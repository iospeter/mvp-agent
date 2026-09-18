import html
import re
import urllib.request
import urllib.parse
import urllib.error

from pydantic import BaseModel

from tools import BaseTool

class _Result:
    def __init__(self, title:str, snippet:str,url:str):
        self.title = title
        self.snippet = snippet
        self.url = url

    def format(self):
        url = self.url.strip('`')
        return f"- {self.title}\n  {self.snippet}\n  {url}"

def _parse_bing(html_text:str, max_results:int = 5) ->list:
    """从 Bing 国内版 HTML 抓前 N 条结果。
    每条结果位于 <li class="b_algo"> 块内：
      - 标题：<h2><a ...>TITLE</a></h2>
      - 摘要：<div class="b_caption"><p ...>SNIPPET</p></div>
      - 展示URL：<cite>URL</cite>
    用正则切块 + 子正则抽取，避免引入 BeautifulSoup 依赖。
    """
    results = []
    blocks = re.split(r'<li class="b_algo"', html_text)
    for block in blocks[1:max_results + 1]:
        title_m = re.search(r'<h2[^>]*><a[^>]*>(.*?)</a></h2>', block, re.DOTALL)
        snippet_m = re.search(r'<div class="b_caption"><p[^>]*>(.*?)</p>', block, re.DOTALL)
        url_m = re.search(r'<cite>(.*?)</cite>', block, re.DOTALL)
        title = html.unescape(re.sub(r"<[^>]+>", "", title_m.group(1))).strip() if title_m else ""

        snippet = html.unescape(re.sub(r"<[^>]+>", "", snippet_m.group(1))).strip() if snippet_m else ""
        url = html.unescape(re.sub(r"<[^>]+>", "", url_m.group(1))).strip() if url_m else ""
        if title:
            results.append(_Result(title, snippet, url))
    return results


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "联网搜索，返回前 5 条结果（标题+摘要+链接）。用于获取实时信息或回答需要联网的问题。"
    class Input(BaseModel):
        query: str

    def run(self, query:str) -> str:
        if not query or not query.strip():
            return "搜索失败：query 不能为空"
        if "?" in query:
            return f"搜索失败：query 含乱码占位符（可能是编码问题）: {query} "

        try:
            url = "https://cn.bing.com/search?q=" + urllib.parse.quote(query)
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw =resp.read()
                try:
                    html_text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    html_text = raw.decode("utf-8",errors="replace")
            results = _parse_bing(html_text, max_results=5)
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

