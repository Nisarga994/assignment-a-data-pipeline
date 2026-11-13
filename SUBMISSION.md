# Submission

> Replace everything in _italics_. Be concise: bullet points are fine. We read every word.

## Candidate
- **Name:** _Nisarga N
- **Assignment chosen:** _A (Data)
- **Time spent (honest estimate):** 9 hours

## How to run
```bash
Run these commands from the repository root on a clean clone.
# Install dependencies
python -m pip install -r requirements.txt

# Ingest the first data drop
python solution/main.py ingest data/drop_1

# Ingest the second data drop
python solution/main.py ingest data/drop_2

# Generate all five reports
python solution/main.py report

# Run tests
python -m unittest discover -s tests -v
Python 3.11 or later is recommended.
```

## Design
The solution is organised into separate Python modules:
main.py: command-line interface and pipeline orchestration.
database.py: SQLite database connection and table creation.
lead_processor.py: CSV ingestion, header matching, validation, normalisation, rejection and duplicate handling.
event_processor.py: JSONL event ingestion, deduplication and event-to-lead linking.
reports.py: generation of the five required output files.
utils.py: shared functions for phone normalisation, date parsing, decimal parsing, enum handling, encryption and masking.
## Decisions & assumptions
_Decision                                  Why                                         Alternative considered
Use SQLite          Simple persistent database suitable for this assignment                 PostgreSQL
Use canonical 
Indian phone 
numbers            Ensures consistent lead identity across different phone formats    Store original phone formats
Use a keyed phone 
hash for identity 
matching           Avoids storing searchable phone numbers in plaintext             Plaintext phone-based identity
Encrypt sensitive
 values              Protects PII at rest                                          Store sensitive values directly
Treat naive 
timestamps as IST           Follows the assignment specification                    Treat naive timestamps as UTC
Keep events in a 
separate ledger        Preserves event history and supports reporting             Store only the latest call state

## Failure modes considered
_Invalid phone numbers and dates are rejected or treated as invalid values according to field requirements.
Missing required fields result in row rejection.
Duplicate leads are identified using workflow and canonical phone identity.
Duplicate event IDs are prevented from being inserted again.
Malformed JSON event lines are counted and skipped.
Unknown disposition codes are counted.
Sensitive values are encrypted before database storage._

## Testing
_Unit tests are included for:
Indian phone-number normalisation.
Valid and invalid date formats.
Effective disposition selection.
Lead bucket classification._

## Results
_Both supplied data drops were ingested and the five report files were generated successfully.
The generated data-quality report recorded:
Lead rows processed: 4,114
Rejected lead rows: 216
Duplicate lead rows merged: 12,036
Field warnings: 244
Event lines read: 17,490
Malformed events: 16
Duplicate events dropped: 8,951
Orphan events: 461
Unknown disposition events: 42
These are the results from the supplied dataset, not a claim of correctness against every evaluation seed._

## If I had another day
_Fix and verify idempotency of both database records and data-quality statistics.
Add tests for late-arriving leads, orphan events and disposition overrides.
Verify all five reports against the exact required headers, sorting and formatting.
Test the pipeline using a fresh generated dataset and compare results.
Measure ingestion and report-generation performance on the large dataset.
Improve error handling, logging and documentation._
