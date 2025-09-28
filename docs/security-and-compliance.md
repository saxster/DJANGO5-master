# Security & Compliance

_Preamble: Security is woven throughout: CSP nonces, defensive middleware, authenticated APIs, PII redaction for streams, and privacy‑aware models. Build without weakening guarantees._

## Controls
- CSP Nonces: `apps/core/middleware/csp_nonce.py` injects per‑request nonces; CSP directives in `intelliwiz_config/settings.py`.
- XSS/SQLi Protection: `apps/core/xss_protection.py`, `apps/core/sql_security.py` and helpers in `apps/core/utils_new/`.
- Authentication:
  - User model: `peoples.People`
  - GraphQL JWT middleware (see `GRAPHENE` and `GRAPHQL_JWT` in settings)
  - DRF permissions for REST endpoints
- PII & Privacy:
  - Stream PII protection in `apps/streamlab/models.py` (allowlists, hashing, removals)
  - Journal privacy and consent in `apps/journal/models.py` and `apps/journal/privacy.py`
- CORS/CSRF/Cookies: Strict origins, credentialed CORS when necessary; secure cookies/redirects via env flags.
- Multi‑tenancy: `TenantAwareModel` for all tenant data; route through tenant filters consistently.

## Developer Guidance
- Avoid inline scripts; if needed, use the CSP nonce placed on the request.
- Sanitize all free‑text fields when rendering; never trust user input.
- Prefer ORM query composition; validate dynamic filters (`apps/core/utils_new/sql_security.py`).
- Define PII rules before adding new streams or payload capture.

## Auditing & Alerts
- Monitoring hooks in `monitoring/performance_monitor_enhanced.py` with slow query alerts and regression checks.
- CSP reporting endpoint configurable via settings; blocklist noisy bots.

## Secure Coding Checklists
- XSS: never render unescaped user content; avoid `safe` unless audited; sanitize HTML inputs.
- CSRF: use Django’s CSRF middleware for forms; set `CSRF_COOKIE_SECURE` in prod.
- SQLi: never string‑format SQL; use ORM or parameterized queries; validate sort/filter fields against an allowlist.
- Secrets: keep secrets in env files (not in VCS); rotate keys regularly; restrict access.
- Logging: avoid logging PII/secrets; include correlation IDs; redact sensitive fields.

## CSP Nonce Usage Examples
- Django template:
```html
<script nonce="{{ request.csp_nonce }}">/* inline, minimal */</script>
```
- Jinja template: pass `request` in context (already configured); reference `{{ request.csp_nonce }}` similarly.
- Prefer external JS/CSS with subresource integrity; use nonces for unavoidable inline fragments.

## Safe ORM Filtering
- Map user‑provided sort/filter keys to model fields via a dict:
```python
FIELD_MAP = {"name": "people__peoplename", "code": "people__peoplecode"}
field = FIELD_MAP.get(request.GET.get("sort"), "id")
qs = Model.objects.order_by(field)
```
- For text filters, use `icontains` on approved fields; never interpolate column names or raw WHERE strings.

## Secrets & Environment Separation
- Use `intelliwiz_config/envs/` with environment‑specific files; keep production keys out of dev files.
- Deny DEBUG in production (`settings.py` enforces this for prod envs).
- Store salts (e.g., for hashing) in environment; never in code.

## Rate Limiting & TLS
- Paths covered by rate limiting: see `RATE_LIMIT_PATHS` and related settings.
- Terminate TLS at a trusted proxy; set `SECURE_SSL_REDIRECT` and secure cookies in production.

## Data Subject Rights (DSR)
- Export: build filtered queries per tenant and user; redact PII as required; deliver via secure links.
- Delete: implement soft‑delete where retention is required; otherwise cascade deletes carefully; log DSR actions for audit.
