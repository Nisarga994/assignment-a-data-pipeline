import csv
import json
from pathlib import Path

from utils import (
    normalize_header,
    normalize_phone,
    parse_date,
    parse_decimal,
    parse_enum,
)


SCHEMA_DIR = Path("assignment-a-data/schemas")


def load_schema(workflow_id):
    schema_path = SCHEMA_DIR / f"{workflow_id}.json"

    with open(schema_path, "r", encoding="utf-8") as file:
        return json.load(file)


def build_header_map(fields):
    header_map = {}

    for field in fields:
        names = [field["name"]] + field.get("aliases", [])

        for name in names:
            header_map[normalize_header(name)] = field["name"]

    return header_map


def validate_field(value, field):
    field_type = field["type"]

    if field_type == "string":
        return value.strip()

    if field_type == "phone":
        return normalize_phone(value)

    if field_type == "date":
        return parse_date(value)

    if field_type == "decimal":
        return parse_decimal(value)

    if field_type == "enum":
        return parse_enum(value, field["values"])

    raise ValueError("unsupported_field_type")


def process_csv_file(
    csv_path,
    workflow_id,
    batch_id,
    connection,
    phone_hash_func,
    encrypt_func,
):
    schema = load_schema(workflow_id)
    fields = schema["fields"]
    header_map = build_header_map(fields)

    rejected = []
    warnings = []
    
    processed = 0
    duplicates = 0

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames:
            return {
                "processed": 0,
                "rejected": [],
                "warnings": [],
                "duplicates": 0,
            }

        normalized_columns = {
            column: header_map.get(normalize_header(column))
            for column in reader.fieldnames
        }

        for row in reader:
            if not any(str(value or "").strip() for value in row.values()):
                continue

            processed += 1
            row_number = processed

            raw_values = {}

            for column, value in row.items():
                field_name = normalized_columns.get(column)

                if field_name:
                    raw_values[field_name] = str(value or "").strip()

            lead_data = {}
            row_warnings = []
            rejection_reason = None
            canonical_phone = None

            for field in fields:
                name = field["name"]
                value = raw_values.get(name, "")

                if not value:
                    if field.get("required"):
                        rejection_reason = f"missing_required:{name}"
                        break
                    lead_data[name] = None
                    continue

                try:
                    converted = validate_field(value, field)
                    lead_data[name] = converted

                    if name == "phone":
                        canonical_phone = converted

                except ValueError as error:
                    if name == "phone":
                        rejection_reason = "invalid_phone"
                        break

                    lead_data[name] = None
                    row_warnings.append({
                        "field_name": name,
                        "reason": str(error),
                    })

            if rejection_reason:
                rejected.append({
                    "workflow_id": workflow_id,
                    "batch_id": batch_id,
                    "row_number": row_number,
                    "reason": rejection_reason,
                })
                continue

            for field in fields:
                name = field["name"]
                if lead_data.get(name) is None and "default" in field:
                    lead_data[name] = field["default"]

            phone_hash = phone_hash_func(canonical_phone)

            reference_field = next(
                field["name"]
                for field in fields
                if field.get("reference")
            )

            external_ref = lead_data[reference_field]

            existing = connection.execute(
                """
                SELECT lead_id, lead_data
                FROM leads
                WHERE workflow_id = ? AND phone_hash = ?
                """,
                (workflow_id, phone_hash),
            ).fetchone()

            if existing:
              old_data = json.loads(existing["lead_data"])

              for name, value in lead_data.items():
                if value is not None:
                    if name in ("customer_name", "phone"):
                        old_data[name] = encrypt_func(str(value))
                    else:
                        old_data[name] = value

                connection.execute("""
                    UPDATE leads
                    SET lead_data = ?, external_ref = ?,
                        phone_encrypted = ?, customer_name_encrypted = ?,
                        duplicate_count = duplicate_count + 1
                    WHERE lead_id = ?
                """, (
                    json.dumps(old_data),
                    lead_data[reference_field],
                    encrypt_func(canonical_phone),
                    encrypt_func(lead_data["customer_name"]),
                    existing["lead_id"]
                ))

                duplicates += 1

            else:
                connection.execute(
                    """
                    INSERT INTO leads (
                        workflow_id,
                        phone_hash,
                        phone_encrypted,
                        customer_name_encrypted,
                        external_ref,
                        batch_id,
                        lead_data
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        workflow_id,
                        phone_hash,
                        encrypt_func(canonical_phone),
                        encrypt_func(lead_data["customer_name"]),
                        external_ref,
                        batch_id,
                        json.dumps({
    key: (
        encrypt_func(str(value))
        if key in ("customer_name", "phone") and value is not None
        else value
    )
    for key, value in lead_data.items()
}),
                    ),
                )

            for warning in row_warnings:
                warnings.append({
                    "workflow_id": workflow_id,
                    "batch_id": batch_id,
                    "row_number": row_number,
                    **warning,
                })

    connection.commit()

    return {
        "processed": processed,
        "rejected": rejected,
        "warnings": warnings,
        "duplicates": duplicates,
    }