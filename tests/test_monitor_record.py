from __future__ import annotations

import unittest

from monitor.record import summarize_metrics, summary_deltas, validate_interval


class MonitorRecordTestCase(unittest.TestCase):
    def test_summarize_lightweight_metrics_extracts_quota_total_and_native_state(self) -> None:
        metrics = {
            "mode": "summary",
            "event_loop_lag": {
                "enabled": True,
                "stalls_20ms": 17,
                "stalls_50ms": 8,
                "stalls_100ms": 3,
                "stalls_250ms": 1,
                "max_lag_ms": 251.2,
            },
            "process_memory": {
                "rss_mib": 401.25,
                "swap_mib": 98.5,
                "rss_plus_swap_mib": 499.75,
                "peak_rss_mib": 412.5,
                "allocated_blocks": 123456,
            },
            "state": {
                "users": 120,
                "user_perf_entries": 245,
                "user_puzzle_perf_entries": 18,
                "games": 8,
                "tournaments": 14,
                "finished_tournaments": 9,
                "tournament_remove_tasks": 8,
                "tournament_user_references": 210,
                "finished_tournament_user_references": 180,
                "tournaments_with_active_sockets": 2,
                "tournament_active_sockets": 3,
                "active_tasks": 17,
                "catalogued_variants": 31,
                "pyffish_variants": 151,
                "catalogued_payload_bytes": 8192,
                "fishnet_works": 2,
                "fishnet_payload_bytes": 4096,
            },
            "registered": {
                "registered_total": 90,
                "registered_cache_only": 70,
                "registered_cache_evictions": 12,
            },
            "anonymous": {"anon_total": 25},
            "streams": {
                "lobby_websockets": 4,
                "game_websockets": 5,
                "game_sse": 2,
                "game_sse_queued_messages": 37,
                "game_sse_max_queue": 29,
                "game_sse_full_queues": 1,
                "sse_queued_messages": 41,
                "sse_max_queue": 29,
                "sse_full_queues": 1,
                "bot_event_queued_messages": 3,
                "bot_game_queued_messages": 4,
                "bot_max_queue": 3,
            },
            "caches": [
                {"name": "one", "currsize": 12},
                {"name": "two", "currsize": 30},
            ],
        }

        summary = summarize_metrics(metrics)

        self.assertEqual(summary["rss_plus_swap_mib"], 499.75)
        self.assertEqual(summary["loop_lag_stalls_100ms"], 3)
        self.assertEqual(summary["loop_lag_max_ms"], 251.2)
        self.assertEqual(summary["swap_mib"], 98.5)
        self.assertEqual(summary["allocated_blocks"], 123456)
        self.assertEqual(summary["user_perf_entries"], 245)
        self.assertEqual(summary["user_puzzle_perf_entries"], 18)
        self.assertEqual(summary["registered_cache_evictions"], 12)
        self.assertEqual(summary["finished_tournaments"], 9)
        self.assertEqual(summary["tournament_remove_tasks"], 8)
        self.assertEqual(summary["finished_tournament_user_references"], 180)
        self.assertEqual(summary["tournaments_with_active_sockets"], 2)
        self.assertEqual(summary["tournament_active_sockets"], 3)
        self.assertEqual(summary["tasks"], 17)
        self.assertEqual(summary["streams"], 11)
        self.assertEqual(summary["game_sse"], 2)
        self.assertEqual(summary["game_sse_queued_messages"], 37)
        self.assertEqual(summary["game_sse_max_queue"], 29)
        self.assertEqual(summary["game_sse_full_queues"], 1)
        self.assertEqual(summary["sse_queued_messages"], 41)
        self.assertEqual(summary["sse_max_queue"], 29)
        self.assertEqual(summary["bot_event_queued_messages"], 3)
        self.assertEqual(summary["bot_game_queued_messages"], 4)
        self.assertEqual(summary["bot_max_queue"], 3)
        self.assertEqual(summary["pyffish_variants"], 151)
        self.assertEqual(summary["catalogued_payload_bytes"], 8192)
        self.assertEqual(summary["cache_entries"], 42)

    def test_summarize_metrics_extracts_growth_indicators(self) -> None:
        metrics = {
            "object_counts": {"tasks": 17, "queues": 3, "caches": 42},
            "object_details": {
                "process_memory": [{"rss_mib": 401.25, "peak_rss_mib": 412.5}],
                "state": [
                    {
                        "users": 120,
                        "games": 8,
                        "catalogued_variants": 31,
                        "fishnet_works": 2,
                        "fishnet_payload_bytes": 4096,
                    }
                ],
                "registered_summary": [
                    {
                        "registered_total": 90,
                        "registered_cache_only": 70,
                    }
                ],
                "anon_summary": [{"anon_total": 25}],
                "streams": [
                    {
                        "lobby_websockets": 4,
                        "game_websockets": 5,
                        "tournament_websockets": 1,
                        "simul_websockets": 0,
                        "game_sse": 2,
                        "game_sse_queued_messages": 37,
                        "game_sse_max_queue": 29,
                        "game_sse_full_queues": 1,
                        "sse_queued_messages": 41,
                        "sse_max_queue": 29,
                        "sse_full_queues": 1,
                        "bot_event_queued_messages": 3,
                        "bot_game_queued_messages": 4,
                        "bot_max_queue": 3,
                        "invite_sse": 1,
                        "notify_sse": 3,
                        "inbox_sse": 0,
                        "challenge_sse": 1,
                        "active_bot_game_streams": 2,
                    }
                ],
            },
        }

        summary = summarize_metrics(metrics)

        self.assertEqual(summary["rss_mib"], 401.25)
        self.assertEqual(summary["users"], 120)
        self.assertEqual(summary["registered_cache_only"], 70)
        self.assertEqual(summary["streams"], 19)
        self.assertEqual(summary["game_sse_queued_messages"], 37)
        self.assertEqual(summary["game_sse_max_queue"], 29)
        self.assertEqual(summary["game_sse_full_queues"], 1)
        self.assertEqual(summary["sse_queued_messages"], 41)
        self.assertEqual(summary["sse_max_queue"], 29)
        self.assertEqual(summary["bot_event_queued_messages"], 3)
        self.assertEqual(summary["bot_game_queued_messages"], 4)
        self.assertEqual(summary["bot_max_queue"], 3)
        self.assertEqual(summary["cache_entries"], 42)

    def test_summary_deltas_compare_first_and_last_samples(self) -> None:
        first = summarize_metrics(
            {
                "object_details": {
                    "process_memory": [{"rss_mib": 350.0}],
                    "state": [{"users": 100}],
                }
            }
        )
        last = summarize_metrics(
            {
                "object_details": {
                    "process_memory": [{"rss_mib": 362.5}],
                    "state": [{"users": 125}],
                }
            }
        )

        deltas = summary_deltas(first, last)

        self.assertEqual(deltas["rss_mib"], 12.5)
        self.assertEqual(deltas["users"], 25)

    def test_production_interval_rejects_frequent_polling(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least 60"):
            validate_interval("https://www.pychess.org/metrics", 5)

        validate_interval("https://www.pychess.org/metrics", 60)
        validate_interval("http://127.0.0.1:8080/metrics", 1)


if __name__ == "__main__":
    unittest.main()
