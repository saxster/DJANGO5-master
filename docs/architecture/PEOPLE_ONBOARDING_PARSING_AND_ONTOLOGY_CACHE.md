# People Onboarding Parsing & Ontology Registry Cache

Updates from the Ultrathink remediation now ship two multi-team capabilities:

1. **AI-assisted document parsing for People Onboarding**
2. **Process-wide caching for the Ontology registry**

This note describes the knobs operators/infra owners need to wire up before enabling the features in production.

---

## 1. People Onboarding Document Parsing

### Feature overview
- Resumes: regex/section-based entity extraction (name, email, phone, skills, experience, education, certifications)
- ID documents: OCR-backed identifier + DOB parsing (Aadhaar, PAN, Passport, Driving License, Address Proof)
- Other documents: keyword extraction + sentence summaries
- Results are written to `DocumentSubmission.extracted_data` and surfaced to reviewers
- Celery task: `apps.people_onboarding.tasks.extract_document_data`

### Configuration
| Setting | Default | Description |
|---------|---------|-------------|
| `PEOPLE_ONBOARDING_ENABLE_AI_DOCUMENT_PARSING` | `False` (prod) / `True` (dev,test) | Master feature flag. Turn **on** once OCR creds + Celery queues are ready. |
| `PEOPLE_ONBOARDING_MAX_DOCUMENT_PAGES` | `12` | Hard cap on the number of PDF pages parsed per document. |
| `PEOPLE_ONBOARDING_MAX_DOCUMENT_SIZE_MB` | `10` | Upload-size guard for AI parsing (matching the Dropzone UI guidance). |
| `PEOPLE_ONBOARDING_OCR_CONFIDENCE_THRESHOLD` | `0.65` | Future use: threshold for automatically trusting OCR output. Stored so ops can keep a single source of truth. |

All values can be supplied via environment variables (same name). Example Helm snippet:

```yaml
env:
  PEOPLE_ONBOARDING_ENABLE_AI_DOCUMENT_PARSING: "true"
  PEOPLE_ONBOARDING_MAX_DOCUMENT_PAGES: "12"
  PEOPLE_ONBOARDING_MAX_DOCUMENT_SIZE_MB: "10"
  PEOPLE_ONBOARDING_OCR_CONFIDENCE_THRESHOLD: "0.65"
```

### Operational checklist
1. Configure Google Vision (or the configured OCR backend) credentials for the Celery worker.
2. Ensure the `document-parser` queue is routed to CPU-friendly workers (no GPU needed).
3. Turn on the feature flag and monitor `DocumentSubmission.verification_status` for `REQUIRES_REUPLOAD` spikes.
4. UI will automatically surface “AI parsing offline” badges when the flag is `False`.

---

## 2. Ontology Registry Cache

### Why
The ontology registry previously lived only in-process, causing each Gunicorn worker to register tens of thousands of entries independently. The new cache-backed snapshot guarantees warm starts and consistent responses across workers.

### Configuration
| Setting | Default | Description |
|---------|---------|-------------|
| `ONTOLOGY_REGISTRY_CACHE_ENABLED` | `True` | Master toggle for sharing registry snapshots through Django’s cache backend. |
| `ONTOLOGY_REGISTRY_CACHE_KEY` | `apps.ontology.registry.snapshot` | Cache key storing the serialized registry. Override if multiple stacks share the same cache cluster. |
| `ONTOLOGY_REGISTRY_CACHE_TIMEOUT` | `3600` seconds | TTL for the snapshot. A rolling window is fine because every update writes a fresh copy. |
| `ONTOLOGY_REGISTRY_AUTO_WARM` | `True` | Whether to fall back to executing `apps.ontology.registrations.load_all_registrations()` when the cache is empty. Keep enabled unless you boot from a pre-generated snapshot. |

### Operating tips
1. **Redis recommended**: LocMem works for tests, but Redis or Memcached gives true multi-worker consistency.
2. **Cache reset**: run `python manage.py shell -c "from apps.ontology.registry import OntologyRegistry; OntologyRegistry.clear()"` to force a rebuild.
3. **Monitoring**: the new regression test (`apps/ontology/tests/test_registry_cache.py`) ensures cache hydration stays wired—wire it into CI to prevent regressions.

With both settings blocks configured, people onboarding finally advertises AI parsing only when the end-to-end pipeline is healthy, and ontology queries remain consistent regardless of process layout.
