"""
People Onboarding Module

Comprehensive system for onboarding workers, consultants, contractors, and vendor personnel.
This module handles the complete employee lifecycle from application to full system provisioning.

Key Features:
- Multi-type onboarding workflows (employees, contractors, consultants, vendors)
- AI-powered conversational data collection
- Document verification with OCR and validation
- Multi-stakeholder approval workflows
- Automated access provisioning
- Biometric enrollment integration
- Training and orientation tracking
- Compliance and background checks
- Analytics and reporting

Integration Points:
- apps.onboarding_api: Conversational AI infrastructure
- apps.peoples: User creation and management
- apps.face_recognition: Biometric enrollment
- apps.voice_recognition: Voice biometric setup
- apps.attendance: Attendance tracking auto-enrollment
- apps.work_order_management: Equipment provisioning
- apps.y_helpdesk: IT support ticket creation

Compliance:
- Follows .claude/rules.md for code quality and security
- Model complexity < 150 lines (Rule #7)
- Service functions < 50 lines (Rule #14)
- Comprehensive audit trails
- Multi-tenant data isolation
"""