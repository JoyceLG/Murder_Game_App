from src.adapters.system_clock import SystemClock


def test_system_clock_returns_non_decreasing_millis():
    clock = SystemClock()
    first = clock.now_ms()
    second = clock.now_ms()
    assert isinstance(first, int)
    assert second >= first
