# Stream Testbench & Issue Knowledge Base

_Preamble: A subsystem to test and observe real‑time streams with PII protection, and to capture anomalies into a knowledge base for recurrence detection and fixes._

## Streamlab
- Models: `apps/streamlab/models.py`
  - `TestScenario` (protocol, endpoint, config, PII rules)
  - `TestRun` (execution metrics, SLO checks)
  - `StreamEvent` (sanitized payloads, schema signatures, anomalies)
- WebSocket dashboards: `apps/streamlab/consumers.py`

## Issue Tracker
- Models: `apps/issue_tracker/models.py`
  - `AnomalySignature` (unique fingerprint with severity, status, MTTR/MTBF metrics)
  - `AnomalyOccurrence` (instances tied to events/runs; assignments and resolution)

## Extending
- Define scenarios with expected SLOs and explicit PII allowlists.
- Add anomaly rules/fix suggestions under `apps/issue_tracker/services/` and `apps/issue_tracker/rules/`.

## Scenario Configuration Examples
`TestScenario.config` suggestions:
```json
{
  "rate_qps": 50,
  "burst_limit": 200,
  "jitter_ms": {"p50": 25, "p95": 120},
  "timeouts_ms": {"connect": 2000, "request": 5000},
  "failures": {"probability": 0.01, "types": ["timeout","malformed_payload"]}
}
```

## PII Redaction Rules (DSL)
`pii_redaction_rules`:
```json
{
  "allowlisted_fields": ["timestamp","event_type","duration_ms","confidence_score"],
  "hash_fields": ["user_id","device_id","session_id"],
  "remove_fields": ["voice_sample","image_data","free_text"],
  "hash_algo": "sha256",
  "salt_env_var": "PII_HASH_SALT"
}
```
Guidelines: avoid reversible hashes; never store raw PII; treat salts as secrets.

## Schema Signatures & Anomaly Fingerprints
- Schema signature: derive a normalized structure (sorted keys + value types) and compute SHA‑256; store in `payload_schema_hash`.
- Fingerprint: combine endpoint pattern + error class + schema signature + stack trace hash → SHA‑256 stored in `AnomalySignature.signature_hash`.

## Triage Workflow
1) New `StreamEvent` recorded with sanitized payload and timings
2) If anomalous (`latency_ms > threshold` or error outcome), create/attach `AnomalyOccurrence`
3) Group to a signature (`AnomalySignature`) or create one if none matches
4) Assign owner, set status to `investigating`, capture resolution notes on close
5) Track MTTR/MTBF metrics on the signature

## SLO Tuning
- For each scenario: set `expected_p95_latency_ms` and `expected_error_rate`
- Treat `TestRun.is_within_slo` as a gating signal in CI
- Adjust thresholds using representative load tests and environment variances
