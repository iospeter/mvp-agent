from pydantic import BaseModel

from tools import CalculatorTool, BaseTool, WebSearchTool


class AnalysisSkill(BaseTool):
    name = "analysis"
    description = "对数字表达式进行计算并联网搜索补充说明，输出综合分析结果"
    class Input(BaseModel):
        number_expr: str
        desc_query: str
    def __init__(self):
        super().__init__()
        self.calc = CalculatorTool()
        self.search = WebSearchTool()

    def run(self, number_expr:str, desc_query:str):
        calc_result = self.calc.run(number_expr)
        search_result = self.search.run(desc_query)
        return f"【分析输出】\n {calc_result}\n{search_result}"