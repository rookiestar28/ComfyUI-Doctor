"""
Statistics Calculator for ComfyUI-Doctor F4 Dashboard.

Analyzes error history data to generate statisticsFor the dashboard UI.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from collections import Counter


class StatisticsCalculator:
    """
    Calculate statistics from error history for dashboard display.
    
    Features:
    - Pattern frequency counting
    - Category breakdown
    - Top N patterns
    - Time-based filtering
    - Resolution rate tracking
    """
    
    @staticmethod
    def calculate(history: List[Dict[str, Any]], time_range_days: int = 30) -> Dict[str, Any]:
        """
        Calculate comprehensive statistics from error history.
        
        Args:
            history: List of history entry dictionaries (from HistoryStore.get_all())
            time_range_days: Number of days to include (default: 30)
        
        Returns:
            Dictionary with statistics:
            {
                "total_errors": int,
                "pattern_frequency": {pattern_id: count, ...},
                "category_breakdown": {category: count, ...},
                "top_patterns": [{pattern_id, count, category}, ...],  # Top 5
                "resolution_rate": {resolved, unresolved, ignored},
                "trend": {last_24h, last_7d, last_30d}
            }
        """
        if not history:
            return StatisticsCalculator._empty_stats()
        
        # Filter by time range
        cutoff_time = datetime.now() - timedelta(days=time_range_days)
        filtered_history = StatisticsCalculator._filter_by_time(history, cutoff_time)
        
        if not filtered_history:
            return StatisticsCalculator._empty_stats()
        
        # Calculate metrics
        total_errors = len(filtered_history)
        pattern_frequency = StatisticsCalculator._count_patterns(filtered_history)
        category_breakdown = StatisticsCalculator._count_categories(filtered_history)
        top_patterns = StatisticsCalculator._get_top_patterns(filtered_history, limit=5)
        resolution_rate = StatisticsCalculator._calculate_resolution_rate(filtered_history)
        trend = StatisticsCalculator._calculate_trend(history)
        
        return {
            "total_errors": total_errors,
            "pattern_frequency": pattern_frequency,
            "category_breakdown": category_breakdown,
            "top_patterns": top_patterns,
            "resolution_rate": resolution_rate,
            "trend": trend
        }
    
    @staticmethod
    def _filter_by_time(history: List[Dict], cutoff_time: datetime) -> List[Dict]:
        """Filter history entries by timestamp."""
        filtered = []
        for entry in history:
            try:
                # Parse ISO timestamp
                timestamp_str = entry.get("timestamp", "")
                if timestamp_str:
                    # Handle multiple ISO formats
                    entry_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    # Make cutoff_time timezone-aware if entry_time has timezone
                    if entry_time.tzinfo is not None and cutoff_time.tzinfo is None:
                        cutoff_time = cutoff_time.replace(tzinfo=entry_time.tzinfo)
                    
                    if entry_time >= cutoff_time:
                        filtered.append(entry)
            except (ValueError, TypeError):
                # Skip entries with invalid timestamps
                continue
        return filtered
    
    @staticmethod
    def _count_patterns(history: List[Dict]) -> Dict[str, int]:
        """Count frequency of each matched pattern."""
        pattern_ids = [
            entry.get("matched_pattern_id")
            for entry in history
            if entry.get("matched_pattern_id")
        ]
        return dict(Counter(pattern_ids))
    
    @staticmethod
    def _count_categories(history: List[Dict]) -> Dict[str, int]:
        """Count errors by category."""
        categories = [
            entry.get("pattern_category", "generic")
            for entry in history
            if entry.get("pattern_category")
        ]
        return dict(Counter(categories))
    
    @staticmethod
    def _get_top_patterns(history: List[Dict], limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get top N most common error patterns.
        
        Returns:
            List of dicts with {pattern_id, count, category} sorted by frequency
        """
        # Count patterns with category tracking
        pattern_data = {}
        for entry in history:
            pattern_id = entry.get("matched_pattern_id")
            if pattern_id:
                if pattern_id not in pattern_data:
                    pattern_data[pattern_id] = {
                        "pattern_id": pattern_id,
                        "count": 0,
                        "category": entry.get("pattern_category", "generic")
                    }
                pattern_data[pattern_id]["count"] += 1
        
        # Sort by count and return top N
        sorted_patterns = sorted(
            pattern_data.values(),
            key=lambda x: x["count"],
            reverse=True
        )
        return sorted_patterns[:limit]
    
    @staticmethod
    def _calculate_resolution_rate(history: List[Dict]) -> Dict[str, int]:
        """Calculate resolution status breakdown."""
        statuses = [
            entry.get("resolution_status", "unresolved")
            for entry in history
        ]
        status_counts = Counter(statuses)
        return {
            "resolved": status_counts.get("resolved", 0),
            "unresolved": status_counts.get("unresolved", 0),
            "ignored": status_counts.get("ignored", 0)
        }
    
    @staticmethod
    def _calculate_trend(history: List[Dict]) -> Dict[str, int]:
        """Calculate error trends for different time periods."""
        now = datetime.now()
        
        # Define time windows
        windows = {
            "last_24h": now - timedelta(hours=24),
            "last_7d": now - timedelta(days=7),
            "last_30d": now - timedelta(days=30)
        }
        
        counts = {key: 0 for key in windows}
        
        for entry in history:
            try:
                timestamp_str = entry.get("timestamp", "")
                if timestamp_str:
                    entry_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    # Make entry_time timezone-naive for comparison
                    if entry_time.tzinfo is not None:
                        entry_time = entry_time.replace(tzinfo=None)
                    
                    for window_key, window_time in windows.items():
                        if entry_time >= window_time:
                            counts[window_key] += 1
            except (ValueError, TypeError):
                continue
        
        return counts
    
    @staticmethod
    def _empty_stats() -> Dict[str, Any]:
        """Return empty statistics structure."""
        return {
            "total_errors": 0,
            "pattern_frequency": {},
            "category_breakdown": {},
            "top_patterns": [],
            "resolution_rate": {"resolved": 0, "unresolved": 0, "ignored": 0},
            "trend": {"last_24h": 0, "last_7d": 0, "last_30d": 0}
        }
