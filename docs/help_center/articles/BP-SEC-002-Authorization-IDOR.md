# Best Practices: Authorization & IDOR Prevention

**ID:** BP-SEC-002  
**Category:** Security Best Practices  
**Difficulty:** Advanced  
**Last Updated:** November 6, 2025

---

## Overview

Authorization ensures users can only access resources they own. IDOR (Insecure Direct Object Reference) vulnerabilities allow attackers to access other users' data by manipulating IDs.

**Critical Rule:** ALWAYS validate ownership before serving files or sensitive data.

---

## ❌ Critical Vulnerability (FOUND IN AUDIT)

### IDOR File Download Vulnerability

```python
# ❌ FORBIDDEN: Direct file access without permission check
def download_attachment(request):
    attachment_id = request.GET.get('id')
    attachment = Attachment.objects.get(id=attachment_id)  # ⚠️ NO PERMISSION CHECK
    
    # Attacker can access ANY file by changing ID in URL
    filepath = os.path.join(settings.MEDIA_ROOT, attachment.filepath)
    return FileResponse(open(filepath, 'rb'))
```

**Attack Vector:**
```bash
# Legitimate request
curl https://example.com/download?id=123

# Attacker changes ID to access other users' files
curl https://example.com/download?id=456  # ⚠️ Accesses victim's file
```

**Impact:**
- ✅ Data breach - access to all user files
- ✅ Cross-tenant data leakage
- ✅ Compliance violations (GDPR, HIPAA)

---

## ✅ Required Pattern: SecureFileDownloadService

```python
from apps.core.services.secure_file_download_service import SecureFileDownloadService
from apps.core.exceptions.patterns import VALIDATION_EXCEPTIONS
from django.http import JsonResponse

def secure_download_attachment(request):
    """
    Multi-layer security validation before serving files.
    
    Security Layers:
    1. Tenant isolation
    2. Ownership validation
    3. Path traversal prevention
    4. Audit logging
    """
    try:
        # Step 1: Validate user has permission to access attachment
        attachment = SecureFileDownloadService.validate_attachment_access(
            attachment_id=request.GET['id'],
            user=request.user
        )
        
        # Step 2: Validate file path and serve securely
        response = SecureFileDownloadService.validate_and_serve_file(
            filepath=attachment.filepath,
            filename=attachment.filename,
            user=request.user,
            owner_id=attachment.owner
        )
        
        return response
        
    except VALIDATION_EXCEPTIONS as e:
        # Audit logging built-in
        return JsonResponse({
            'error': 'Access denied',
            'correlation_id': e.correlation_id
        }, status=403)
```

**Security Enforced:**

| Layer | Check | Blocks |
|-------|-------|--------|
| 1. Tenant Isolation | `attachment.tenant == user.tenant` | Cross-tenant access |
| 2. Ownership | `attachment.owner == user.id` | IDOR attacks |
| 3. Path Validation | File within `MEDIA_ROOT` | Path traversal |
| 4. Existence Check | File exists on disk | 404 exposure |
| 5. Audit Log | All access attempts logged | Forensics |

---

## SecureFileDownloadService Implementation

```python
# apps/core/services/secure_file_download_service.py

import os
from django.conf import settings
from django.http import FileResponse, Http404
from apps.core.models import Attachment
from apps.core.exceptions.patterns import ValidationError
import logging

logger = logging.getLogger(__name__)

class SecureFileDownloadService:
    """
    Multi-layer file download security validation.
    
    Usage:
        attachment = SecureFileDownloadService.validate_attachment_access(
            attachment_id=request.GET['id'],
            user=request.user
        )
        response = SecureFileDownloadService.validate_and_serve_file(
            filepath=attachment.filepath,
            filename=attachment.filename,
            user=request.user,
            owner_id=attachment.owner
        )
    """
    
    @staticmethod
    def validate_attachment_access(attachment_id, user):
        """
        Validate user has permission to access attachment.
        
        Checks:
        1. Attachment exists
        2. User's tenant matches attachment tenant
        3. User owns the attachment
        
        Raises:
            ValidationError: If any check fails
        """
        try:
            attachment = Attachment.objects.get(id=attachment_id)
        except Attachment.DoesNotExist:
            logger.warning(
                f"Attachment not found: {attachment_id}",
                extra={'user_id': user.id}
            )
            raise ValidationError("Attachment not found")
        
        # Tenant isolation check
        if attachment.tenant_id != user.tenant_id:
            logger.warning(
                f"Cross-tenant access attempt: user {user.id} -> attachment {attachment_id}",
                extra={'user_tenant': user.tenant_id, 'attachment_tenant': attachment.tenant_id}
            )
            raise ValidationError("Access denied")
        
        # Ownership check
        if attachment.owner != user.id:
            logger.warning(
                f"IDOR attempt: user {user.id} -> attachment {attachment_id} (owner: {attachment.owner})",
                extra={'user_id': user.id, 'attachment_id': attachment_id}
            )
            raise ValidationError("You do not have permission to access this file")
        
        return attachment
    
    @staticmethod
    def validate_and_serve_file(filepath, filename, user, owner_id):
        """
        Validate file path and serve securely.
        
        Checks:
        1. Path is within MEDIA_ROOT (prevents path traversal)
        2. File exists
        3. Re-validates ownership
        
        Returns:
            FileResponse with secure headers
        """
        # Construct absolute path
        full_path = os.path.join(settings.MEDIA_ROOT, filepath)
        
        # Prevent path traversal attacks
        real_path = os.path.realpath(full_path)
        if not real_path.startswith(os.path.realpath(settings.MEDIA_ROOT)):
            logger.error(
                f"Path traversal attempt: {filepath}",
                extra={'user_id': user.id, 'requested_path': filepath}
            )
            raise ValidationError("Invalid file path")
        
        # Check file exists
        if not os.path.exists(real_path):
            logger.warning(
                f"File not found: {filepath}",
                extra={'user_id': user.id}
            )
            raise Http404("File not found")
        
        # Audit log successful access
        logger.info(
            f"File download: {filename}",
            extra={
                'user_id': user.id,
                'owner_id': owner_id,
                'filepath': filepath,
                'filename': filename
            }
        )
        
        # Serve file with secure headers
        response = FileResponse(open(real_path, 'rb'))
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['X-Content-Type-Options'] = 'nosniff'  # Prevent MIME sniffing
        
        return response
```

---

## Query-Level Authorization

### ❌ Anti-Pattern: Filter After Query

```python
# ❌ FORBIDDEN: Retrieve all, filter in Python
def get_user_tasks(request):
    all_tasks = Task.objects.all()  # ⚠️ Retrieves ALL tasks
    user_tasks = [t for t in all_tasks if t.assigned_to == request.user]  # Inefficient
    return user_tasks
```

### ✅ Required: Filter at Database Level

```python
# ✅ CORRECT: Filter in query
def get_user_tasks(request):
    """Only retrieve tasks user has permission to see."""
    return Task.objects.filter(
        tenant=request.user.tenant,  # Tenant isolation
        assigned_to=request.user      # User-specific
    ).select_related('site', 'created_by')
```

---

## Multi-Tenant Authorization

```python
from apps.tenants.mixins import TenantAwareMixin

class SecureTaskViewSet(TenantAwareMixin, viewsets.ModelViewSet):
    """
    TenantAwareMixin automatically filters by tenant.
    
    Prevents cross-tenant data access.
    """
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    
    def get_queryset(self):
        """Further filter by user permissions."""
        qs = super().get_queryset()  # Already filtered by tenant
        
        # Additional user-level permissions
        if not self.request.user.is_manager:
            qs = qs.filter(assigned_to=self.request.user)
        
        return qs
```

---

## Testing IDOR Vulnerabilities

```python
from rest_framework.test import APITestCase
from apps.peoples.models import People
from apps.core.models import Attachment

class IDORTests(APITestCase):
    """Test IDOR vulnerability prevention."""
    
    def setUp(self):
        # User 1 with attachment
        self.user1 = People.objects.create_user(username='user1')
        self.attachment1 = Attachment.objects.create(
            owner=self.user1.id,
            tenant=self.user1.tenant,
            filepath='user1/file.pdf'
        )
        
        # User 2 (attacker)
        self.user2 = People.objects.create_user(username='user2')
    
    def test_user_cannot_access_other_users_files(self):
        """CRITICAL: User 2 cannot access User 1's files."""
        self.client.force_authenticate(user=self.user2)
        
        # Attempt IDOR attack
        response = self.client.get(f'/download?id={self.attachment1.id}')
        
        # Must be denied
        self.assertEqual(response.status_code, 403)
        self.assertIn('Access denied', response.content.decode())
    
    def test_user_can_access_own_files(self):
        """User can access their own files."""
        self.client.force_authenticate(user=self.user1)
        
        response = self.client.get(f'/download?id={self.attachment1.id}')
        
        # Must succeed
        self.assertEqual(response.status_code, 200)
    
    def test_path_traversal_blocked(self):
        """Prevent path traversal attacks."""
        self.client.force_authenticate(user=self.user1)
        
        # Create malicious attachment
        evil_attachment = Attachment.objects.create(
            owner=self.user1.id,
            tenant=self.user1.tenant,
            filepath='../../etc/passwd'  # Path traversal attempt
        )
        
        response = self.client.get(f'/download?id={evil_attachment.id}')
        
        # Must be blocked
        self.assertEqual(response.status_code, 400)
```

---

## Authorization Checklist

- [ ] **File downloads use SecureFileDownloadService**
- [ ] **Database queries filter by tenant first**
- [ ] **Ownership validated before data access**
- [ ] **No direct object access via ID without permission check**
- [ ] **Path traversal prevention implemented**
- [ ] **Audit logging for access attempts**
- [ ] **IDOR tests written for all sensitive endpoints**
- [ ] **Cross-tenant access tests written**

---

## Common Mistakes

### Mistake 1: Trust User Input

```python
# ❌ WRONG: Trust ID from user
attachment_id = request.GET.get('id')
attachment = Attachment.objects.get(id=attachment_id)  # NO VALIDATION
```

**Fix:** Always validate ownership.

### Mistake 2: Check After Retrieval

```python
# ❌ WRONG: Check after fetching
attachment = Attachment.objects.get(id=attachment_id)
if attachment.owner != request.user.id:  # Too late!
    raise PermissionDenied
```

**Fix:** Filter in query or use service layer.

---

## References

- **[Secure File Download Remediation](../../SECURE_FILE_DOWNLOAD_REMEDIATION_COMPLETE.md)** - Complete fix
- **[IDOR Audit Report](../../IDOR_VULNERABILITY_AUDIT_REPORT.md)** - Vulnerabilities found
- **[Multi-Tenancy Security](../../MULTI_TENANCY_SECURITY_AUDIT_REPORT.md)** - Tenant isolation
- **[BP-SEC-001: API Authentication](BP-SEC-001-API-Authentication.md)** - Authentication layer

---

**Questions?** Submit a Help Desk ticket with tag `best-practices-authorization`
