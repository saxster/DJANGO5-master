"""
Capability model for the peoples app.

This module contains the Capability model which defines hierarchical
capabilities that can be assigned to users for different platform types.

Compliant with Rule #7 from .claude/rules.md (< 80 lines).
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.tenants.models import TenantAwareModel
from .base_model import BaseModel
from ..managers import CapabilityManager

from apps.ontology.decorators import ontology


@ontology(
    domain="people",
    concept="Authorization & Permission Management",
    purpose=(
        "Hierarchical capability/permission model for fine-grained access control across "
        "multiple platform types (web, mobile, reports, NOC, portlets). Capabilities form "
        "a tree structure with parent-child relationships, enabling role-based access control "
        "(RBAC) and tenant-aware permission management."
    ),
    criticality="critical",
    security_boundary=True,
    models=[
        {
            "name": "Capability",
            "purpose": "Defines hierarchical permission capabilities that can be assigned to users/groups for access control",
            "platform_types": ["WEB", "PORTLET", "REPORT", "MOB (Mobile)", "NOC (Network Operations)"],
            "hierarchy": "Self-referential tree structure via parent ForeignKey",
            "tenant_aware": True,
            "business_logic": [
                "Tree structure: Each capability can have parent and multiple children",
                "Platform scoping: Capabilities are specific to platform type (web vs mobile)",
                "Client isolation: Multi-tenant via client ForeignKey",
                "Enable/disable: Soft deletion via enable flag",
            ],
        },
    ],
    inputs=[
        {
            "name": "capscode",
            "type": "str",
            "description": "Unique code identifying the capability (e.g., 'user.create', 'report.view', 'admin.delete')",
            "required": True,
            "max_length": 50,
            "sensitive": False,
            "unique_together": ["capscode", "cfor", "client"],
        },
        {
            "name": "capsname",
            "type": "str",
            "description": "Human-readable name of the capability (e.g., 'Create User', 'View Reports')",
            "required": False,
            "max_length": 1000,
            "sensitive": False,
        },
        {
            "name": "parent",
            "type": "ForeignKey(self)",
            "description": "Parent capability in the hierarchy (e.g., 'user' is parent of 'user.create')",
            "required": False,
            "cascade": "RESTRICT (prevents accidental deletion of parent capabilities)",
        },
        {
            "name": "cfor",
            "type": "str (choices)",
            "description": "Platform type: WEB, PORTLET, REPORT, MOB, NOC",
            "required": True,
            "default": "WEB",
            "choices": ["WEB", "PORTLET", "REPORT", "MOB", "NOC"],
        },
        {
            "name": "client",
            "type": "ForeignKey(Bt)",
            "description": "Client organization (multi-tenant isolation)",
            "required": False,
            "cascade": "RESTRICT (prevents deletion of client with active capabilities)",
            "sensitive": True,
        },
        {
            "name": "enable",
            "type": "bool",
            "description": "Whether capability is active (soft delete mechanism)",
            "required": False,
            "default": True,
        },
    ],
    outputs=[
        {
            "name": "Capability queryset",
            "type": "QuerySet",
            "description": "Hierarchical capability tree with parent-child relationships",
        },
        {
            "name": "children relationship",
            "type": "RelatedManager",
            "description": "Reverse FK to child capabilities (one-to-many)",
        },
    ],
    side_effects=[
        "Creates Capability record (used by permission checking middleware)",
        "Used by MembershipCapability join table (assigns capabilities to users/groups)",
        "Queried on every request for permission checking (cached in Redis)",
        "RESTRICT cascade prevents deletion of parent capabilities with children",
        "RESTRICT cascade prevents deletion of clients with active capabilities",
        "Database writes indexed by: capscode, cfor, enable",
    ],
    depends_on=[
        "apps.tenants.models.TenantAwareModel (multi-tenant isolation)",
        "apps.peoples.models.base_model.BaseModel (audit fields: cdtz, mdtz)",
        "apps.peoples.managers.CapabilityManager (custom query methods)",
        "apps.client_onboarding.models.Bt (client organization ForeignKey)",
    ],
    used_by=[
        "apps.peoples.models.membership_model.MembershipCapability (assigns capabilities to users)",
        "apps.peoples.models.group_model.GroupCapability (assigns capabilities to groups)",
        "apps.core.middleware.permission_middleware.PermissionMiddleware (permission checking)",
        "Authorization decorators (@require_capability, @has_permission)",
        "Admin panel (capability management UI)",
        "REST API permission classes (DRF IsAuthorized)",
    ],
    tags=[
        "security",
        "authorization",
        "permissions",
        "rbac",
        "access-control",
        "multi-tenant",
        "hierarchical",
        "platform-scoped",
    ],
    security_notes=(
        "CRITICAL SECURITY BOUNDARIES:\n\n"
        "1. Hierarchical Permission Model:\n"
        "   - Tree structure: Parent capabilities grant access to all child capabilities\n"
        "   - Example: 'admin' parent grants 'admin.users', 'admin.reports', etc.\n"
        "   - WARNING: Granting root-level capability gives access to entire subtree\n"
        "   - Least privilege: Grant most specific (leaf) capabilities, not broad (root) ones\n\n"
        "2. Multi-Tenant Isolation:\n"
        "   - Each capability scoped to client organization (via client FK)\n"
        "   - Tenant A cannot access Tenant B's capabilities\n"
        "   - Global capabilities: client=NULL (system-wide, admin-only)\n"
        "   - ENFORCE: Always filter by client in queries (TenantAwareModel does this automatically)\n\n"
        "3. Platform Type Scoping:\n"
        "   - WEB: Web application permissions\n"
        "   - MOB: Mobile app permissions (different feature set)\n"
        "   - REPORT: Report generation and viewing\n"
        "   - PORTLET: Dashboard widget permissions\n"
        "   - NOC: Network Operations Center (security team)\n"
        "   - Same capability code can exist for different platforms (unique constraint: capscode+cfor+client)\n\n"
        "4. Capability Code Naming Convention:\n"
        "   - Dotted notation: 'resource.action' (e.g., 'user.create', 'report.delete')\n"
        "   - Hierarchical: 'parent.child.grandchild' (e.g., 'admin.users.create')\n"
        "   - ENFORCE: Code review required for new root-level capabilities\n"
        "   - NEVER: Use wildcards in capability codes (creates overly broad permissions)\n\n"
        "5. Enable/Disable Mechanism:\n"
        "   - enable=False: Soft delete (capability exists but not checked)\n"
        "   - Use case: Temporarily revoke capability without deleting assignments\n"
        "   - WARNING: Disabling parent capability disables all children (check recursively)\n"
        "   - Re-enabling: Must manually re-enable each child (not automatic)\n\n"
        "6. RESTRICT Cascade Protection:\n"
        "   - Cannot delete parent capability if children exist (prevents orphaned permissions)\n"
        "   - Cannot delete client if capabilities exist (prevents dangling FKs)\n"
        "   - Deletion workflow: Disable → reassign users → delete children → delete parent\n\n"
        "7. Permission Checking Performance:\n"
        "   - Capabilities queried on EVERY request (via middleware)\n"
        "   - CRITICAL: Cache user capabilities in Redis (5-minute TTL)\n"
        "   - Cache key: f'user:{user_id}:capabilities:{platform}'\n"
        "   - Cache invalidation: On capability assignment/revocation, user logout\n\n"
        "8. Assignment Security:\n"
        "   - Capabilities assigned via MembershipCapability (user-level)\n"
        "   - Or via GroupCapability → Membership (group-level)\n"
        "   - ENFORCE: Admins can only assign capabilities they possess (no privilege escalation)\n"
        "   - Audit: Log all capability assignments/revocations\n\n"
        "9. NEVER:\n"
        "   - Create capability without specifying platform (cfor)\n"
        "   - Assign root-level 'admin' capability to non-admin users\n"
        "   - Use capscode with special characters (security risk in regex matching)\n"
        "   - Trust client-provided capability codes (always validate against database)\n"
        "   - Expose capability tree structure via public API (reveals authorization model)"
    ),
    performance_notes=(
        "Database Indexes:\n"
        "- Single: capscode (permission checking queries)\n"
        "- Single: cfor (platform-scoped queries)\n"
        "- Single: enable (active capabilities only)\n"
        "- Composite unique: capscode+cfor+client (constraint enforcement)\n\n"
        "Query Patterns:\n"
        "- High read volume: Permission checking on every request (~1000s/sec)\n"
        "- Low write volume: Capability creation (admin setup only)\n"
        "- Medium read: Hierarchy traversal (get all children of parent)\n\n"
        "Caching Strategy:\n"
        "- Cache user capabilities: Redis, key=f'user:{id}:caps:{platform}', TTL=5min\n"
        "- Cache capability tree: Redis, key=f'capability:tree:{platform}:{client}', TTL=1hour\n"
        "- Cache invalidation: On capability enable/disable, assignment change\n\n"
        "Performance Optimizations:\n"
        "- Use select_related('parent', 'client') for hierarchy queries (prevent N+1)\n"
        "- Use prefetch_related('children') for tree expansion\n"
        "- Denormalize user capabilities: Store flattened list in cache (avoid tree traversal)\n"
        "- Batch permission checks: Check multiple capabilities in single query\n\n"
        "Scaling Considerations:\n"
        "- Capability table: ~500-2000 rows (small, manageable)\n"
        "- Tree depth: Typically 2-4 levels (shallow, performant)\n"
        "- Cardinality: ~5-20 children per parent (reasonable for queries)\n"
        "- Memory footprint: Entire capability tree fits in Redis (< 1MB per client)"
    ),
    examples=[
        "# Get all capabilities for a platform\n"
        "web_capabilities = Capability.objects.filter(\n"
        "    cfor=Capability.Cfor.WEB,\n"
        "    enable=True\n"
        ").select_related('parent', 'client')\n",
        "# Get capability tree (parents with children)\n"
        "root_capabilities = Capability.objects.filter(\n"
        "    parent__isnull=True,\n"
        "    enable=True\n"
        ").prefetch_related('children')\n"
        "# Recursively traverse tree\n",
        "# Check if user has capability\n"
        "def user_has_capability(user, capscode, platform='WEB'):\n"
        "    # Check cache first\n"
        "    cache_key = f'user:{user.id}:caps:{platform}'\n"
        "    cached_caps = cache.get(cache_key)\n"
        "    if cached_caps:\n"
        "        return capscode in cached_caps\n"
        "    \n"
        "    # Query database\n"
        "    has_cap = user.capabilities.filter(\n"
        "        capscode=capscode,\n"
        "        cfor=platform,\n"
        "        enable=True\n"
        "    ).exists()\n"
        "    return has_cap\n",
        "# Create hierarchical capabilities\n"
        "admin_cap = Capability.objects.create(\n"
        "    capscode='admin',\n"
        "    capsname='Administration',\n"
        "    cfor=Capability.Cfor.WEB,\n"
        "    client=client,\n"
        "    enable=True\n"
        ")\n"
        "user_mgmt_cap = Capability.objects.create(\n"
        "    capscode='admin.users',\n"
        "    capsname='User Management',\n"
        "    parent=admin_cap,  # Child of 'admin'\n"
        "    cfor=Capability.Cfor.WEB,\n"
        "    client=client\n"
        ")\n",
        "# Disable capability (soft delete)\n"
        "capability.enable = False\n"
        "capability.save()\n"
        "# WARNING: Also disable children recursively\n"
        "capability.children.update(enable=False)\n",
    ],
)


class Capability(BaseModel, TenantAwareModel):
    """
    Hierarchical capability model for defining user permissions and access rights.

    Capabilities are organized in a tree structure where each capability can have
    a parent and multiple children, allowing for flexible permission hierarchies
    across different platform types (web, mobile, etc.).

    Attributes:
        capscode (CharField): Unique code identifying the capability
        capsname (CharField): Human-readable name of the capability
        parent (ForeignKey): Parent capability in the hierarchy
        cfor (CharField): Platform type this capability applies to
        client (ForeignKey): Client organization this capability belongs to
        enable (BooleanField): Whether the capability is active
    """

    class Cfor(models.TextChoices):
        """Platform types for capabilities."""
        WEB = ("WEB", "WEB")
        PORTLET = ("PORTLET", "PORTLET")
        REPORT = ("REPORT", "REPORT")
        MOB = ("MOB", "MOB")
        NOC = ("NOC", "NOC")

    capscode = models.CharField(
        _("Capability Code"),
        max_length=50,
        help_text=_("Unique code identifying this capability")
    )

    capsname = models.CharField(
        _("Capability Name"),
        max_length=1000,
        null=True,
        blank=True,
        help_text=_("Human-readable name of the capability")
    )

    parent = models.ForeignKey(
        "self",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="children",
        verbose_name=_("Parent Capability"),
        help_text=_("Parent capability in the hierarchy")
    )

    cfor = models.CharField(
        _("Platform Type"),
        max_length=10,
        default="WEB",
        choices=Cfor.choices,
        help_text=_("Platform type this capability applies to")
    )

    client = models.ForeignKey(
        "client_onboarding.Bt",
        verbose_name=_("Client"),
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        help_text=_("Client organization this capability belongs to")
    )

    enable = models.BooleanField(
        _("Enabled"),
        default=True,
        help_text=_("Whether this capability is active")
    )

    objects = CapabilityManager()

    class Meta(BaseModel.Meta):
        db_table = "capability"
        verbose_name = _("Capability")
        verbose_name_plural = _("Capabilities")
        constraints = [
            models.UniqueConstraint(
                fields=["capscode", "cfor", "client"],
                name="capability_capscode_cfor_client_uk"
            ),
        ]
        indexes = [
            models.Index(fields=['capscode'], name='capability_capscode_idx'),
            models.Index(fields=['cfor'], name='capability_cfor_idx'),
            models.Index(fields=['enable'], name='capability_enable_idx'),
        ]
        get_latest_by = ["mdtz", "cdtz"]

    def __str__(self) -> str:
        """String representation of the capability."""
        return self.capscode

    def get_absolute_url(self):
        """Get URL for capability update view."""
        return f"/people/capabilities/update/{self.pk}/"