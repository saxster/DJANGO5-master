"""
People model admin interface with privacy-safe display.

Features:
    - Import/Export support for bulk operations
    - Privacy-safe masked fields (email, mobile, password)
    - Optimized querysets with select_related
    - GDPR compliant display

Security:
    - Sensitive fields masked in list display
    - Password never displayed (bullets only)
    - Prevents shoulder-surfing attacks
"""

from django.contrib import admin
from import_export.admin import ImportExportModelAdmin

from apps.peoples import models as pm
from .import_export_resources import PeopleResource


@admin.register(pm.People)
class PeopleAdmin(ImportExportModelAdmin):
    """
    Admin interface for People with privacy-safe display.

    Security Features:
        - Sensitive fields (email, mobno, password) are masked in list display
        - Uses callable methods to prevent decrypted value exposure
        - Complies with GDPR privacy requirements
        - Prevents shoulder-surfing and screenshot leaks

    Privacy Compliance:
        - Email: Shows first 2 chars + domain TLD only
        - Mobile: Shows first 3 and last 2 digits only
        - Password: Never displayed (always shows bullets)
    """

    resource_class = PeopleResource

    list_display = [
        "id",
        "peoplecode",
        "peoplename",
        "loginid",
        "mobno_masked",  # Privacy-safe display
        "email_masked",  # Privacy-safe display
        "password_masked",  # Privacy-safe display (never shows actual password)
        "gender",
        "peopletype",
        "isadmin",
        "client",
        "cuser",
        "muser",
        "cdtz",
        "mdtz",
    ]

    list_display_links = ["peoplecode", "peoplename"]
    list_select_related = (
        "cuser",
        "muser",
        "tenant",
    )
    search_fields = [
        "peoplecode",
        "peoplename",
        "loginid",
        "email",
        "mobno",
    ]
    list_filter = [
        "enable",
        "isadmin",
        "is_staff",
        "isverified",
    ]

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("loginid", "password1", "password2"),
            },
        ),
    )

    fieldsets = (
        (
            "Create/Update People",
            {
                "fields": [
                    "peoplecode",
                    "peoplename",
                    "loginid",
                    "mobno",
                    "email",
                    "bu",
                    "dateofjoin",
                    "dateofbirth",
                    "gender",
                    "enable",
                    "tenant",
                    "isadmin",
                    "client",
                ]
            },
        ),
        (
            "Add/Remove Permissions",
            {
                "fields": ("is_staff", "is_superuser", "groups", "user_permissions"),
            },
        ),
    )

    def get_resource_kwargs(self, request, *args, **kwargs):
        """Pass request context to resource."""
        return {"request": request}

    def get_queryset(self, request):
        """Optimize queryset with select_related for real foreign keys only."""
        return pm.People.objects.select_related(
            "cuser",
            "muser",
            "tenant",
        ).all()

    def email_masked(self, obj):
        """Display masked email (GDPR compliant)."""
        if not obj.email:
            return "-"
        email_str = str(obj.email)
        if "@" not in email_str or "*" in email_str:
            return email_str
        local, domain = email_str.split("@", 1)
        masked_local = "****" if len(local) <= 2 else f"{local[:2]}****"
        domain_parts = domain.split(".")
        masked_domain = f"***.{domain_parts[-1]}" if len(domain_parts) > 1 else "***"
        return f"{masked_local}@{masked_domain}"

    email_masked.short_description = "Email"
    email_masked.admin_order_field = "email"

    def mobno_masked(self, obj):
        """Display masked mobile number (GDPR compliant)."""
        if not obj.mobno:
            return "-"
        mobno_str = str(obj.mobno)
        if "*" in mobno_str:
            return mobno_str
        if len(mobno_str) <= 5:
            return "********"
        return f"{mobno_str[:3]}****{mobno_str[-2:]}"

    mobno_masked.short_description = "Mobile"
    mobno_masked.admin_order_field = "mobno"

    def password_masked(self, obj):
        """Never display password - always show bullets."""
        return "••••••••" if obj.password else "-"

    password_masked.short_description = "Password"
