# Developer’s Guide

Welcome to the Developer’s Guide for the YOUTILITY5 Django application. This guide is opinionated, practical, and extensible. It teaches the platform’s architecture, security posture, domain modules, and the patterns to build new features safely and quickly.

- Audience: Backend engineers, full‑stack developers, SREs, and advanced contributors
- Stack: Django, DRF, Graphene, Channels, Postgres/PostGIS, Redis, Jinja2, Celery (optional)
- Conventions: Tenant‑aware models, domain‑driven URLs, security by default, observability first

How to use this guide
- Start with Architecture Overview, then Security & Compliance.
- Jump to your domain (People/Attendance/Operations, Journal & Wellness, Onboarding, Streamlab) for details.
- Use Extensibility Patterns before introducing new modules.

Quick start
- Configure env in `intelliwiz_config/envs/` (the active file is set in `intelliwiz_config/settings.py`).
- Requirements: PostgreSQL + PostGIS, Redis, Python 3.10+.
- Migrate and run: `python manage.py migrate && python manage.py runserver`.
- Health endpoints: `/health`, `/ready`, `/alive`, `/monitoring/health/`.

This folder includes one Markdown per chapter and a GitBook‑ready `SUMMARY.md`.

Common tasks
- See: [Common Developer Tasks](developer-tasks.md) for copy‑paste workflows (GraphQL fields, REST endpoints, WS consumers, tenant‑aware models, routes, metrics, tests, reports).
