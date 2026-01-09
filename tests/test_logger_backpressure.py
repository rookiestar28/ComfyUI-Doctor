from logger import DroppingQueue


def test_drop_non_priority_when_full():
    queue = DroppingQueue(maxsize=1)
    assert queue.put_nowait("first", priority=False) is True
    assert queue.put_nowait("second", priority=False) is False

    stats = queue.get_stats()
    assert stats["queue_dropped_total"] == 1
    assert stats["queue_dropped_non_priority"] == 1


def test_priority_eviction_prefers_non_priority():
    queue = DroppingQueue(maxsize=2)
    assert queue.put_nowait("first", priority=False) is True
    assert queue.put_nowait("second", priority=False) is True
    assert queue.put_nowait("priority", priority=True) is True

    stats = queue.get_stats()
    assert stats["queue_dropped_total"] == 1
    assert stats["queue_dropped_oldest"] == 1

    items = [queue.get()[1], queue.get()[1]]
    assert "priority" in items


def test_priority_drop_when_queue_full_of_priority():
    queue = DroppingQueue(maxsize=1)
    assert queue.put_nowait("first", priority=True) is True
    assert queue.put_nowait("second", priority=True) is True

    stats = queue.get_stats()
    assert stats["queue_dropped_total"] == 1
    assert stats["queue_dropped_priority"] == 1
    assert stats["queue_dropped_oldest"] == 1
