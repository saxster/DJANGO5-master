# Message Bus & Streaming Architecture

**Last Updated:** November 1, 2025
**Version:** 2.0 (Post-Remediation)
**Status:** Production-Ready

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Message Bus Components](#message-bus-components)
4. [Data Flows](#data-flows)
5. [Queue Configuration](#queue-configuration)
6. [Security & Compliance](#security--compliance)
7. [Performance & Scaling](#performance--scaling)
8. [Monitoring & Observability](#monitoring--observability)
9. [Operations Guide](#operations-guide)
10. [Troubleshooting](#troubleshooting)

---

## Executive Summary

The IntelliWiz message bus architecture provides real-time, bidirectional communication across four integrated messaging systems:

| System | Purpose | Implementation | Status |
|--------|---------|----------------|--------|
| **Celery** | Async task queue | Redis broker + PostgreSQL-backed beat | ✅ Production |
| **MQTT** | IoT device telemetry | Mosquitto broker + paho-mqtt | ✅ Bidirectional |
| **WebSocket** | Real-time UI updates | Django Channels + Redis | ✅ Encrypted |
| **Prometheus** | Metrics export | `/metrics/export/` endpoint | ✅ Active |

**Key Characteristics:**
- **Bidirectional MQTT** - Devices can send telemetry AND receive commands
- **Direct Celery → WebSocket** - Tasks broadcast without Django signals intermediary
- **Unified Observability** - All components export to Prometheus
- **Security-First** - Encryption, authentication, circuit breakers throughout

---

## Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       Message Bus & Streaming Layer                      │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
        ┌──────────────┬──────────────┼──────────────┬──────────────┐
        │              │              │              │              │
        ▼              ▼              ▼              ▼              ▼
   ┌────────┐    ┌──────────┐   ┌──────────┐  ┌────────────┐  ┌──────────┐
   │ MQTT   │    │ Celery   │   │WebSocket │  │Prometheus  │  │  Redis   │
   │ Broker │    │ Workers  │   │ Channels │  │  Metrics   │  │  Cache   │
   └────────┘    └──────────┘   └──────────┘  └────────────┘  └──────────┘
       │              │               │              │              │
       │              │               │              │              │
   IoT Devices   Background      Web Clients    Monitoring      Shared
   (Guards,      Tasks (ML,      (Dashboard,    (Grafana,      State &
   Sensors)      Reports)        NOC)           Alert Manager)  Queues
```

---

## Security & Compliance

### Security Layers

**1. MQTT Security:**
- Username/password authentication (configurable)
- TLS encryption support (`MQTT_SSL_ENABLED=true`)
- Topic whitelist enforcement (only allowed prefixes)
- Payload validation (JSON schema, size limits, SQL injection prevention)

**2. WebSocket Security:**
- JWT authentication + session fallback
- Origin validation (CORS-like for WebSockets)
- Connection throttling (100 msg/min per connection)
- **Channel layer encryption (MANDATORY in production)**
- Token binding to device fingerprints

**3. Celery Security:**
- **JSON-only serialization** (safe, no arbitrary code execution risk)
- Task result sanitization
- Circuit breakers for external services
- Idempotency framework (duplicate task prevention)

**4. Prometheus Security:**
- Optional IP whitelist (`PROMETHEUS_ALLOWED_IPS`)
- Read-only endpoint (no writes)
- No sensitive data in metric labels

### Compliance

**PCI DSS Level 1:**
- Redis TLS enforced after April 1, 2025 ✅
- Channel layer encryption mandatory in production ✅
- No secrets in logs or metrics ✅

**OWASP Top 10:**
- Input validation on all MQTT payloads ✅
- XSS prevention in WebSocket messages ✅
- SQL injection prevention in task parameters ✅
- No command injection in MQTT topics ✅

---

**Document Version:** 2.0
**Last Updated:** November 1, 2025
**Maintainer:** DevOps & Architecture Team
