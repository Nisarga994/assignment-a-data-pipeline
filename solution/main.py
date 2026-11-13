import os
import argparse
import csv
import json
from pathlib import Path

from database import get_connection, create_tables
from lead_processor import process_csv_file
from event_processor import process_event_file, link_events_to_leads
from reports import generate_reports
from utils import (
    hash_phone,
    encrypt_value,
    generate_encryption_key,
)


def get_stats():
    return {
        "lead_rows_total": 0,
        "lead_rows_rejected": 0,
        "rejections_by_reason": {},
        "duplicate_lead_rows_merged": 0,
        "field_warnings": 0,
        "events_total": 0,
        "malformed_events": 0,
        "duplicate_events_dropped": 0,
        "orphan_events": 0,
        "unknown_disposition_events": 0,
        "rejections": [],
    }
def load_stats():
    stats_path = Path("data/pipeline_stats.json")

    if stats_path.exists():
        with open(stats_path, "r", encoding="utf-8") as file:
            return json.load(file)

    return get_stats()


def save_stats(stats):
    stats_path = Path("data/pipeline_stats.json")
    stats_path.parent.mkdir(parents=True, exist_ok=True)

    with open(stats_path, "w", encoding="utf-8") as file:
        json.dump(stats, file, indent=2)


def ingest(drop_path, connection, stats):
    drop_path = Path(drop_path)

    # Process lead CSV files by workflow and batch.
    leads_dir = drop_path / "leads"

    for workflow_dir in sorted(leads_dir.iterdir()):
        if not workflow_dir.is_dir():
            continue

        workflow_id = workflow_dir.name

        for csv_path in sorted(workflow_dir.glob("*.csv")):
            batch_id = csv_path.stem

            result = process_csv_file(
                csv_path,
                workflow_id,
                batch_id,
                connection,
                hash_phone,
                encrypt_value,
            )

            stats["lead_rows_total"] += result["processed"]
            stats["lead_rows_rejected"] += len(result["rejected"])
            stats["duplicate_lead_rows_merged"] += result["duplicates"]
            stats["field_warnings"] += len(result["warnings"])

            stats["rejections"].extend(result["rejected"])

            for rejection in result["rejected"]:
                reason = rejection["reason"]
                stats["rejections_by_reason"][reason] = (
                    stats["rejections_by_reason"].get(reason, 0) + 1
                )

    # Process event JSONL files.
    events_dir = drop_path / "events"
    for jsonl_path in sorted(events_dir.glob("*.jsonl")):
        process_event_file(
            jsonl_path,
            connection,
            hash_phone,
            stats,
        )

    # Recalculate orphan events after processing each drop.
    orphan_count, _ = link_events_to_leads(connection)
    stats["orphan_events"] = orphan_count


def main():
    parser = argparse.ArgumentParser(
        description="Interaction Ledger and Reporting Pipeline"
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    ingest_parser = subparsers.add_parser("ingest")
    ingest_parser.add_argument("drop_path")

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--out", default="reports")

    args = parser.parse_args()

    import os

    key_path = Path("data/.ledger_encryption_key")
    key = os.environ.get("LEDGER_ENCRYPTION_KEY")

    if not key:
        if key_path.exists():
            key = key_path.read_text(encoding="utf-8").strip()
        else:
            key = generate_encryption_key()
            key_path.parent.mkdir(parents=True, exist_ok=True)
            key_path.write_text(key, encoding="utf-8")

        os.environ["LEDGER_ENCRYPTION_KEY"] = key

    connection = get_connection()
    create_tables(connection)

    stats = load_stats()

    if args.command == "ingest":
        ingest(args.drop_path, connection, stats)
        save_stats(stats)
        print("Ingestion completed.")

    elif args.command == "report":
        generate_reports(connection, args.out, stats)
        print("Reports generated in:", args.out)

    connection.close()


if __name__ == "__main__":
    main()