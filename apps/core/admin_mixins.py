"""
Optimized Admin Mixins for N+1 Query Prevention

This module provides base admin classes with optimized querysets
to prevent N+1 query issues across all admin interfaces.

Complies with Rule #12 (Database Query Optimization)
"""

from django.contrib import admin


class OptimizedAdminMixin:
    """
    Base mixin for all ModelAdmin classes to prevent N+1 queries

    Usage:
        class MyModelAdmin(OptimizedAdminMixin, admin.ModelAdmin):
            # Define relationships to optimize
            list_select_related = ('foreign_key1', 'foreign_key2')
            list_prefetch_related = ('many_to_many1', 'reverse_fk')
    """

    list_select_related = ()  # Override in subclasses
    list_prefetch_related = ()  # Override in subclasses

    def get_queryset(self, request):
        """Optimize queryset with select_related and prefetch_related"""
        queryset = super().get_queryset(request)

        if self.list_select_related:
            queryset = queryset.select_related(*self.list_select_related)

        if self.list_prefetch_related:
            queryset = queryset.prefetch_related(*self.list_prefetch_related)

        return queryset


class TenantAwareAdminMixin(OptimizedAdminMixin):
    """
    Admin mixin for tenant-aware models
    Automatically includes tenant in select_related
    """

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        # Always include tenant for tenant-aware models
        if hasattr(self.model, 'tenant'):
            queryset = queryset.select_related('tenant')
        return queryset


class UserAwareAdminMixin(OptimizedAdminMixin):
    """
    Admin mixin for models with cuser/muser tracking
    Automatically includes user relationships
    """

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        # Check which user fields exist and optimize accordingly
        user_fields = []
        if hasattr(self.model, 'cuser'):
            user_fields.append('cuser')
        if hasattr(self.model, 'muser'):
            user_fields.append('muser')
        if hasattr(self.model, 'user'):
            user_fields.append('user')

        if user_fields:
            queryset = queryset.select_related(*user_fields)

        return queryset


class FullyOptimizedAdminMixin(TenantAwareAdminMixin, UserAwareAdminMixin):
    """
    Combines all optimization mixins for comprehensive query optimization
    Use this for most admin classes in the application
    """
    pass


# Convenience base classes
class OptimizedModelAdmin(OptimizedAdminMixin, admin.ModelAdmin):
    """Base ModelAdmin with query optimization"""
    pass


class OptimizedTenantModelAdmin(TenantAwareAdminMixin, admin.ModelAdmin):
    """ModelAdmin for tenant-aware models"""
    pass


class OptimizedUserModelAdmin(UserAwareAdminMixin, admin.ModelAdmin):
    """ModelAdmin for user-tracked models"""
    pass


class FullyOptimizedModelAdmin(FullyOptimizedAdminMixin, admin.ModelAdmin):
    """ModelAdmin with all optimizations applied"""
    pass