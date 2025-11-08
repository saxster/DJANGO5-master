"""
Admin Help Topic Admin Interface

Provides rich admin interface for managing help content with:
- Rich text editing
- Preview functionality
- Bulk import from CSV
- Usage analytics dashboard

Following .claude/rules.md:
- Rule #7: Settings files <200 lines
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import path, reverse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Count, Avg
from unfold.decorators import display
import csv
from io import TextIOWrapper

from apps.core.admin.base_admin import IntelliWizModelAdmin
from apps.core.models.admin_help import AdminHelpTopic


@admin.register(AdminHelpTopic)
class AdminHelpTopicAdmin(IntelliWizModelAdmin):
    """Admin interface for help topics with analytics."""
    
    list_display = [
        'feature_name',
        'category_badge',
        'difficulty_badge',
        'view_count_display',
        'helpful_count_display',
        'is_active_badge',
        'created_display',
    ]
    
    list_filter = [
        'category',
        'difficulty_level',
        'is_active',
        'created_at',
    ]
    
    search_fields = [
        'feature_name',
        'short_description',
        'detailed_explanation',
        'keywords',
    ]
    
    readonly_fields = [
        'view_count',
        'helpful_count',
        'created_at',
        'updated_at',
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'category',
                'feature_name',
                'difficulty_level',
                'is_active',
            )
        }),
        ('Content', {
            'fields': (
                'short_description',
                'detailed_explanation',
                'how_to_use',
            ),
            'description': 'Write in simple, friendly language - avoid jargon!'
        }),
        ('Examples & Benefits', {
            'fields': (
                'use_cases',
                'advantages',
            ),
            'classes': ('collapse',),
        }),
        ('Resources', {
            'fields': (
                'video_url',
                'keywords',
            ),
            'classes': ('collapse',),
        }),
        ('Analytics', {
            'fields': (
                'view_count',
                'helpful_count',
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',),
        }),
    )
    
    list_per_page = 25
    list_select_related = ['tenant']
    
    def get_urls(self):
        """Add custom URLs for bulk import and analytics."""
        urls = super().get_urls()
        custom_urls = [
            path(
                'bulk-import/',
                self.admin_site.admin_view(self.bulk_import_view),
                name='core_adminhelptopic_bulk_import',
            ),
            path(
                'analytics/',
                self.admin_site.admin_view(self.analytics_view),
                name='core_adminhelptopic_analytics',
            ),
        ]
        return custom_urls + urls
    
    @display(description="Category", label=True)
    def category_badge(self, obj):
        """Display category as colored badge."""
        colors = {
            'command_center': 'primary',
            'workflows': 'info',
            'approvals': 'warning',
            'views': 'success',
            'reports': 'secondary',
            'notifications': 'danger',
            'scheduling': 'info',
            'team': 'success',
            'settings': 'secondary',
        }
        color = colors.get(obj.category, 'info')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color,
            obj.get_category_display()
        )
    
    @display(description="Difficulty", label=True)
    def difficulty_badge(self, obj):
        """Display difficulty as colored badge."""
        colors = {
            'beginner': 'success',
            'intermediate': 'warning',
            'advanced': 'danger',
        }
        icons = {
            'beginner': '⭐',
            'intermediate': '⭐⭐',
            'advanced': '⭐⭐⭐',
        }
        color = colors.get(obj.difficulty_level, 'info')
        icon = icons.get(obj.difficulty_level, '')
        return format_html(
            '<span class="badge badge-{}">{} {}</span>',
            color,
            icon,
            obj.get_difficulty_level_display().split(' - ')[0]
        )
    
    @display(description="Views", ordering='view_count')
    def view_count_display(self, obj):
        """Display view count with formatting."""
        if obj.view_count > 1000:
            return f"{obj.view_count / 1000:.1f}k"
        return str(obj.view_count)
    
    @display(description="Helpful", ordering='helpful_count')
    def helpful_count_display(self, obj):
        """Display helpful count with percentage."""
        if obj.view_count > 0:
            percentage = (obj.helpful_count / obj.view_count) * 100
            return format_html(
                '{} <span style="color: gray;">({:.0f}%)</span>',
                obj.helpful_count,
                percentage
            )
        return str(obj.helpful_count)
    
    @display(description="Active", boolean=True)
    def is_active_badge(self, obj):
        """Display active status."""
        return obj.is_active
    
    def bulk_import_view(self, request):
        """Bulk import help topics from CSV."""
        if request.method == 'POST':
            csv_file = request.FILES.get('csv_file')
            
            if not csv_file:
                messages.error(request, 'Please upload a CSV file')
                return redirect('..')
            
            if not csv_file.name.endswith('.csv'):
                messages.error(request, 'File must be a CSV')
                return redirect('..')
            
            try:
                file_data = TextIOWrapper(csv_file.file, encoding='utf-8')
                reader = csv.DictReader(file_data)
                
                created_count = 0
                for row in reader:
                    # Parse arrays from comma-separated strings
                    use_cases = [
                        uc.strip() for uc in row.get('use_cases', '').split('|')
                        if uc.strip()
                    ]
                    advantages = [
                        adv.strip() for adv in row.get('advantages', '').split('|')
                        if adv.strip()
                    ]
                    keywords = [
                        kw.strip() for kw in row.get('keywords', '').split(',')
                        if kw.strip()
                    ]
                    
                    AdminHelpTopic.objects.create(
                        category=row['category'],
                        feature_name=row['feature_name'],
                        short_description=row['short_description'],
                        detailed_explanation=row['detailed_explanation'],
                        use_cases=use_cases,
                        advantages=advantages,
                        how_to_use=row.get('how_to_use', ''),
                        video_url=row.get('video_url', ''),
                        keywords=keywords,
                        difficulty_level=row.get('difficulty_level', 'beginner'),
                    )
                    created_count += 1
                
                messages.success(
                    request,
                    f'Successfully imported {created_count} help topics'
                )
                return redirect('..')
                
            except Exception as e:
                messages.error(request, f'Error importing CSV: {str(e)}')
                return redirect('..')
        
        return render(
            request,
            'admin/core/adminhelptopic/bulk_import.html',
            {
                'title': 'Bulk Import Help Topics',
                'opts': self.model._meta,
            }
        )
    
    def analytics_view(self, request):
        """Display usage analytics dashboard."""
        stats = AdminHelpTopic.objects.aggregate(
            total_topics=Count('id'),
            total_views=Count('view_count'),
            avg_helpful_rate=Avg('helpful_count'),
        )
        
        popular_topics = (
            AdminHelpTopic.objects
            .filter(is_active=True)
            .order_by('-view_count')[:10]
        )
        
        by_category = (
            AdminHelpTopic.objects
            .values('category')
            .annotate(
                count=Count('id'),
                total_views=Count('view_count')
            )
            .order_by('-total_views')
        )
        
        return render(
            request,
            'admin/core/adminhelptopic/analytics.html',
            {
                'title': 'Help Topics Analytics',
                'opts': self.model._meta,
                'stats': stats,
                'popular_topics': popular_topics,
                'by_category': by_category,
            }
        )
