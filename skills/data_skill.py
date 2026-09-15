from tools import CalculatorTool, SearchDemoTool, search_demo


class AnalysisSkill:
    def __init__(self):
        self.calc = CalculatorTool()
        self.search = SearchDemoTool()

    def analyse_number(self, number_expr:str, desc_query:str):
        calc_result = self.calc.run(number_expr)
        search_result = self.search.run(desc_query)
        return f"【分析输出】\n {calc_result}\n{search_result}"