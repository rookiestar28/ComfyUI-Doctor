import pytest
from statistics import StatisticsCalculator
from services.node_health import NodeHealthService

def test_node_health_integration():
    """Verify StatisticsCalculator includes node health metrics."""
    history = [
        {
            "node_info": {"node_class": "KSampler", "node_id": "10"},
            "error_type": "RuntimeError",
            "timestamp": "2026-02-17T12:00:00Z"
        },
        {
            "node_info": {"node_class": "KSampler", "node_id": "11"},
            "error_type": "RuntimeError",
            "timestamp": "2026-02-17T12:05:00Z"
        },
        {
            "node_info": {"node_class": "CheckpointLoaderSimple", "node_id": "5"},
            "error_type": "FileNotFoundError",
            "timestamp": "2026-02-17T12:10:00Z"
        }
    ]
    
    stats = StatisticsCalculator.calculate(history)
    
    assert "node_health" in stats
    health = stats["node_health"]
    assert len(health) >= 2
    
    # KSampler should be first (2 failures)
    assert health[0]["node_class"] == "KSampler"
    assert health[0]["count"] == 2
    
    # CheckpointLoaderSimple second (1 failure)
    assert health[1]["node_class"] == "CheckpointLoaderSimple"
    assert health[1]["count"] == 1

def test_node_health_scoring():
    """Verify heuristic scoring logic directly."""
    # 0 failures -> score 1.0 (implied, though method takes failure count)
    score_0 = NodeHealthService.calculate_health_score(0)
    assert score_0 == 1.0
    
    # 1 failure -> score < 1.0
    score_1 = NodeHealthService.calculate_health_score(1)
    assert score_1 < 1.0
    assert score_1 > 0.8  # Expect high score still
    
    # Many failures -> low score
    score_100 = NodeHealthService.calculate_health_score(100)
    assert score_100 < 0.2
