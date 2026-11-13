# AI Usage Disclosure

AI tools are allowed. We want to know **how** you used them, because using them well is a
skill. Honest answers are never held against you. Discovering undisclosed use is.

## Tools used
ChatGPT

## What I used them for
_Understanding the assignment requirements and breaking the work into manageable steps.
Getting guidance on the Python project structure and implementation.
Assistance with debugging Python errors and resolving import-path issues.
Reviewing phone normalisation, date parsing, event processing and report-generation logic.
Drafting unit tests for phone normalisation, date parsing, effective disposition and lead bucket logic.
Understanding Git commands and preparing the project for submission.

## What I wrote or decided myself
I worked on implementing and integrating the solution in the project files.
I made the implementation decisions and reviewed the code while working through the assignment.
I ran the ingestion and report-generation commands and checked the generated output files.
I reviewed and tested the code before preparing the submission.

## Where the AI was wrong or unhelpful
An initial test import failed because the reports module imported utils using a path that was not available when running tests from the project root. I checked the traceback and corrected the test import path.
Some suggested implementation changes needed to be checked against the actual assignment requirements rather than accepted without verification.

## How I verified AI-generated code
Ran Python compilation checks using python -m compileall solution.
Ran the ingestion pipeline on both supplied data drops.
Generated and inspected the five report files.
Ran unit tests using python -m unittest discover -s tests -v.
Reviewed errors and corrected issues before running the tests again.
