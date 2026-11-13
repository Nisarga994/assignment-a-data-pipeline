import unittest
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "solution"))

from reports import get_effective_disposition


class TestEffectiveDisposition(unittest.TestCase):

    def make_event(self, event_type, timestamp, code):
        return {
            "event_type": event_type,
            "occurred_at": timestamp,
            "payload": json.dumps({"disposition_code": code}),
        }

    def test_latest_set_when_no_override(self):
        events = [
            self.make_event("disposition.set", "2026-10-01T10:00:00Z", "interested"),
            self.make_event("disposition.set", "2026-10-01T11:00:00Z", "not_interested"),
        ]

        self.assertEqual(
            get_effective_disposition(events),
            "not_interested",
        )

    def test_override_takes_priority_over_set(self):
        events = [
            self.make_event("disposition.set", "2026-10-01T12:00:00Z", "interested"),
            self.make_event("disposition.override", "2026-10-01T10:00:00Z", "success"),
        ]

        self.assertEqual(
            get_effective_disposition(events),
            "success",
        )

    def test_latest_override_is_selected(self):
        events = [
            self.make_event("disposition.override", "2026-10-01T10:00:00Z", "interested"),
            self.make_event("disposition.override", "2026-10-01T11:00:00Z", "success"),
        ]

        self.assertEqual(
            get_effective_disposition(events),
            "success",
        )

    def test_no_disposition_returns_none(self):
        self.assertIsNone(get_effective_disposition([]))


class TestLeadBucket(unittest.TestCase):

    def get_bucket(self, total_calls, has_terminal, call_records):
        if total_calls == 0:
            bucket = "yet_to_reach_out"
        elif has_terminal:
            bucket = "completed"
        elif all(call["failed"] for call in call_records):
            bucket = "in_progress_telephony_failed"
        else:
            bucket = "in_progress_dialed"

        return bucket

    def test_no_calls(self):
        self.assertEqual(
            self.get_bucket(0, False, []),
            "yet_to_reach_out",
        )

    def test_terminal_disposition(self):
        self.assertEqual(
            self.get_bucket(1, True, [{"failed": False}]),
            "completed",
        )

    def test_all_calls_failed(self):
        self.assertEqual(
            self.get_bucket(
                2, False,
                [{"failed": True}, {"failed": True}],
            ),
            "in_progress_telephony_failed",
        )

    def test_other_calls_are_dialed(self):
        self.assertEqual(
            self.get_bucket(
                2, False,
                [{"failed": True}, {"failed": False}],
            ),
            "in_progress_dialed",
        )

if __name__ == "__main__":
    unittest.main()