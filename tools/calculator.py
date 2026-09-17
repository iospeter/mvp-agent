import ast
import operator

from pydantic import BaseModel

from tools import BaseTool

_SAFE_OPS ={
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

def _safe_eval(expr):
    """只允许数字和基本算术运算（+ - * / // % ** 及括号、一元正负）的安全求值，
        拒绝函数调用、名称引用、属性访问、import 等一切有注入风险的节点。"""
    tree = ast.parse(expr, mode="eval")
    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError(f"不支持的常量类型: {type(node.value).__name__}")

        if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPS:
            return _SAFE_OPS[type(node.op)](_eval(node.left), _eval(node.right))

        if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPS:
            return _SAFE_OPS[type(node.op)](_eval(node.operand))
        raise ValueError(f"不支持的表达式节点: {type(node).__name__}")
    return _eval(tree)

class CalculatorTool(BaseTool):
    name = "calculator"
    description = "执行数学计算，输入表达式字符串"

    class Input(BaseModel):
        expr:str
    def run(self,expr:str) -> str:
        try:
            res = _safe_eval(expr)
            return f"计算结果:{res}"
        except Exception as e:
            return f"计算错误:{str(e)}"