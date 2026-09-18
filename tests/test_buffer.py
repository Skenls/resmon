from backend.buffer import MetricsBuffer

def test_buffer_maxlen():
    buf = MetricsBuffer(maxlen=3)
    buf.append({"t": 1})
    buf.append({"t": 2})
    buf.append({"t": 3})
    buf.append({"t": 4})
    history = buf.get_history()
    assert len(history) == 3
    assert history[0]["t"] == 2
    assert history[1]["t"] == 3
    assert history[2]["t"] == 4

def test_buffer_latest_and_clear():
    buf = MetricsBuffer(maxlen=5)
    assert buf.get_latest() is None
    assert buf.get_history() == []

    buf.append({"val": 42})
    assert buf.get_latest() == {"val": 42}
    assert len(buf) == 1

    buf.clear()
    assert len(buf) == 0
    assert buf.get_latest() is None
