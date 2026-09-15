import pytest

from agents.agent import SimpleAgent

def test_agent_init():
    agent = SimpleAgent()
    assert agent is not None

def test_query():
    agent = SimpleAgent()
    out = agent.run("1+2等于几")
    assert out is not None