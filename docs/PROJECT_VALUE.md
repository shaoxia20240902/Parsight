# Project Value

Parsight is an open-source AI BI application for turning spreadsheet data into trustworthy analysis workflows. The project focuses on a common but underserved use case: teams have important business data in XLSX files, but they do not have enough time or BI expertise to model, query, visualize, and explain it.

## What It Does

- Parses uploaded XLSX files and stores sheet data in a queryable database.
- Uses AI agents to understand each sheet across business meaning, grain, metrics, dimensions, anomalies, and analysis opportunities.
- Discovers cross-sheet relationships and validates them with executable SQL.
- Generates BI dashboards from natural-language goals, including chart titles, metric definitions, SQL queries, chart configs, and insight summaries.
- Supports fast Q&A and deeper multi-step research over private business data.

## Why It Matters

Most small teams still rely on Excel as their operational data layer. Traditional BI tools often require data modeling, dashboard design, and SQL knowledge before business users can get answers. Parsight lowers that barrier by combining spreadsheet ingestion, semantic understanding, SQL generation, chart generation, and report writing in one open-source workflow.

## Current Engineering Scope

The repository contains a complete full-stack implementation:

- Backend: FastAPI, SQLAlchemy, MySQL, Pandas, OpenPyXL, SSE streaming, JWT authentication.
- Frontend: Vue 3, Vite, Element Plus, Pinia, ECharts, TypeScript.
- AI workflow: sheet understanding, relationship analysis, BI planning, NLQ-to-SQL, chart generation, report generation.
- Developer materials: setup scripts, mock data, architecture docs, BI design docs, test reports, and contribution guidance.

## Open Source Direction

Parsight is released under the MIT License. The goal is to make AI-assisted BI easier to inspect, self-host, customize, and extend. Future contributors can improve data connectors, chart templates, SQL safety rules, evaluation datasets, model adapters, and domain-specific analysis agents.
