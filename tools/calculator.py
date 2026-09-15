from pydantic import BaseModel
class CalculatorTool:
    name = "calculator"
    description = "执行数学计算，输入表达式字符串"

    class Input(BaseModel):
        expr:str
    def run(self,expr:str) -> str:
        try:
            res = eval(expr)
            return f"计算结果:{res}"
        except Exception as e:
            return f"计算错误:{str(e)}"