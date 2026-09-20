# d:\ASpace\AgentWork\mvp_agent\tests\test_dead_loop.py
from agents._dead_loop import DeadLoopDetector

def test_below_threshold_not_dead_loop():
    d = DeadLoopDetector(max_repeat=3)
    assert d.record("calculator", {"expr": "1+1"}) is False
    assert d.record("calculator", {"expr": "1+1"}) is False

def test_at_threshold_is_dead_loop():
    d = DeadLoopDetector(max_repeat=3)
    d.record("calculator", {"expr": "1+1"})
    d.record("calculator", {"expr": "1+1"})
    assert d.record("calculator", {"expr": "1+1"}) is True

def test_still_detected_after_threshold():
    d = DeadLoopDetector(max_repeat=3)
    for _ in range(6):
        d.record("calculator", {"expr": "1+1"})
    assert d.record("calculator", {"expr": "1+1"}) is True

def test_different_args_not_dead_loop():
    d = DeadLoopDetector(max_repeat=3)
    for i in range(5):
        assert d.record("web_search", {"query": f"q{i}"}) is False

def test_reset_clears_history():
    d = DeadLoopDetector(max_repeat=2)
    d.record("a", {})
    assert d.record("a", {}) is True
    d.reset()
    assert d.record("a", {}) is False