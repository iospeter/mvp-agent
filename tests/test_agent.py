from unittest.mock import patch

from agents.agent import SimpleAgent

def test_agent_init():
    agent = SimpleAgent()
    assert agent is not None

def test_query():
    agent = SimpleAgent()
    out = agent.run("1+2等于几")
    assert out is not None

def test_query_uses_calculator(capfd):
    agent = SimpleAgent()
    out = agent.run("1+2等于几")
    captured = capfd.readouterr()

    assert out is not None
    assert "[TOOL CALL]" in captured.out
    assert "calculator" in captured.out
    assert "[TOOL RESULT] 计算结果:3" in captured.out

def test_query_uses_calculator_tool():
    agent = SimpleAgent()
    with patch.object(agent.tools_map["calculator"], "run", wraps = agent.tools_map["calculator"].run) as mock_run:
        out = agent.run("1+2等于几")
    mock_run.assert_called()
    assert mock_run.call_args.kwargs.get("expr") == "1+2"

def test_force_tool_call():
    """验证 tool_choice 参数被正确透传给 API（不依赖真实模型行为）"""
    from unittest.mock import patch, MagicMock

    agent = SimpleAgent()

    # 模拟第一轮响应：模型返回 tool_calls（被强制调用 calculator）
    mock_msg = MagicMock()
    mock_msg.tool_calls = [MagicMock(
        id="call_123",
        function=MagicMock(name="calculator", arguments='{"expr":"1+2"}')
    )]
    mock_msg.content = None
    mock_msg.model_dump.return_value = {
        "role": "assistant",
        "tool_calls": [{
            "id": "call_123",
            "type": "function",
            "function": {"name": "calculator", "arguments": '{"expr":"1+2"}'}
        }]
    }
    mock_resp = MagicMock()
    mock_resp.choices[0].message = mock_msg

    # 模拟第二轮响应：模型基于工具结果总结
    mock_msg2 = MagicMock()
    mock_msg2.tool_calls = None
    mock_msg2.content = "计算结果是 3"
    mock_resp2 = MagicMock()
    mock_resp2.choices[0].message = mock_msg2

    with patch.object(agent.client.chat.completions, "create",
                      side_effect=[mock_resp, mock_resp2]) as mock_create:
        out = agent.run(
            "今天天气真好",
            tool_choice={"type": "function", "function": {"name": "calculator"}}
        )

    # 核心断言：第一次调用 create 时，tool_choice 就是我们传入的值
    first_call = mock_create.call_args_list[0]
    assert first_call.kwargs["tool_choice"] == {
        "type": "function", "function": {"name": "calculator"}
    }
    assert out == "计算结果是 3"
