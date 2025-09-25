# Product Overview

## YOUTILITY5 - Enterprise Facility Management System

YOUTILITY5 is a comprehensive Django-based enterprise facility management platform designed for multi-tenant environments. Originally built for security guards and facility management teams, it provides real-time monitoring, asset tracking, work order management, and comprehensive reporting capabilities.

### Core Business Domain

- **Primary Users**: Security guards, facility managers, maintenance teams, site supervisors
- **Use Cases**: Site monitoring, preventive maintenance, work permits, attendance tracking, asset management
- **Scale**: Enterprise-level with multi-site support across multiple clients
- **Integration**: ERP systems, IoT devices (MQTT), mobile applications, biometric systems

### Key Features

- **Multi-tenant Architecture**: Complete data isolation per client with tenant-aware models
- **Mobile-First Design**: Optimized for field workers with offline capabilities
- **Real-time IoT Integration**: MQTT-based device communication for sensors and access control
- **AI-Enhanced Operations**: Face recognition, anomaly detection, behavioral analytics
- **Comprehensive Reporting**: PDF generation with custom templates and scheduled reports
- **Advanced Security**: Rate limiting, session management, audit logging, and CSP protection

### Business Context

The system manages the complete lifecycle of facility operations from employee onboarding and attendance tracking to asset maintenance and work order management. It serves as the central hub for coordinating security operations, maintenance schedules, and compliance reporting across multiple sites and clients.

### Target Environment

Production deployment typically involves:
- Multi-site installations with 100-1000+ users per client
- 24/7 operations with real-time monitoring requirements
- Integration with existing security systems and IoT devices
- Compliance with security and audit requirements
- Mobile workforce requiring offline-capable applications