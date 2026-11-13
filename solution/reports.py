import csv
import json
from pathlib import Path
from utils import decrypt_value
from datetime import datetime, timezone, timedelta


IST = timezone(timedelta(hours=5, minutes=30))


def to_ist(value):
    """Convert a timestamp to an IST datetime."""
    if not value:
        return None

    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=IST)

    return timestamp.astimezone(IST)


def write_csv(path, headers, rows):
    """Write a CSV report with a fixed header."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def load_dispositions():
    """Load disposition definitions."""
    dispositions = {}

    with open(
        "assignment-a-data/schemas/dispositions.csv",
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        for row in csv.DictReader(file):
            dispositions.setdefault(row["workflow_id"], {})[
                row["code"]
            ] = {
                "is_terminal": row["is_terminal"].lower() == "true",
                "is_success": row["is_success"].lower() == "true",
            }

    return dispositions


def get_effective_disposition(events):
    """Return the latest override, or latest set event."""
    overrides = [
        event for event in events
        if event["event_type"] == "disposition.override"
    ]

    sets = [
        event for event in events
        if event["event_type"] == "disposition.set"
    ]

    candidates = overrides if overrides else sets

    if not candidates:
        return None

    latest = max(
        candidates,
        key=lambda event: to_ist(event["occurred_at"]),
    )

    return json.loads(latest["payload"]).get("disposition_code")


def save_data_quality(path, stats):
    """Write only the required data-quality fields."""
    required_keys = [
        "lead_rows_total",
        "lead_rows_rejected",
        "rejections_by_reason",
        "duplicate_lead_rows_merged",
        "field_warnings",
        "events_total",
        "malformed_events",
        "duplicate_events_dropped",
        "orphan_events",
        "unknown_disposition_events",
    ]

    report = {key: stats.get(key, 0) for key in required_keys}

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)


def generate_reports(connection, output_dir, stats):
    """Generate the five assignment reports."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    dispositions = load_dispositions()

    leads = connection.execute(
        "SELECT * FROM leads ORDER BY workflow_id, external_ref"
    ).fetchall()

    events = connection.execute(
        "SELECT * FROM events ORDER BY occurred_at"
    ).fetchall()

    lead_events = {}
    call_events = {}

    # Associate events with leads through phone hashes.
    for event in events:
        if event["phone_hash"]:
            lead = connection.execute(
                """
                SELECT lead_id
                FROM leads
                WHERE workflow_id = ? AND phone_hash = ?
                """,
                (event["workflow_id"], event["phone_hash"]),
            ).fetchone()

            if lead:
                lead_events.setdefault(lead["lead_id"], []).append(event)

                if event["call_id"]:
                    call_events.setdefault(event["call_id"], []).append(event)

    # Link events without phone numbers through their call ID.
    for event in events:
        if event["phone_hash"] or not event["call_id"]:
            continue

        related = call_events.get(event["call_id"], [])

        if related:
            lead_id = connection.execute(
                """
                SELECT lead_id
                FROM leads
                WHERE workflow_id = ?
                  AND phone_hash = ?
                """,
                (event["workflow_id"], related[0]["phone_hash"]),
            ).fetchone()

            if lead_id:
                lead_events.setdefault(
                    lead_id["lead_id"], []
                ).append(event)

    batch_counts = {}
    daily_counts = {}
    lead_rows = []

    for lead in leads:
        lead_id = lead["lead_id"]
        workflow = lead["workflow_id"]
        batch = lead["batch_id"]

        lead_data = json.loads(lead["lead_data"])
        events_for_lead = lead_events.get(lead_id, [])

        calls = {}

        for event in events_for_lead:
            if not event["call_id"]:
                continue

            calls.setdefault(event["call_id"], []).append(event)

        call_records = []

        for call_id, call_event_list in calls.items():
            initiated = [
                e for e in call_event_list
                if e["event_type"] == "call.initiated"
            ]

            if not initiated:
                continue

            start_event = min(
                initiated,
                key=lambda e: to_ist(e["occurred_at"]),
            )

            connected = any(
                e["event_type"] == "call.connected"
                for e in call_event_list
            )

            failed = any(
                e["event_type"] == "call.telephony_failed"
                for e in call_event_list
            )

            disposition = get_effective_disposition(
                call_event_list
            )

            call_records.append({
                "call_id": call_id,
                "started": to_ist(start_event["occurred_at"]),
                "connected": connected,
                "failed": failed,
                "disposition": disposition,
            })

        total_calls = len(call_records)
        connected_calls = sum(
            call["connected"] for call in call_records
        )

        has_terminal = any(
            call["disposition"] in dispositions.get(workflow, {})
            and dispositions[workflow][
                call["disposition"]
            ]["is_terminal"]
            for call in call_records
        )

        if total_calls == 0:
            bucket = "yet_to_reach_out"
        elif has_terminal:
            bucket = "completed"
        elif all(call["failed"] for call in call_records):
            bucket = "in_progress_telephony_failed"
        else:
            bucket = "in_progress_dialed"

        batch_key = (workflow, batch)
        counts = batch_counts.setdefault(
            batch_key,
            {
                "total_leads": 0,
                "yet_to_reach_out": 0,
                "in_progress_telephony_failed": 0,
                "in_progress_dialed": 0,
                "completed": 0,
            },
        )

        counts["total_leads"] += 1
        counts[bucket] += 1

        for call in call_records:
            date = call["started"].date().isoformat()
            daily_key = (workflow, date)

            daily = daily_counts.setdefault(
                daily_key,
                {
                    "total_calls": 0,
                    "connected_calls": 0,
                    "success_leads": set(),
                },
            )

            daily["total_calls"] += 1
            daily["connected_calls"] += int(call["connected"])

            code = call["disposition"]

            if (
                code in dispositions.get(workflow, {})
                and dispositions[workflow][code]["is_success"]
            ):
                daily["success_leads"].add(lead_id)

        last_call = max(
            call_records,
            key=lambda call: call["started"],
        ) if call_records else None

        current_disposition = None

        if last_call:
            calls_with_disposition = [
                call for call in call_records
                if call["disposition"]
            ]

            if calls_with_disposition:
                current_disposition = max(
                    calls_with_disposition,
                    key=lambda call: call["started"],
                )["disposition"]

        ever_success = any(
            call["disposition"] in dispositions.get(workflow, {})
            and dispositions[workflow][
                call["disposition"]
            ]["is_success"]
            for call in call_records
        )

        # The phone is stored encrypted; only use the encrypted
        # phone's last four digits after decryption in the next step.
        lead_rows.append({
            "workflow_id": workflow,
            "external_ref": lead["external_ref"],
            "batch_id": batch,
            "phone_masked": "+91******" + decrypt_value(lead["phone_encrypted"])[-4:],
            "bucket": bucket,
            "total_calls": total_calls,
            "connected_calls": connected_calls,
            "last_call_at": (
                last_call["started"].isoformat()
                if last_call else ""
            ),
            "current_disposition": current_disposition or "",
            "ever_success": str(ever_success).lower(),
        })

    batch_rows = []

    for (workflow, batch), counts in sorted(batch_counts.items()):
        batch_rows.append({
            "workflow_id": workflow,
            "batch_id": batch,
            **counts,
        })

    daily_rows = []

    for (workflow, date), counts in sorted(daily_counts.items()):
        total = counts["total_calls"]
        connected = counts["connected_calls"]

        daily_rows.append({
            "workflow_id": workflow,
            "date": date,
            "total_calls": total,
            "connected_calls": connected,
            "connectivity_rate": f"{connected / total:.4f}",
            "success_leads": len(counts["success_leads"]),
        })

    write_csv(
        output_dir / "batch_summary.csv",
        [
            "workflow_id", "batch_id", "total_leads",
            "yet_to_reach_out", "in_progress_telephony_failed",
            "in_progress_dialed", "completed",
        ],
        batch_rows,
    )

    write_csv(
        output_dir / "daily_overview.csv",
        [
            "workflow_id", "date", "total_calls",
            "connected_calls", "connectivity_rate",
            "success_leads",
        ],
        daily_rows,
    )

    write_csv(
        output_dir / "lead_report.csv",
        [
            "workflow_id", "external_ref", "batch_id",
            "phone_masked", "bucket", "total_calls",
            "connected_calls", "last_call_at",
            "current_disposition", "ever_success",
        ],
        lead_rows,
    )

    write_csv(
        output_dir / "rejections.csv",
        [
            "workflow_id", "batch_id", "row_number", "reason"
        ],
        stats.get("rejections", []),
    )

    save_data_quality(
        output_dir / "data_quality.json",
        stats,
    )