"""
F4 Statistics Dashboard - Backend Unit Tests
Tests for StatisticsCalculator class in statistics.py
"""
import pytest
from datetime import datetime, timedelta, timezone
from statistics import StatisticsCalculator


class TestStatisticsCalculator:
    """Tests for StatisticsCalculator.calculate() method"""
    
    # ========================================
    # Test: Empty History
    # ========================================
    
    def test_empty_history_returns_zero_stats(self):
        """Empty history should return all zeros"""
        result = StatisticsCalculator.calculate([], 30)
        
        assert result["total_errors"] == 0
        assert result["pattern_frequency"] == {}
        assert result["category_breakdown"] == {}
        assert result["top_patterns"] == []
        assert result["resolution_rate"]["resolved"] == 0
        assert result["resolution_rate"]["unresolved"] == 0
        assert result["resolution_rate"]["ignored"] == 0
        assert result["trend"]["last_24h"] == 0
        assert result["trend"]["last_7d"] == 0
        assert result["trend"]["last_30d"] == 0
    
    # ========================================
    # Test: Pattern Frequency
    # ========================================
    
    def test_pattern_frequency_counts_correctly(self):
        """Pattern frequency should count occurrences correctly"""
        history = [
            self._make_entry("cuda_oom_classic", "memory"),
            self._make_entry("cuda_oom_classic", "memory"),
            self._make_entry("missing_module", "framework"),
            self._make_entry("cuda_oom_classic", "memory"),
        ]
        
        result = StatisticsCalculator.calculate(history, 30)
        
        assert result["pattern_frequency"]["cuda_oom_classic"] == 3
        assert result["pattern_frequency"]["missing_module"] == 1
        assert result["total_errors"] == 4

    def test_repeat_count_is_weighted_in_totals(self):
        """repeat_count should contribute to totals and counts."""
        now = datetime.now(timezone.utc)
        history = [
            {
                "timestamp": (now - timedelta(minutes=5)).isoformat(),
                "matched_pattern_id": "a",
                "pattern_category": "memory",
                "resolution_status": "unresolved",
                "repeat_count": 3,
                "first_seen": (now - timedelta(minutes=5)).isoformat(),
                "last_seen": (now - timedelta(minutes=4)).isoformat(),
            },
            {
                "timestamp": (now - timedelta(minutes=3)).isoformat(),
                "matched_pattern_id": "b",
                "pattern_category": "workflow",
                "resolution_status": "resolved",
                "repeat_count": 2,
                "first_seen": (now - timedelta(minutes=3)).isoformat(),
                "last_seen": (now - timedelta(minutes=3)).isoformat(),
            },
        ]

        result = StatisticsCalculator.calculate(history, 30)
        assert result["total_errors"] == 5
        assert result["pattern_frequency"]["a"] == 3
        assert result["pattern_frequency"]["b"] == 2
        assert result["category_breakdown"]["memory"] == 3
        assert result["category_breakdown"]["workflow"] == 2
        assert result["resolution_rate"]["unresolved"] == 3
        assert result["resolution_rate"]["resolved"] == 2
    
    def test_pattern_frequency_skips_none_pattern(self):
        """Entries without pattern_id should be skipped in frequency count"""
        history = [
            self._make_entry(None, None),
            self._make_entry("cuda_oom", "memory"),
        ]
        
        result = StatisticsCalculator.calculate(history, 30)
        
        # None pattern is skipped, only cuda_oom is counted
        assert "unknown" not in result["pattern_frequency"]
        assert result["pattern_frequency"]["cuda_oom"] == 1
        # But total_errors still includes all entries in time range
        assert result["total_errors"] == 2
    
    # ========================================
    # Test: Category Breakdown
    # ========================================
    
    def test_category_breakdown_counts_correctly(self):
        """Category breakdown should group by category"""
        history = [
            self._make_entry("cuda_oom", "memory"),
            self._make_entry("vram_full", "memory"),
            self._make_entry("model_not_found", "model_loading"),
            self._make_entry("connection_error", "workflow"),
        ]
        
        result = StatisticsCalculator.calculate(history, 30)
        
        assert result["category_breakdown"]["memory"] == 2
        assert result["category_breakdown"]["model_loading"] == 1
        assert result["category_breakdown"]["workflow"] == 1
    
    def test_category_breakdown_skips_none_category(self):
        """Entries without category should be skipped in breakdown"""
        history = [
            self._make_entry("some_error", None),
            self._make_entry("other_error", "memory"),
        ]
        
        result = StatisticsCalculator.calculate(history, 30)
        
        # None category is skipped, not counted as generic
        assert "generic" not in result["category_breakdown"]
        assert result["category_breakdown"]["memory"] == 1
    
    # ========================================
    # Test: Top Patterns
    # ========================================
    
    def test_top_patterns_returns_top_5(self):
        """Should return top 5 most frequent patterns"""
        history = [
            *[self._make_entry("pattern_a", "memory")] * 10,
            *[self._make_entry("pattern_b", "workflow")] * 8,
            *[self._make_entry("pattern_c", "model_loading")] * 6,
            *[self._make_entry("pattern_d", "framework")] * 4,
            *[self._make_entry("pattern_e", "generic")] * 2,
            *[self._make_entry("pattern_f", "memory")] * 1,  # Should NOT be in top 5
        ]
        
        result = StatisticsCalculator.calculate(history, 30)
        
        assert len(result["top_patterns"]) == 5
        assert result["top_patterns"][0]["pattern_id"] == "pattern_a"
        assert result["top_patterns"][0]["count"] == 10
        assert result["top_patterns"][1]["pattern_id"] == "pattern_b"
        assert result["top_patterns"][4]["pattern_id"] == "pattern_e"
    
    def test_top_patterns_sorted_by_count_descending(self):
        """Top patterns should be sorted by count descending"""
        history = [
            self._make_entry("low", "memory"),
            *[self._make_entry("high", "memory")] * 5,
            *[self._make_entry("medium", "memory")] * 3,
        ]
        
        result = StatisticsCalculator.calculate(history, 30)
        
        counts = [p["count"] for p in result["top_patterns"]]
        assert counts == sorted(counts, reverse=True)
    
    # ========================================
    # Test: Resolution Rate
    # ========================================
    
    def test_resolution_rate_counts_all_statuses(self):
        """Resolution rate should count all three statuses"""
        history = [
            self._make_entry("a", "memory", resolution_status="resolved"),
            self._make_entry("b", "memory", resolution_status="resolved"),
            self._make_entry("c", "memory", resolution_status="unresolved"),
            self._make_entry("d", "memory", resolution_status="ignored"),
        ]
        
        result = StatisticsCalculator.calculate(history, 30)
        
        assert result["resolution_rate"]["resolved"] == 2
        assert result["resolution_rate"]["unresolved"] == 1
        assert result["resolution_rate"]["ignored"] == 1
    
    def test_resolution_rate_default_is_unresolved(self):
        """Missing resolution_status should default to unresolved"""
        history = [
            {"timestamp": self._recent_timestamp(), "matched_pattern_id": "a"},
        ]
        
        result = StatisticsCalculator.calculate(history, 30)
        
        assert result["resolution_rate"]["unresolved"] == 1
    
    # ========================================
    # Test: Trend Calculation
    # ========================================
    
    def test_trend_last_24h_counts_recent_errors(self):
        """Trend should count errors in last 24 hours"""
        now = datetime.now(timezone.utc)
        history = [
            self._make_entry("a", "memory", timestamp=now - timedelta(hours=1)),
            self._make_entry("b", "memory", timestamp=now - timedelta(hours=12)),
            self._make_entry("c", "memory", timestamp=now - timedelta(hours=25)),  # Outside 24h
        ]
        
        result = StatisticsCalculator.calculate(history, 30)
        
        assert result["trend"]["last_24h"] == 2
    
    def test_trend_last_7d_counts_weekly_errors(self):
        """Trend should count errors in last 7 days"""
        now = datetime.now(timezone.utc)
        history = [
            self._make_entry("a", "memory", timestamp=now - timedelta(days=1)),
            self._make_entry("b", "memory", timestamp=now - timedelta(days=5)),
            self._make_entry("c", "memory", timestamp=now - timedelta(days=8)),  # Outside 7d
        ]
        
        result = StatisticsCalculator.calculate(history, 30)
        
        assert result["trend"]["last_7d"] == 2
    
    def test_trend_last_30d_equals_total_within_range(self):
        """Trend 30d should equal total if all within 30 days"""
        now = datetime.now(timezone.utc)
        history = [
            self._make_entry("a", "memory", timestamp=now - timedelta(days=1)),
            self._make_entry("b", "memory", timestamp=now - timedelta(days=15)),
            self._make_entry("c", "memory", timestamp=now - timedelta(days=29)),
        ]
        
        result = StatisticsCalculator.calculate(history, 30)
        
        assert result["trend"]["last_30d"] == 3
        assert result["total_errors"] == 3
    
    # ========================================
    # Test: Time Range Filtering
    # ========================================
    
    def test_time_range_filters_old_entries(self):
        """Entries older than time_range_days should be excluded"""
        now = datetime.now(timezone.utc)
        history = [
            self._make_entry("a", "memory", timestamp=now - timedelta(days=5)),
            self._make_entry("b", "memory", timestamp=now - timedelta(days=15)),  # Outside 7d
        ]
        
        result = StatisticsCalculator.calculate(history, 7)
        
        assert result["total_errors"] == 1
        assert result["pattern_frequency"]["a"] == 1
        assert "b" not in result["pattern_frequency"]
    
    def test_custom_time_range(self):
        """Custom time range should work correctly"""
        now = datetime.now(timezone.utc)
        history = [
            self._make_entry("a", "memory", timestamp=now - timedelta(days=2)),
            self._make_entry("b", "memory", timestamp=now - timedelta(days=4)),  # Outside 3d
        ]
        
        result = StatisticsCalculator.calculate(history, 3)
        
        assert result["total_errors"] == 1
    
    # ========================================
    # Test: Edge Cases
    # ========================================
    
    def test_handles_malformed_timestamp(self):
        """Should handle malformed timestamps gracefully"""
        history = [
            {"timestamp": "invalid-date", "matched_pattern_id": "a"},
            self._make_entry("b", "memory"),
        ]
        
        result = StatisticsCalculator.calculate(history, 30)
        
        # Should still process valid entries
        assert result["total_errors"] >= 1
    
    def test_handles_dict_with_missing_fields(self):
        """Should handle dicts with missing fields"""
        history = [
            {"timestamp": self._recent_timestamp()},  # No pattern_id
            {"matched_pattern_id": "test"},  # No timestamp
        ]
        
        # Should not raise exception
        result = StatisticsCalculator.calculate(history, 30)
        assert isinstance(result, dict)
    
    # ========================================
    # Helper Methods
    # ========================================
    
    def _make_entry(
        self, 
        pattern_id: str, 
        category: str, 
        timestamp: datetime = None,
        resolution_status: str = "unresolved"
    ) -> dict:
        """Create a test history entry"""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc) - timedelta(hours=1)
        
        return {
            "timestamp": timestamp.isoformat(),
            "matched_pattern_id": pattern_id,
            "pattern_category": category,
            "resolution_status": resolution_status,
        }
    
    def _recent_timestamp(self) -> str:
        """Return a recent timestamp string"""
        return (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()


class TestStatisticsCalculatorHelpers:
    """Tests for internal helper methods"""
    
    def test_empty_stats_structure(self):
        """_empty_stats should return correct structure"""
        result = StatisticsCalculator._empty_stats()
        
        assert "total_errors" in result
        assert "pattern_frequency" in result
        assert "category_breakdown" in result
        assert "top_patterns" in result
        assert "resolution_rate" in result
        assert "trend" in result
