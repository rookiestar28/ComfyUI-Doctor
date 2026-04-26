"""
Statistics Calculator for ComfyUI-Doctor F4 Dashboard.

Analyzes error history data to generate statisticsFor the dashboard UI.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from collections import Counter
try:
    from .services.node_health import NodeHealthService
    from .services.time_utils import ensure_utc, parse_utc_timestamp, utc_now
except ImportError as import_error:
    from import_compat import ensure_absolute_import_fallback_allowed
    ensure_absolute_import_fallback_allowed(import_error)
    from services.node_health import NodeHealthService
    from services.time_utils import ensure_utc, parse_utc_timestamp, utc_now



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
        cutoff_time = utc_now() - timedelta(days=time_range_days)
        filtered_history = StatisticsCalculator._filter_by_time(history, cutoff_time)
        
        if not filtered_history:
            return StatisticsCalculator._empty_stats()
        
        # Calculate metrics
        def weight(entry: Dict[str, Any]) -> int:
            try:
                return int(entry.get("repeat_count", 1) or 1)
            except Exception:
                return 1

        total_errors = sum(weight(e) for e in filtered_history)
        pattern_frequency = StatisticsCalculator._count_patterns(filtered_history)
        category_breakdown = StatisticsCalculator._count_categories(filtered_history)
        top_patterns = StatisticsCalculator._get_top_patterns(filtered_history, limit=5)
        resolution_rate = StatisticsCalculator._calculate_resolution_rate(filtered_history)
        trend = StatisticsCalculator._calculate_trend(history)
        
        # T5: Node Health Scoring
        node_health = NodeHealthService.calculate_node_failures(filtered_history)
        
        return {
            "total_errors": total_errors,
            "pattern_frequency": pattern_frequency,
            "category_breakdown": category_breakdown,
            "top_patterns": top_patterns,
            "node_health": node_health,
            "resolution_rate": resolution_rate,
            "trend": trend
        }
    
    @staticmethod
    def _filter_by_time(history: List[Dict], cutoff_time: datetime) -> List[Dict]:
        """Filter history entries by timestamp."""
        filtered = []
        normalized_cutoff = ensure_utc(cutoff_time)
        for entry in history:
            timestamp_str = entry.get("last_seen") or entry.get("timestamp", "")
            entry_time = parse_utc_timestamp(timestamp_str)
            if entry_time and entry_time >= normalized_cutoff:
                filtered.append(entry)
        return filtered
    
    @staticmethod
    def _count_patterns(history: List[Dict]) -> Dict[str, int]:
        """Count frequency of each matched pattern."""
        counts: Dict[str, int] = {}
        for entry in history:
            pattern_id = entry.get("matched_pattern_id")
            if not pattern_id:
                continue
            try:
                w = int(entry.get("repeat_count", 1) or 1)
            except Exception:
                w = 1
            counts[pattern_id] = counts.get(pattern_id, 0) + w
        return counts
    
    @staticmethod
    def _count_categories(history: List[Dict]) -> Dict[str, int]:
        """Count errors by category."""
        counts: Dict[str, int] = {}
        for entry in history:
            category = entry.get("pattern_category", "generic")
            if not category:
                continue
            try:
                w = int(entry.get("repeat_count", 1) or 1)
            except Exception:
                w = 1
            counts[category] = counts.get(category, 0) + w
        return counts
    
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
                try:
                    w = int(entry.get("repeat_count", 1) or 1)
                except Exception:
                    w = 1
                pattern_data[pattern_id]["count"] += w
        
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
        counts = {"resolved": 0, "unresolved": 0, "ignored": 0}
        for entry in history:
            status = entry.get("resolution_status", "unresolved") or "unresolved"
            try:
                w = int(entry.get("repeat_count", 1) or 1)
            except Exception:
                w = 1
            if status not in counts:
                status = "unresolved"
            counts[status] += w
        return counts
    
    @staticmethod
    def _calculate_trend(history: List[Dict]) -> Dict[str, int]:
        """Calculate error trends for different time periods."""
        now = utc_now()

        # Define time windows
        windows = {
            "last_24h": now - timedelta(hours=24),
            "last_7d": now - timedelta(days=7),
            "last_30d": now - timedelta(days=30)
        }
        
        counts = {key: 0 for key in windows}
        
        for entry in history:
            timestamp_str = entry.get("last_seen") or entry.get("timestamp", "")
            entry_time = parse_utc_timestamp(timestamp_str)
            if not entry_time:
                continue

            try:
                w = int(entry.get("repeat_count", 1) or 1)
            except Exception:
                w = 1

            for window_key, window_time in windows.items():
                if entry_time >= window_time:
                    counts[window_key] += w
        
        return counts
    
    @staticmethod
    def _empty_stats() -> Dict[str, Any]:
        """Return empty statistics structure."""
        return {
            "total_errors": 0,
            "pattern_frequency": {},
            "category_breakdown": {},
            "top_patterns": [],
            "node_health": [],
            "resolution_rate": {"resolved": 0, "unresolved": 0, "ignored": 0},
            "trend": {"last_24h": 0, "last_7d": 0, "last_30d": 0}
        }
