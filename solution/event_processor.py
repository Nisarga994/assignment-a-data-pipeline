import json
from pathlib import Path

from utils import normalize_phone


def load_dispositions():
    """Load valid disposition codes for each workflow."""
    import csv

    path = Path("assignment-a-data/schemas/dispositions.csv")
    dispositions = {}

    with open(path, "r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            workflow = row["workflow_id"]
            dispositions.setdefault(workflow, {})[row["code"]] = {
                "is_terminal": row["is_terminal"].lower() == "true",
                "is_success": row["is_success"].lower() == "true",
            }

    return dispositions


def process_event_file(
    file_path,
    connection,
    phone_hash_func,
    stats,
):
    """Read JSONL events and store valid, unique events."""

    dispositions = load_dispositions()

    with open(file_path, "r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue

            stats["events_total"] += 1

            try:
                event = json.loads(line)

                event_id = event.get("event_id")
                event_type = event.get("event_type")
                workflow_id = event.get("workflow_id")
                occurred_at = event.get("occurred_at")
                call_id = event.get("call_id")

                if not event_id:
                    raise ValueError("missing event_id")

            except (json.JSONDecodeError, ValueError, TypeError):
                stats["malformed_events"] += 1
                continue

            existing = connection.execute(
                "SELECT event_id FROM events WHERE event_id = ?",
                (event_id,),
            ).fetchone()

            if existing:
                stats["duplicate_events_dropped"] += 1
                continue

            payload = event.get("payload") or {}

            if event_type in ("disposition.set", "disposition.override"):
                code = payload.get("disposition_code")

                if code not in dispositions.get(workflow_id, {}):
                    stats["unknown_disposition_events"] += 1
                    continue

            phone = event.get("phone")
            phone_hash = None

            if phone:
                try:
                    canonical_phone = normalize_phone(phone)
                    phone_hash = phone_hash_func(canonical_phone)
                except ValueError:
                    phone_hash = None

            connection.execute(
                """
                INSERT INTO events (
                    event_id,
                    event_type,
                    call_id,
                    workflow_id,
                    phone_hash,
                    occurred_at,
                    payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    event_type,
                    call_id,
                    workflow_id,
                    phone_hash,
                    occurred_at,
                    json.dumps(payload),
                ),
            )

    connection.commit()


def link_events_to_leads(connection):
    """Link events to leads, including events whose leads arrived later."""

    events = connection.execute(
        """
        SELECT event_id, workflow_id, phone_hash, call_id, event_type
        FROM events
        ORDER BY rowid
        """
    ).fetchall()

    call_leads = {}

    # First, link calls using events that contain a phone hash.
    for event in events:
        if event["call_id"] and event["phone_hash"]:
            lead = connection.execute(
                """
                SELECT lead_id
                FROM leads
                WHERE workflow_id = ? AND phone_hash = ?
                """,
                (event["workflow_id"], event["phone_hash"]),
            ).fetchone()

            if lead:
                call_leads[event["call_id"]] = lead["lead_id"]

    # Count events that cannot be linked to a lead.
    orphan_count = 0

    for event in events:
        if not event["call_id"]:
            orphan_count += 1
        elif event["call_id"] not in call_leads:
            orphan_count += 1

    return orphan_count, call_leads