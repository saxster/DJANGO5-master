# Work Order Security Guide

**Last Updated**: November 6, 2025  
**Module**: Work Order Management  
**Security Level**: CRITICAL  

---

## Quick Reference

### Importing Security Service

```python
from apps.work_order_management.services.work_order_security_service import (
    WorkOrderSecurityService
)
from django.core.exceptions import PermissionDenied
```

### Common Patterns

#### 1. Validate Work Order Access (Authenticated Views)

```python
# Require ownership
try:
    work_order = WorkOrderSecurityService.validate_work_order_access(
        work_order_id=int(request.GET['id']),
        user=request.user,
        require_ownership=True
    )
except PermissionDenied as e:
    return JsonResponse({"error": str(e)}, status=403)
```

```python
# Allow same-tenant access
try:
    work_order = WorkOrderSecurityService.validate_work_order_access(
        work_order_id=int(request.GET['id']),
        user=request.user,
        allow_tenant_access=True
    )
except PermissionDenied as e:
    return JsonResponse({"error": str(e)}, status=403)
```

#### 2. Validate Token Access (Public Email Workflows)

```python
# Vendor email reply
try:
    if not request.GET.get('token'):
        return HttpResponse("Invalid token", status=403)
    
    work_order = WorkOrderSecurityService.validate_vendor_access(
        work_order_id=int(request.GET['womid']),
        token=request.GET['token']
    )
except PermissionDenied as e:
    return HttpResponse(str(e), status=403)
```

#### 3. Validate Approver Access

```python
# Approver/verifier email workflow
try:
    work_order, approver = WorkOrderSecurityService.validate_approver_access(
        work_order_id=int(request.GET['womid']),
        people_id=int(request.GET['peopleid']),
        token=request.GET.get('token')  # Optional
    )
except PermissionDenied as e:
    return HttpResponse(str(e), status=403)
```

#### 4. Get Filtered Queryset

```python
# Automatically filter by user's tenant
queryset = WorkOrderSecurityService.get_user_work_orders_queryset(request.user)
work_orders = queryset.filter(workstatus='ASSIGNED')
```

---

## Security Methods Reference

### `generate_secure_token()`
Generate cryptographically secure token for email workflows.

**Returns**: 32-character URL-safe token

**Usage**:
```python
token = WorkOrderSecurityService.generate_secure_token()
work_order.other_data['token'] = token
work_order.save()
```

---

### `validate_work_order_access()`
Validate user has access to work order (authenticated views).

**Parameters**:
- `work_order_id` (int): Work order ID
- `user` (User): Current user
- `require_ownership` (bool): If True, user must be owner (default: False)
- `allow_tenant_access` (bool): If True, allow same-tenant access (default: True)

**Returns**: Wom instance

**Raises**:
- `PermissionDenied`: User lacks access
- `Wom.DoesNotExist`: Work order not found

**When to use**:
- `require_ownership=True`: Delete, update operations
- `allow_tenant_access=True`: View, close operations

---

### `validate_token_access()`
Validate token-based access for email workflows (public views).

**Parameters**:
- `work_order_id` (int): Work order ID
- `token` (str): Security token from email link

**Returns**: Wom instance

**Raises**:
- `PermissionDenied`: Invalid token
- `ValidationError`: Token format invalid

**Security Notes**:
- Token must be at least 16 characters
- Token must match value in `other_data['token']`
- Use for vendor email replies

---

### `validate_approver_access()`
Validate approver/verifier has permission to act on work order.

**Parameters**:
- `work_order_id` (int): Work order ID
- `people_id` (int): Approver's people ID
- `token` (str, optional): Security token

**Returns**: Tuple of (Wom, People)

**Raises**:
- `PermissionDenied`: Person not authorized

**Validation Logic**:
- Checks if person is in `wp_approvers`, `wp_verifiers`, or `sla_approvers`
- Optionally validates token if provided

---

### `validate_vendor_access()`
Validate vendor has access via email token.

**Parameters**:
- `work_order_id` (int): Work order ID
- `token` (str): Security token from email link

**Returns**: Wom instance

**Raises**:
- `PermissionDenied`: Invalid token or work order completed

**Additional Checks**:
- Prevents modification of completed work orders

---

### `validate_delete_permission()`
Validate user can delete work order.

**Parameters**:
- `work_order_id` (int): Work order ID
- `user` (User): Current user

**Returns**: Wom instance

**Raises**:
- `PermissionDenied`: User cannot delete

**Rules**:
- Only owner can delete
- Cannot delete in-progress work orders

---

### `validate_close_permission()`
Validate user can close work order.

**Parameters**:
- `work_order_id` (int): Work order ID
- `user` (User): Current user

**Returns**: Wom instance

**Raises**:
- `PermissionDenied`: User cannot close

**Rules**:
- Owner or same-tenant user can close

---

### `get_user_work_orders_queryset()`
Get queryset of work orders accessible to user.

**Parameters**:
- `user` (User): Current user

**Returns**: QuerySet (filtered by tenant and business unit)

**Usage**:
```python
# Get all work orders user can access
queryset = WorkOrderSecurityService.get_user_work_orders_queryset(request.user)

# Apply additional filters
assigned_orders = queryset.filter(workstatus='ASSIGNED')
```

---

## Security Checklist

### For Authenticated Views (LoginRequiredMixin)

- [ ] Import `WorkOrderSecurityService` and `PermissionDenied`
- [ ] Use `validate_work_order_access()` for all work order operations
- [ ] Set `require_ownership=True` for delete/update operations
- [ ] Set `allow_tenant_access=True` for view/close operations
- [ ] Catch `PermissionDenied` and return 403 Forbidden
- [ ] Use `get_user_work_orders_queryset()` for list views

### For Public Views (Email Workflows)

- [ ] Require `token` parameter in URL
- [ ] Validate token is present before any operation
- [ ] Use `validate_vendor_access()` or `validate_token_access()`
- [ ] Catch `PermissionDenied` and return 403 Forbidden
- [ ] Generate token when creating work order
- [ ] Include token in email URLs

### For Approval Workflows

- [ ] Require `womid`, `peopleid`, and optionally `token`
- [ ] Use `validate_approver_access()` to verify authorization
- [ ] Prevent duplicate approvals/rejections
- [ ] Log approval actions

---

## Common Mistakes to Avoid

### ❌ WRONG: Direct database access without validation
```python
# VULNERABLE TO IDOR
work_order = Wom.objects.get(id=request.GET['id'])
work_order.delete()
```

### ✅ CORRECT: Validate before access
```python
# PROTECTED AGAINST IDOR
try:
    work_order = WorkOrderSecurityService.validate_delete_permission(
        int(request.GET['id']),
        request.user
    )
    work_order.delete()
except PermissionDenied as e:
    return JsonResponse({"error": str(e)}, status=403)
```

---

### ❌ WRONG: Public endpoint without token
```python
# VULNERABLE - Anyone can call this
def accept_work_order(request):
    wo = Wom.objects.get(id=request.GET['womid'])
    wo.workstatus = 'INPROGRESS'
    wo.save()
```

### ✅ CORRECT: Validate token
```python
# PROTECTED - Token required
def accept_work_order(request):
    try:
        if not request.GET.get('token'):
            return HttpResponse("Invalid token", status=403)
        
        wo = WorkOrderSecurityService.validate_vendor_access(
            int(request.GET['womid']),
            request.GET['token']
        )
        wo.workstatus = 'INPROGRESS'
        wo.save()
    except PermissionDenied as e:
        return HttpResponse(str(e), status=403)
```

---

### ❌ WRONG: Returning detailed error messages
```python
# INFORMATION DISCLOSURE
except PermissionDenied as e:
    return JsonResponse({
        "error": f"User {request.user.id} cannot access work order {wo.id} owned by {wo.cuser_id}"
    }, status=403)
```

### ✅ CORRECT: Generic error messages
```python
# SECURE - No information disclosure
except PermissionDenied as e:
    return JsonResponse({"error": "Access denied"}, status=403)
    # Detailed info goes to logs only
```

---

## Testing Your Security Implementation

### Unit Tests

```python
import pytest
from django.core.exceptions import PermissionDenied
from apps.work_order_management.services.work_order_security_service import (
    WorkOrderSecurityService
)

@pytest.mark.django_db
def test_cross_tenant_access_denied(work_order, other_tenant_user):
    """Test IDOR protection."""
    with pytest.raises(PermissionDenied):
        WorkOrderSecurityService.validate_work_order_access(
            work_order.id,
            other_tenant_user,
            allow_tenant_access=True
        )
```

### Manual Testing

1. **Test IDOR Protection**:
   - Create work order as User A
   - Log in as User B (different tenant)
   - Try to access work order via URL
   - Expected: 403 Forbidden

2. **Test Token Validation**:
   - Create work order
   - Access public endpoint without token
   - Expected: 403 Forbidden
   - Access with valid token
   - Expected: Success

3. **Test Ownership**:
   - Create work order as User A
   - Log in as User B (same tenant)
   - Try to delete work order
   - Expected: 403 Forbidden

---

## Security Audit Logging

All security events are logged with:

```python
logger.info(
    f"Access granted: User {user.id} accessing work order {work_order_id}"
)

logger.warning(
    f"IDOR attempt: User {user.id} tried to access "
    f"work order {work_order_id} owned by {work_order.cuser_id}"
)

logger.warning(
    f"Cross-tenant IDOR attempt: User {user.id} (tenant {user_client_id}) "
    f"tried to access work order {work_order_id} (tenant {work_order.client_id})"
)
```

---

## Email Template Updates

When creating work orders, include token in email URLs:

```python
# Generate token
work_order.other_data['token'] = WorkOrderSecurityService.generate_secure_token()
work_order.save()

# Email template
accept_url = f"{base_url}/reply-work-order?action=accepted&womid={work_order.id}&token={work_order.other_data['token']}"
decline_url = f"{base_url}/reply-work-order?action=declined&womid={work_order.id}&token={work_order.other_data['token']}"
```

---

## Performance Considerations

- Authorization checks add <10ms per request
- Use `select_related()` to minimize queries:
  ```python
  # In security service
  work_order = Wom.objects.select_related('client', 'bu', 'vendor', 'cuser').get(id=work_order_id)
  ```
- Database queries use indexed fields (`client_id`, `cuser_id`)
- Token validation is in-memory string comparison

---

## Additional Security Layers (Future)

1. **Rate Limiting**: Prevent brute force token guessing
2. **Token Expiration**: Invalidate tokens after 24-48 hours
3. **IP Whitelisting**: Restrict access to known IPs
4. **Two-Factor Authentication**: For critical operations
5. **Anomaly Detection**: Flag unusual access patterns

---

## Support

- **Security Issues**: Report immediately to security team
- **Implementation Questions**: See examples in `work_order_views.py`
- **Test Suite**: `apps/work_order_management/tests/test_security_service.py`

---

**Remember**: Security is mandatory, not optional. All work order access must go through the security service.
