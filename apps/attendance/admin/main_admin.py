"""
Attendance Module Django Admin Configuration

Provides comprehensive admin interfaces for:
- Posts (duty stations)
- Post Assignments (roster management)
- Post Order Acknowledgements (compliance tracking)
- Attendance Records (PeopleEventlog)
- Geofences

Author: Claude Code
Created: 2025-11-03
"""

from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count, Q

from apps.attendance.models import (
    Post,
    PostAssignment,
    PostOrderAcknowledgement,
    PeopleEventlog,
    Geofence,
)


# ==================== INLINE ADMIN CLASSES ====================

class PostAssignmentInline(admin.TabularInline):
    """Inline for viewing post assignments within Post admin"""
    model = PostAssignment
    extra = 0
    fields = ('worker', 'assignment_date', 'status', 'start_time', 'end_time', 'on_time_checkin')
    readonly_fields = ('on_time_checkin',)
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False  # Create assignments via dedicated interface


class PostOrderAcknowledgementInline(admin.TabularInline):
    """Inline for viewing acknowledgements within Post admin"""
    model = PostOrderAcknowledgement
    extra = 0
    fields = ('worker', 'post_orders_version', 'acknowledged_at', 'is_valid', 'supervisor_verified')
    readonly_fields = ('acknowledged_at', 'is_valid', 'supervisor_verified')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False  # Created automatically by workers


# ==================== POST ADMIN ====================

@admin.register(Post)
class PostAdmin(GISModelAdmin):
    """
    Admin interface for Post (duty station) management.

    Features:
    - List view with site, shift, status, coverage info
    - Filtering by site, shift, type, risk, status
    - Search by post code/name
    - Inline viewing of assignments and acknowledgements
    - Bulk actions for activation/deactivation
    - Color-coded risk levels
    
    N+1 Query Optimization:
    - select_related: site, shift, zone, geofence, created_by, modified_by
    - prefetch_related: required_certifications
    """

    list_display = (
        'post_code',
        'post_name',
        'site',
        'shift',
        'post_type',
        'risk_level_colored',
        'active_status',
        'coverage_status',
        'current_assignments_count',
        'post_orders_version',
    )
    
    # N+1 query optimization
    list_select_related = ['site', 'shift', 'zone', 'geofence', 'created_by', 'modified_by']
    list_prefetch_related = ['required_certifications']

    list_filter = (
        'active',
        'coverage_required',
        'post_type',
        'risk_level',
        'armed_required',
        'temporary',
        'site',
        'shift',
    )

    search_fields = (
        'post_code',
        'post_name',
        'site__buname',
        'shift__shiftname',
    )

    readonly_fields = (
        'post_orders_last_updated',
        'created_at',
        'updated_at',
        'current_assignments_display',
        'coverage_status_detail',
    )

    fieldsets = (
        ('Post Identification', {
            'fields': ('post_code', 'post_name', 'post_type')
        }),
        ('Relationships', {
            'fields': ('site', 'zone', 'shift', 'geofence')
        }),
        ('Location', {
            'fields': ('gps_coordinates', 'geofence_radius', 'floor_level', 'building_section'),
            'classes': ('collapse',),
        }),
        ('Staffing Requirements', {
            'fields': ('required_guard_count', 'armed_required', 'required_certifications')
        }),
        ('Post Orders', {
            'fields': (
                'post_orders',
                'post_orders_version',
                'post_orders_last_updated',
                'duties_summary',
                'emergency_procedures',
                'reporting_instructions'
            ),
            'classes': ('collapse',),
        }),
        ('Security & Risk', {
            'fields': ('risk_level', 'high_value_assets', 'public_access')
        }),
        ('Operational Status', {
            'fields': (
                'active',
                'coverage_required',
                'temporary',
                'temporary_start_date',
                'temporary_end_date'
            )
        }),
        ('Current Coverage', {
            'fields': ('current_assignments_display', 'coverage_status_detail'),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('post_metadata', 'notes'),
            'classes': ('collapse',),
        }),
        ('Audit', {
            'fields': ('created_by', 'modified_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    filter_horizontal = ('required_certifications',)

    inlines = [PostAssignmentInline, PostOrderAcknowledgementInline]

    actions = ['activate_posts', 'deactivate_posts', 'mark_coverage_required', 'mark_coverage_optional']

    list_per_page = 50

    def risk_level_colored(self, obj):
        """Display risk level with color coding"""
        colors = {
            'CRITICAL': 'red',
            'HIGH': 'orange',
            'MEDIUM': 'blue',
            'LOW': 'green',
            'MINIMAL': 'gray',
        }
        color = colors.get(obj.risk_level, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_risk_level_display()
        )
    risk_level_colored.short_description = 'Risk Level'

    def active_status(self, obj):
        """Display active status with icon"""
        if obj.active:
            return format_html('<span style="color: green;">● Active</span>')
        return format_html('<span style="color: red;">○ Inactive</span>')
    active_status.short_description = 'Status'

    def coverage_status(self, obj):
        """Display coverage requirement"""
        is_met, assigned, required = obj.is_coverage_met()
        if not obj.coverage_required:
            return format_html('<span style="color: gray;">Not Required</span>')
        elif is_met:
            return format_html(
                '<span style="color: green;">✓ Covered ({}/{})</span>',
                assigned, required
            )
        else:
            return format_html(
                '<span style="color: red;">⚠ Gap ({}/{})</span>',
                assigned, required
            )
    coverage_status.short_description = 'Coverage'

    def current_assignments_count(self, obj):
        """Count of current assignments"""
        today = timezone.now().date()
        count = obj.assignments.filter(
            assignment_date=today,
            status__in=['SCHEDULED', 'CONFIRMED', 'IN_PROGRESS']
        ).count()
        return count
    current_assignments_count.short_description = 'Today Assigned'

    def current_assignments_display(self, obj):
        """Display current assignments with links"""
        today = timezone.now().date()
        assignments = obj.assignments.filter(
            assignment_date=today
        ).select_related('worker')

        if not assignments:
            return "No assignments for today"

        html = '<ul>'
        for assignment in assignments:
            worker_name = assignment.worker.get_full_name() if hasattr(assignment.worker, 'get_full_name') else str(assignment.worker)
            status_color = {
                'SCHEDULED': 'blue',
                'CONFIRMED': 'cyan',
                'IN_PROGRESS': 'green',
                'COMPLETED': 'gray',
                'NO_SHOW': 'red',
            }.get(assignment.status, 'black')

            html += f'<li><strong>{worker_name}</strong> - <span style="color: {status_color};">{assignment.get_status_display()}</span></li>'
        html += '</ul>'
        return format_html(html)
    current_assignments_display.short_description = 'Current Assignments'

    def coverage_status_detail(self, obj):
        """Detailed coverage status"""
        is_met, assigned, required = obj.is_coverage_met()
        return f"Assigned: {assigned}, Required: {required}, Coverage: {'Met' if is_met else 'GAP'}"
    coverage_status_detail.short_description = 'Coverage Detail'

    def activate_posts(self, request, queryset):
        """Bulk action to activate posts"""
        updated = queryset.update(active=True)
        self.message_user(request, f'{updated} posts activated')
    activate_posts.short_description = 'Activate selected posts'

    def deactivate_posts(self, request, queryset):
        """Bulk action to deactivate posts"""
        updated = queryset.update(active=False)
        self.message_user(request, f'{updated} posts deactivated')
    deactivate_posts.short_description = 'Deactivate selected posts'

    def mark_coverage_required(self, request, queryset):
        """Bulk action to mark posts as requiring coverage"""
        updated = queryset.update(coverage_required=True)
        self.message_user(request, f'{updated} posts marked as requiring coverage')
    mark_coverage_required.short_description = 'Mark coverage required'

    def mark_coverage_optional(self, request, queryset):
        """Bulk action to mark posts as not requiring coverage"""
        updated = queryset.update(coverage_required=False)
        self.message_user(request, f'{updated} posts marked as optional coverage')
    mark_coverage_optional.short_description = 'Mark coverage optional'

    def save_model(self, request, obj, form, change):
        """Auto-populate created_by and modified_by"""
        if not change:
            obj.created_by = request.user
        obj.modified_by = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        """Optimize queryset to prevent N+1 queries."""
        qs = super().get_queryset(request)
        qs = qs.select_related(
            'site',
            'zone',
            'shift',
            'geofence',
            'created_by',
            'modified_by'
        )

        prefetch_fields = getattr(self, 'list_prefetch_related', ['required_certifications'])
        if prefetch_fields:
            qs = qs.prefetch_related(*prefetch_fields)

        return qs


# ==================== POST ASSIGNMENT ADMIN ====================

@admin.register(PostAssignment)
class PostAssignmentAdmin(admin.ModelAdmin):
    """
    Admin interface for PostAssignment (roster) management.

    Features:
    - List view with worker, post, shift, date, status
    - Filtering by date range, status, site, worker
    - Search by worker name, post code
    - Status color coding
    - Bulk actions for status changes
    - Override tracking
    """

    list_display = (
        'assignment_id',
        'worker_link',
        'post_link',
        'site',
        'assignment_date',
        'shift',
        'status_colored',
        'on_time_status',
        'hours_worked',
        'override_indicator',
        'post_orders_ack_status',
    )

    list_filter = (
        'status',
        'assignment_date',
        'site',
        'shift',
        'is_override',
        'on_time_checkin',
        'post_orders_acknowledged',
        'approval_required',
    )

    search_fields = (
        'worker__username',
        'worker__first_name',
        'worker__last_name',
        'post__post_code',
        'post__post_name',
        'site__buname',
    )

    readonly_fields = (
        'status_updated_at',
        'checked_in_at',
        'checked_out_at',
        'hours_worked',
        'late_minutes',
        'created_at',
        'updated_at',
    )

    fieldsets = (
        ('Assignment Details', {
            'fields': ('worker', 'post', 'shift', 'site', 'assignment_date')
        }),
        ('Schedule', {
            'fields': ('start_time', 'end_time')
        }),
        ('Status', {
            'fields': ('status', 'status_updated_at', 'confirmed_at')
        }),
        ('Check-In/Out', {
            'fields': ('checked_in_at', 'checked_out_at', 'attendance_record'),
            'classes': ('collapse',),
        }),
        ('Performance', {
            'fields': ('on_time_checkin', 'late_minutes', 'hours_worked'),
            'classes': ('collapse',),
        }),
        ('Approval', {
            'fields': ('approval_required', 'assigned_by', 'approved_by', 'approved_at', 'approval_notes'),
            'classes': ('collapse',),
        }),
        ('Override', {
            'fields': ('is_override', 'override_type', 'override_reason', 'replaced_assignment'),
            'classes': ('collapse',),
        }),
        ('Post Orders', {
            'fields': (
                'post_orders_acknowledged',
                'post_orders_version_acknowledged',
                'post_orders_acknowledged_at'
            ),
            'classes': ('collapse',),
        }),
        ('Notifications', {
            'fields': ('worker_notified', 'worker_notified_at', 'reminder_sent', 'reminder_sent_at'),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('assignment_metadata', 'notes'),
            'classes': ('collapse',),
        }),
    )

    date_hierarchy = 'assignment_date'

    actions = [
        'mark_confirmed',
        'mark_cancelled',
        'mark_no_show',
        'send_reminders',
    ]

    list_per_page = 50

    def assignment_id(self, obj):
        """Short ID for display"""
        return f"PA-{obj.id}"
    assignment_id.short_description = 'ID'

    def worker_link(self, obj):
        """Link to worker admin"""
        url = reverse('admin:peoples_people_change', args=[obj.worker.id])
        worker_name = obj.worker.get_full_name() if hasattr(obj.worker, 'get_full_name') else str(obj.worker)
        return format_html('<a href="{}">{}</a>', url, worker_name)
    worker_link.short_description = 'Worker'

    def post_link(self, obj):
        """Link to post admin"""
        url = reverse('admin:attendance_post_change', args=[obj.post.id])
        return format_html('<a href="{}">{}</a>', url, obj.post.post_code)
    post_link.short_description = 'Post'

    def status_colored(self, obj):
        """Display status with color coding"""
        color = obj.get_status_display_color()
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_colored.short_description = 'Status'

    def on_time_status(self, obj):
        """Display on-time check-in status"""
        if obj.status in ['SCHEDULED', 'CONFIRMED']:
            return format_html('<span style="color: gray;">Pending</span>')
        elif obj.on_time_checkin:
            return format_html('<span style="color: green;">✓ On Time</span>')
        elif obj.late_minutes:
            return format_html(
                '<span style="color: orange;">⚠ Late ({} min)</span>',
                obj.late_minutes
            )
        else:
            return format_html('<span style="color: gray;">N/A</span>')
    on_time_status.short_description = 'Timeliness'

    def override_indicator(self, obj):
        """Show if assignment is an override"""
        if obj.is_override:
            return format_html(
                '<span style="color: red;" title="{}">⚡ Override</span>',
                obj.override_type
            )
        return ''
    override_indicator.short_description = 'Override'

    def post_orders_ack_status(self, obj):
        """Show post orders acknowledgement status"""
        if obj.post_orders_acknowledged:
            return format_html('<span style="color: green;">✓ Ack v{}</span>', obj.post_orders_version_acknowledged)
        elif obj.status in ['SCHEDULED', 'CONFIRMED']:
            return format_html('<span style="color: orange;">⚠ Pending</span>')
        else:
            return format_html('<span style="color: red;">✗ Not Ack</span>')
    post_orders_ack_status.short_description = 'Post Orders'

    def mark_confirmed(self, request, queryset):
        """Bulk action to mark assignments as confirmed"""
        updated = 0
        for assignment in queryset:
            if assignment.can_check_in():
                assignment.mark_confirmed()
                updated += 1
        self.message_user(request, f'{updated} assignments marked as confirmed')
    mark_confirmed.short_description = 'Mark as confirmed'

    def mark_cancelled(self, request, queryset):
        """Bulk action to cancel assignments"""
        updated = queryset.filter(
            status__in=['SCHEDULED', 'CONFIRMED']
        ).update(status='CANCELLED')
        self.message_user(request, f'{updated} assignments cancelled')
    mark_cancelled.short_description = 'Cancel assignments'

    def mark_no_show(self, request, queryset):
        """Bulk action to mark as no-show"""
        updated = 0
        for assignment in queryset:
            if assignment.status in ['SCHEDULED', 'CONFIRMED']:
                assignment.mark_no_show()
                updated += 1
        self.message_user(request, f'{updated} assignments marked as no-show')
    mark_no_show.short_description = 'Mark as no-show'

    def send_reminders(self, request, queryset):
        """Bulk action to send shift reminders"""
        # TODO: Integrate with notification service
        count = queryset.filter(
            status__in=['SCHEDULED', 'CONFIRMED'],
            reminder_sent=False
        ).count()
        self.message_user(request, f'Reminders queued for {count} assignments (feature pending)')
    send_reminders.short_description = 'Send shift reminders'

    def save_model(self, request, obj, form, change):
        """Auto-populate assigned_by"""
        if not change:
            obj.assigned_by = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        """Optimize queryset to prevent N+1 queries."""
        qs = super().get_queryset(request)
        return qs.select_related(
            'worker',
            'post',
            'post__site',
            'site',
            'shift',
            'attendance_record',
            'assigned_by',
            'approved_by',
            'replaced_assignment'
        )


# ==================== POST ORDER ACKNOWLEDGEMENT ADMIN ====================

@admin.register(PostOrderAcknowledgement)
class PostOrderAcknowledgementAdmin(admin.ModelAdmin):
    """
    Admin interface for PostOrderAcknowledgement compliance tracking.

    Features:
    - List view with worker, post, version, validity
    - Filtering by validity, date, verification status
    - Search by worker/post
    - Bulk verification by supervisors
    - Integrity check display
    """

    list_display = (
        'acknowledgement_id',
        'worker_link',
        'post_link',
        'post_orders_version',
        'acknowledged_at',
        'validity_status',
        'integrity_status',
        'supervisor_verification_status',
        'quiz_result',
    )

    list_filter = (
        'is_valid',
        'supervisor_verified',
        'quiz_passed',
        'acknowledgement_date',
        'acknowledgement_method',
        'post__site',
    )

    search_fields = (
        'worker__username',
        'worker__first_name',
        'worker__last_name',
        'post__post_code',
        'post__post_name',
    )

    readonly_fields = (
        'acknowledged_at',
        'post_orders_content_hash',
        'acknowledgement_date',
        'verified_at',
        'created_at',
        'updated_at',
        'integrity_check_result',
        'gps_location_map_link',
    )

    fieldsets = (
        ('Acknowledgement', {
            'fields': ('worker', 'post', 'post_assignment', 'post_orders_version')
        }),
        ('Timestamp', {
            'fields': ('acknowledged_at', 'acknowledgement_date')
        }),
        ('Integrity', {
            'fields': ('post_orders_content_hash', 'integrity_check_result'),
            'classes': ('collapse',),
        }),
        ('Device & Location', {
            'fields': (
                'device_id',
                'ip_address',
                'user_agent',
                'gps_location',
                'gps_location_map_link'
            ),
            'classes': ('collapse',),
        }),
        ('Method & Timing', {
            'fields': (
                'acknowledgement_method',
                'time_to_acknowledge_seconds',
                'minimum_read_time_met'
            ),
            'classes': ('collapse',),
        }),
        ('Quiz/Comprehension', {
            'fields': ('quiz_taken', 'quiz_score', 'quiz_passed', 'quiz_results'),
            'classes': ('collapse',),
        }),
        ('Signature', {
            'fields': ('digital_signature', 'signature_verified'),
            'classes': ('collapse',),
        }),
        ('Statement', {
            'fields': ('acknowledgement_statement', 'worker_comments'),
            'classes': ('collapse',),
        }),
        ('Validity', {
            'fields': ('is_valid', 'valid_from', 'valid_until')
        }),
        ('Supervisor Verification', {
            'fields': ('supervisor_verified', 'verified_by', 'verified_at')
        }),
        ('Metadata', {
            'fields': ('acknowledgement_metadata',),
            'classes': ('collapse',),
        }),
    )

    date_hierarchy = 'acknowledgement_date'

    actions = ['verify_acknowledgements', 'invalidate_acknowledgements']

    list_per_page = 50

    def acknowledgement_id(self, obj):
        """Short ID for display"""
        return f"ACK-{obj.id}"
    acknowledgement_id.short_description = 'ID'

    def worker_link(self, obj):
        """Link to worker admin"""
        url = reverse('admin:peoples_people_change', args=[obj.worker.id])
        worker_name = obj.worker.get_full_name() if hasattr(obj.worker, 'get_full_name') else str(obj.worker)
        return format_html('<a href="{}">{}</a>', url, worker_name)
    worker_link.short_description = 'Worker'

    def post_link(self, obj):
        """Link to post admin"""
        url = reverse('admin:attendance_post_change', args=[obj.post.id])
        return format_html('<a href="{}">{}</a>', url, obj.post.post_code)
    post_link.short_description = 'Post'

    def validity_status(self, obj):
        """Display validity with color"""
        if not obj.is_valid:
            return format_html('<span style="color: red;">✗ Invalid</span>')
        elif obj.is_expired():
            return format_html('<span style="color: orange;">⚠ Expired</span>')
        else:
            return format_html('<span style="color: green;">✓ Valid</span>')
    validity_status.short_description = 'Validity'

    def integrity_status(self, obj):
        """Display integrity verification status"""
        if obj.verify_integrity():
            return format_html('<span style="color: green;">✓ Verified</span>')
        else:
            return format_html('<span style="color: red;">⚠ Hash Mismatch</span>')
    integrity_status.short_description = 'Integrity'

    def supervisor_verification_status(self, obj):
        """Display supervisor verification"""
        if obj.supervisor_verified:
            verifier = obj.verified_by.get_full_name() if obj.verified_by and hasattr(obj.verified_by, 'get_full_name') else 'Unknown'
            return format_html(
                '<span style="color: green;">✓ {}</span>',
                verifier
            )
        return format_html('<span style="color: gray;">Pending</span>')
    supervisor_verification_status.short_description = 'Supervisor'

    def quiz_result(self, obj):
        """Display quiz result"""
        if not obj.quiz_taken:
            return format_html('<span style="color: gray;">N/A</span>')
        elif obj.quiz_passed:
            return format_html('<span style="color: green;">✓ {}%</span>', obj.quiz_score)
        else:
            return format_html('<span style="color: red;">✗ {}%</span>', obj.quiz_score)
    quiz_result.short_description = 'Quiz'

    def integrity_check_result(self, obj):
        """Display detailed integrity check"""
        verified = obj.verify_integrity()
        if verified:
            return format_html('<span style="color: green; font-weight: bold;">✓ Post orders unchanged since acknowledgement</span>')
        else:
            return format_html('<span style="color: red; font-weight: bold;">⚠ WARNING: Post orders have been modified since acknowledgement!</span>')
    integrity_check_result.short_description = 'Integrity Check'

    def gps_location_map_link(self, obj):
        """Link to view GPS location on map"""
        if obj.gps_location and 'lat' in obj.gps_location and 'lng' in obj.gps_location:
            lat = obj.gps_location['lat']
            lng = obj.gps_location['lng']
            return format_html(
                '<a href="https://www.google.com/maps?q={},{}" target="_blank">View on Map ({}, {})</a>',
                lat, lng, lat, lng
            )
        return 'No GPS data'
    gps_location_map_link.short_description = 'GPS Location'

    def verify_acknowledgements(self, request, queryset):
        """Bulk action for supervisor verification"""
        updated = 0
        for ack in queryset:
            if not ack.supervisor_verified:
                ack.verify_by_supervisor(request.user)
                updated += 1
        self.message_user(request, f'{updated} acknowledgements verified')
    verify_acknowledgements.short_description = 'Verify acknowledgements'

    def invalidate_acknowledgements(self, request, queryset):
        """Bulk action to invalidate acknowledgements"""
        updated = 0
        for ack in queryset:
            if ack.is_valid:
                ack.invalidate(reason="Invalidated by supervisor")
                updated += 1
        self.message_user(request, f'{updated} acknowledgements invalidated')
    invalidate_acknowledgements.short_description = 'Invalidate acknowledgements'

    def get_queryset(self, request):
        """Optimize queryset to prevent N+1 queries."""
        qs = super().get_queryset(request)
        return qs.select_related(
            'worker',
            'post',
            'post__site',
            'post_assignment',
            'verified_by'
        )


# ==================== PEOPLE EVENT LOG ADMIN (ENHANCED) ====================

@admin.register(PeopleEventlog)
class PeopleEventlogAdmin(admin.ModelAdmin):
    """
    Enhanced admin for attendance records with post tracking.
    """

    list_display = (
        'id',
        'worker_name',
        'site',
        'post_code',
        'shift',
        'datefor',
        'punchintime',
        'punchouttime',
        'geofence_status',
        'validation_status',
    )

    list_filter = (
        'datefor',
        'bu',
        'shift',
        'post',
    )

    search_fields = (
        'people__username',
        'people__first_name',
        'people__last_name',
        'bu__buname',
        'post__post_code',
    )

    readonly_fields = ('created_at', 'updated_at', 'cdtz')

    date_hierarchy = 'datefor'

    list_per_page = 50

    def worker_name(self, obj):
        """Display worker name"""
        if obj.people:
            return obj.people.get_full_name() if hasattr(obj.people, 'get_full_name') else str(obj.people)
        return 'N/A'
    worker_name.short_description = 'Worker'

    def site(self, obj):
        """Display site name"""
        return obj.bu.buname if obj.bu else 'N/A'
    site.short_description = 'Site'

    def post_code(self, obj):
        """Display post code"""
        return obj.post.post_code if obj.post else 'N/A'
    post_code.short_description = 'Post'

    def geofence_status(self, obj):
        """Display geofence validation status"""
        if not obj.peventlogextras:
            return format_html('<span style="color: gray;">N/A</span>')

        verified = obj.peventlogextras.get('verified_in', False)
        if verified:
            return format_html('<span style="color: green;">✓ Inside</span>')
        else:
            distance = obj.peventlogextras.get('distance_in', 'unknown')
            return format_html(
                '<span style="color: orange;">⚠ Outside ({}m)</span>',
                distance
            )
    geofence_status.short_description = 'Geofence'

    def validation_status(self, obj):
        """Display validation status"""
        if not obj.peventlogextras:
            return format_html('<span style="color: gray;">Legacy</span>')

        validated = obj.peventlogextras.get('validation_passed', False)
        if validated:
            return format_html('<span style="color: green;">✓ Validated</span>')
        else:
            return format_html('<span style="color: red;">✗ Failed</span>')
    validation_status.short_description = 'Validation'

    def get_queryset(self, request):
        """Optimize queryset to prevent N+1 queries."""
        qs = super().get_queryset(request)
        return qs.select_related(
            'people',
            'bu',
            'shift',
            'post',
            'post__site'
        )


# ==================== GEOFENCE ADMIN ====================

@admin.register(Geofence)
class GeofenceAdmin(GISModelAdmin):
    """Admin interface for Geofence management"""

    list_display = ('name', 'geofence_type', 'bu', 'is_active', 'posts_count')
    list_filter = ('geofence_type', 'is_active', 'bu')
    search_fields = ('name', 'bu__buname')
    list_per_page = 50

    def posts_count(self, obj):
        """Count of posts using this geofence"""
        count = obj.posts.count()
        return format_html('<span>{}</span>', count)
    posts_count.short_description = 'Posts Using'

    def get_queryset(self, request):
        """Optimize queryset to prevent N+1 queries."""
        qs = super().get_queryset(request)
        return qs.select_related('bu')


__all__ = [
    'PostAdmin',
    'PostAssignmentAdmin',
    'PostOrderAcknowledgementAdmin',
    'PeopleEventlogAdmin',
    'GeofenceAdmin',
]
