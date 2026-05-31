# Security and API Usage Plan

This document explains why Parsight benefits from Codex Security review and OpenAI API credits.

## Codex Security Needs

Parsight handles user-uploaded spreadsheets and turns AI-generated analysis plans into executable database queries. That creates several important security surfaces:

- File upload and XLSX parsing must reject unsafe or malformed inputs.
- Dynamic table creation must avoid unsafe identifiers and schema collisions.
- AI-generated SQL must be constrained, validated, and executed with least privilege.
- Authentication, JWT handling, workspace separation, and admin routes must be reviewed for authorization gaps.
- Environment files and model API keys must stay out of commits and logs.
- Streaming endpoints should avoid leaking internal errors, prompts, database details, or private data.
- Dependencies in both Python and Node stacks need regular vulnerability checks.

Codex Security can help review these risks continuously as the project evolves.

## API Credit Usage

API credits will be used for the AI features that define the project:

- Spreadsheet schema and field semantics understanding.
- Cross-sheet relationship discovery and verification.
- Natural-language question decomposition.
- SQL generation and repair.
- Chart recommendation and dashboard composition.
- Narrative insight and report generation.
- Evaluation runs that compare prompts, models, accuracy, latency, and cost.

The immediate goal is to improve the reliability of AI-assisted BI generation while keeping the system practical for self-hosted open-source users.
