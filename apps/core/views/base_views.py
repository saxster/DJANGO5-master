"""
Unified base view classes for consistent functionality across the application
Implements DRY principles and standardized patterns
"""
    ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
)
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.contrib import messages
from django.urls import reverse_lazy
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


class BaseViewMixin:
    """Base mixin providing common functionality for all views"""
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add common context variables
        context.update({
            'app_name': self.get_app_name(),
            'module_name': self.get_module_name(),
            'breadcrumbs': self.get_breadcrumbs(),
            'user_permissions': self.get_user_permissions(),
            'page_title': self.get_page_title(),
        })
        
        return context
    
    def get_app_name(self):
        """Get the current app name for navigation highlighting"""
        return self.request.resolver_match.app_name
    
    def get_module_name(self):
        """Get the current module/section name"""
        return getattr(self, 'module_name', self.__class__.__name__)
    
    def get_breadcrumbs(self):
        """Generate breadcrumb navigation"""
        breadcrumbs = [
            {'title': 'Home', 'url': reverse_lazy('dashboard')}
        ]
        
        # Add app-specific breadcrumbs
        if hasattr(self, 'breadcrumb_trail'):
            breadcrumbs.extend(self.breadcrumb_trail)
        
        return breadcrumbs
    
    def get_user_permissions(self):
        """Get current user's permissions for the view"""
        if not self.request.user.is_authenticated:
            return {}
        
        return {
            'can_create': self.request.user.has_perm(f'{self.get_app_name()}.add_{self.model._meta.model_name}'),
            'can_edit': self.request.user.has_perm(f'{self.get_app_name()}.change_{self.model._meta.model_name}'),
            'can_delete': self.request.user.has_perm(f'{self.get_app_name()}.delete_{self.model._meta.model_name}'),
            'can_view': self.request.user.has_perm(f'{self.get_app_name()}.view_{self.model._meta.model_name}'),
        }
    
    def get_page_title(self):
        """Get page title for the view"""
        if hasattr(self, 'page_title'):
            return self.page_title
        
        if hasattr(self, 'model'):
            return f"{self.model._meta.verbose_name_plural.title()}"
        
        return self.get_module_name()
    
    def log_action(self, action, obj=None, details=None):
        """Log user actions for audit trail"""
        log_entry = {
            'user': self.request.user.username if self.request.user.is_authenticated else 'anonymous',
            'action': action,
            'model': self.model._meta.label if hasattr(self, 'model') else 'unknown',
            'object_id': obj.pk if obj else None,
            'details': details,
            'ip_address': self.request.META.get('REMOTE_ADDR'),
        }
        
        logger.info(f"User action: {log_entry}")


class SearchMixin:
    """Mixin for adding search functionality to list views"""
    
    search_fields = []  # Override in subclass
    
    def get_queryset(self):
        queryset = super().get_queryset()
        search_query = self.request.GET.get('q', '').strip()
        
        if search_query and self.search_fields:
            query = Q()
            for field in self.search_fields:
                query |= Q(**{f'{field}__icontains': search_query})
            queryset = queryset.filter(query)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        return context


class FilterMixin:
    """Mixin for adding filter functionality to list views"""
    
    filter_fields = {}  # Override in subclass: {'field_name': 'display_name'}
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        for field, display_name in self.filter_fields.items():
            value = self.request.GET.get(f'filter_{field}')
            if value:
                queryset = queryset.filter(**{field: value})
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter options to context
        context['filters'] = {}
        for field, display_name in self.filter_fields.items():
            context['filters'][field] = {
                'display_name': display_name,
                'value': self.request.GET.get(f'filter_{field}', ''),
                'options': self.get_filter_options(field)
            }
        
        return context
    
    def get_filter_options(self, field):
        """Get available options for a filter field"""
        # Override in subclass for custom options
        return []


class ExportMixin:
    """Mixin for adding export functionality"""
    
    export_formats = ['csv', 'excel', 'pdf']  # Override as needed
    
    def get(self, request, *args, **kwargs):
        export_format = request.GET.get('export')
        
        if export_format in self.export_formats:
            return self.export_data(export_format)
        
        return super().get(request, *args, **kwargs)
    
    def export_data(self, format):
        """Export data in requested format"""
        # Override in subclass
        raise NotImplementedError("Subclass must implement export_data method")


class CachedViewMixin:
    """Mixin for caching view results"""
    
    cache_timeout = 300  # 5 minutes default
    
    def get_cache_key(self):
        """Generate cache key for the view"""
        key_parts = [
            'view',
            self.request.resolver_match.url_name,
            self.request.user.id if self.request.user.is_authenticated else 'anonymous',
            self.request.GET.urlencode()
        ]
        return ':'.join(str(part) for part in key_parts)
    
    def get(self, request, *args, **kwargs):
        if not self.should_use_cache():
            return super().get(request, *args, **kwargs)
        
        cache_key = self.get_cache_key()
        cached_response = cache.get(cache_key)
        
        if cached_response is not None:
            return cached_response
        
        response = super().get(request, *args, **kwargs)
        cache.set(cache_key, response, self.cache_timeout)
        
        return response
    
    def should_use_cache(self):
        """Determine if caching should be used"""
        return self.request.method == 'GET' and not self.request.user.is_staff


# Concrete base views combining mixins

class BaseListView(LoginRequiredMixin, BaseViewMixin, SearchMixin, FilterMixin, 
                   ExportMixin, CachedViewMixin, ListView):
    """Base list view with all common functionality"""
    
    paginate_by = 25
    template_name = 'base/list.html'  # Override with app-specific template
    context_object_name = 'objects'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add pagination info
        if context.get('is_paginated'):
            context['pagination_info'] = self.get_pagination_info(context['page_obj'])
        
        return context
    
    def get_pagination_info(self, page_obj):
        """Get pagination information for template"""
        return {
            'total_count': page_obj.paginator.count,
            'page_range': page_obj.paginator.get_elided_page_range(
                page_obj.number, 
                on_each_side=2, 
                on_ends=1
            ),
        }


class BaseDetailView(LoginRequiredMixin, BaseViewMixin, DetailView):
    """Base detail view with common functionality"""
    
    template_name = 'base/detail.html'  # Override with app-specific template
    context_object_name = 'object'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add related objects
        context['related_objects'] = self.get_related_objects()
        
        # Log view action
        self.log_action('view', self.object)
        
        return context
    
    def get_related_objects(self):
        """Get related objects for display"""
        # Override in subclass
        return {}


class BaseCreateView(LoginRequiredMixin, PermissionRequiredMixin, BaseViewMixin, CreateView):
    """Base create view with common functionality"""
    
    template_name = 'base/form.html'  # Override with app-specific template
    
    def get_permission_required(self):
        """Get required permission for creating objects"""
        if hasattr(self, 'model'):
            return [f'{self.model._meta.app_label}.add_{self.model._meta.model_name}']
        return []
    
    def form_valid(self, form):
        """Handle valid form submission"""
        # Set created_by if field exists
        if hasattr(form.instance, 'created_by'):
            form.instance.created_by = self.request.user
        
        response = super().form_valid(form)
        
        # Log creation
        self.log_action('create', self.object)
        
        # Add success message
        messages.success(
            self.request, 
            f'{self.model._meta.verbose_name.title()} created successfully!'
        )
        
        return response
    
    def get_success_url(self):
        """Get URL to redirect to after successful creation"""
        if hasattr(self.object, 'get_absolute_url'):
            return self.object.get_absolute_url()
        
        return reverse_lazy(
            f'{self.model._meta.app_label}:{self.model._meta.model_name}_list'
        )


class BaseUpdateView(LoginRequiredMixin, PermissionRequiredMixin, BaseViewMixin, UpdateView):
    """Base update view with common functionality"""
    
    template_name = 'base/form.html'  # Override with app-specific template
    
    def get_permission_required(self):
        """Get required permission for updating objects"""
        if hasattr(self, 'model'):
            return [f'{self.model._meta.app_label}.change_{self.model._meta.model_name}']
        return []
    
    def form_valid(self, form):
        """Handle valid form submission"""
        # Set updated_by if field exists
        if hasattr(form.instance, 'updated_by'):
            form.instance.updated_by = self.request.user
        
        # Store old values for audit
        old_values = {
            field: getattr(self.object, field) 
            for field in form.changed_data
        }
        
        response = super().form_valid(form)
        
        # Log update with changes
        self.log_action('update', self.object, {
            'changed_fields': form.changed_data,
            'old_values': old_values
        })
        
        # Add success message
        messages.success(
            self.request,
            f'{self.model._meta.verbose_name.title()} updated successfully!'
        )
        
        return response


class BaseDeleteView(LoginRequiredMixin, PermissionRequiredMixin, BaseViewMixin, DeleteView):
    """Base delete view with common functionality"""
    
    template_name = 'base/confirm_delete.html'  # Override with app-specific template
    
    def get_permission_required(self):
        """Get required permission for deleting objects"""
        if hasattr(self, 'model'):
            return [f'{self.model._meta.app_label}.delete_{self.model._meta.model_name}']
        return []
    
    def delete(self, request, *args, **kwargs):
        """Handle deletion"""
        self.object = self.get_object()
        
        # Log deletion before it happens
        self.log_action('delete', self.object)
        
        success_url = self.get_success_url()
        self.object.delete()
        
        # Add success message
        messages.success(
            request,
            f'{self.model._meta.verbose_name.title()} deleted successfully!'
        )
        
        return HttpResponseRedirect(success_url)
    
    def get_success_url(self):
        """Get URL to redirect to after successful deletion"""
        return reverse_lazy(
            f'{self.model._meta.app_label}:{self.model._meta.model_name}_list'
        )