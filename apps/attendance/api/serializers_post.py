"""
Post Assignment API Serializers

Comprehensive serializers for:
- Post (duty station) CRUD
- PostAssignment (roster) management
- PostOrderAcknowledgement (compliance)

Author: Claude Code
Created: 2025-11-03
Phase: 2 - Post Assignment Model
"""

from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from django.contrib.gis.geos import Point

from apps.attendance.models import Post, PostAssignment, PostOrderAcknowledgement
from apps.onboarding.models import Bt, Shift
from apps.peoples.models import People


# ==================== POST SERIALIZERS ====================

class PostListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for post lists"""

    site_name = serializers.CharField(source='site.buname', read_only=True)
    shift_name = serializers.CharField(source='shift.shiftname', read_only=True)
    coverage_met = serializers.SerializerMethodField()
    current_assignments_count = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            'id',
            'post_code',
            'post_name',
            'post_type',
            'site',
            'site_name',
            'shift',
            'shift_name',
            'risk_level',
            'active',
            'coverage_required',
            'coverage_met',
            'current_assignments_count',
            'required_guard_count',
            'armed_required',
        ]

    def get_coverage_met(self, obj):
        """Check if coverage requirement is met"""
        is_met, assigned, required = obj.is_coverage_met()
        return {
            'is_met': is_met,
            'assigned_count': assigned,
            'required_count': required,
        }

    def get_current_assignments_count(self, obj):
        """Count of current assignments"""
        from django.utils import timezone
        today = timezone.now().date()
        return obj.assignments.filter(
            assignment_date=today,
            status__in=['SCHEDULED', 'CONFIRMED', 'IN_PROGRESS']
        ).count()


class PostDetailSerializer(serializers.ModelSerializer):
    """Full serializer for post details"""

    site_name = serializers.CharField(source='site.buname', read_only=True)
    shift_name = serializers.CharField(source='shift.shiftname', read_only=True)
    shift_details = serializers.SerializerMethodField()
    zone_name = serializers.CharField(source='zone.zone_name', read_only=True, allow_null=True)
    geofence_name = serializers.CharField(source='geofence.name', read_only=True, allow_null=True)
    required_certifications_list = serializers.SerializerMethodField()
    coverage_status = serializers.SerializerMethodField()
    current_assignments = serializers.SerializerMethodField()
    post_orders_dict = serializers.SerializerMethodField()

    class Meta:
        model = Post
        exclude = ['internal_notes', 'sensitive_data']  # Security: Explicit exclusion instead of '__all__'
        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
            'post_orders_last_updated',
            'post_orders_version',
        ]

    def get_shift_details(self, obj):
        """Get shift details"""
        if not obj.shift:
            return None
        return {
            'id': obj.shift.id,
            'name': obj.shift.shiftname,
            'start_time': obj.shift.starttime.isoformat() if obj.shift.starttime else None,
            'end_time': obj.shift.endtime.isoformat() if obj.shift.endtime else None,
        }

    def get_required_certifications_list(self, obj):
        """Get list of required certification names"""
        return obj.get_required_certifications_list()

    def get_coverage_status(self, obj):
        """Get detailed coverage status"""
        is_met, assigned, required = obj.is_coverage_met()
        return {
            'is_met': is_met,
            'assigned_count': assigned,
            'required_count': required,
            'gap': max(0, required - assigned) if obj.coverage_required else 0,
        }

    def get_current_assignments(self, obj):
        """Get current day's assignments"""
        from django.utils import timezone
        today = timezone.now().date()
        assignments = obj.assignments.filter(
            assignment_date=today
        ).select_related('worker')

        return [{
            'id': a.id,
            'worker_id': a.worker.id,
            'worker_name': a.worker.get_full_name() if hasattr(a.worker, 'get_full_name') else str(a.worker),
            'status': a.status,
            'on_time': a.on_time_checkin,
        } for a in assignments]

    def get_post_orders_dict(self, obj):
        """Get structured post orders"""
        return obj.get_post_orders_dict()


class PostGeoSerializer(GeoFeatureModelSerializer):
    """GeoJSON serializer for map display"""

    site_name = serializers.CharField(source='site.buname', read_only=True)

    class Meta:
        model = Post
        geo_field = 'gps_coordinates'
        fields = [
            'id',
            'post_code',
            'post_name',
            'post_type',
            'site',
            'site_name',
            'risk_level',
            'active',
            'geofence_radius',
        ]


# ==================== POST ASSIGNMENT SERIALIZERS ====================

class PostAssignmentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for assignment lists"""

    worker_name = serializers.SerializerMethodField()
    post_code = serializers.CharField(source='post.post_code', read_only=True)
    post_name = serializers.CharField(source='post.post_name', read_only=True)
    site_name = serializers.CharField(source='site.buname', read_only=True)
    shift_name = serializers.CharField(source='shift.shiftname', read_only=True)

    class Meta:
        model = PostAssignment
        fields = [
            'id',
            'worker',
            'worker_name',
            'post',
            'post_code',
            'post_name',
            'site',
            'site_name',
            'shift',
            'shift_name',
            'assignment_date',
            'start_time',
            'end_time',
            'status',
            'on_time_checkin',
            'hours_worked',
            'is_override',
            'post_orders_acknowledged',
        ]

    def get_worker_name(self, obj):
        """Get worker full name"""
        return obj.worker.get_full_name() if hasattr(obj.worker, 'get_full_name') else str(obj.worker)


class PostAssignmentDetailSerializer(serializers.ModelSerializer):
    """Full serializer for assignment details"""

    worker_name = serializers.SerializerMethodField()
    post_details = serializers.SerializerMethodField()
    site_name = serializers.CharField(source='site.buname', read_only=True)
    shift_details = serializers.SerializerMethodField()
    assigned_by_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()
    can_check_in = serializers.SerializerMethodField()
    can_check_out = serializers.SerializerMethodField()

    class Meta:
        model = PostAssignment
        exclude = ['internal_notes', 'gps_coordinates_raw']  # Security: Explicit exclusion instead of '__all__'
        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
            'status_updated_at',
            'checked_in_at',
            'checked_out_at',
            'hours_worked',
            'late_minutes',
            'on_time_checkin',
        ]

    def get_worker_name(self, obj):
        """Get worker full name"""
        return obj.worker.get_full_name() if hasattr(obj.worker, 'get_full_name') else str(obj.worker)

    def get_post_details(self, obj):
        """Get post details"""
        return {
            'id': obj.post.id,
            'code': obj.post.post_code,
            'name': obj.post.post_name,
            'type': obj.post.post_type,
            'risk_level': obj.post.risk_level,
            'armed_required': obj.post.armed_required,
        }

    def get_shift_details(self, obj):
        """Get shift details"""
        return {
            'id': obj.shift.id,
            'name': obj.shift.shiftname,
            'start_time': obj.start_time.isoformat(),
            'end_time': obj.end_time.isoformat(),
        }

    def get_assigned_by_name(self, obj):
        """Get name of person who created assignment"""
        if obj.assigned_by:
            return obj.assigned_by.get_full_name() if hasattr(obj.assigned_by, 'get_full_name') else str(obj.assigned_by)
        return None

    def get_approved_by_name(self, obj):
        """Get name of approver"""
        if obj.approved_by:
            return obj.approved_by.get_full_name() if hasattr(obj.approved_by, 'get_full_name') else str(obj.approved_by)
        return None

    def get_can_check_in(self, obj):
        """Check if worker can check in"""
        return obj.can_check_in()

    def get_can_check_out(self, obj):
        """Check if worker can check out"""
        return obj.can_check_out()


class PostAssignmentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating post assignments"""

    class Meta:
        model = PostAssignment
        fields = [
            'worker',
            'post',
            'shift',
            'assignment_date',
            'start_time',
            'end_time',
            'approval_required',
            'is_override',
            'override_type',
            'override_reason',
            'notes',
        ]

    def validate(self, data):
        """Validate assignment creation"""
        # Validate override requires reason
        if data.get('is_override') and not data.get('override_reason'):
            raise serializers.ValidationError({
                'override_reason': 'Override reason is required when is_override=True'
            })

        # Validate worker is qualified for post
        post = data.get('post')
        worker = data.get('worker')
        if post and worker:
            qualified, missing = post.is_guard_qualified(worker)
            if not qualified:
                raise serializers.ValidationError({
                    'worker': f'Worker does not meet post requirements: {", ".join(missing)}'
                })

        # Check for duplicate assignment
        existing = PostAssignment.objects.filter(
            worker=data.get('worker'),
            assignment_date=data.get('assignment_date'),
            status__in=['SCHEDULED', 'CONFIRMED', 'IN_PROGRESS']
        ).exists()

        if existing:
            raise serializers.ValidationError(
                'Worker already has an active assignment for this date'
            )

        return data

    def create(self, validated_data):
        """Create assignment with auto-populated fields"""
        # Auto-populate site from post
        if 'post' in validated_data and 'site' not in validated_data:
            validated_data['site'] = validated_data['post'].site

        # Auto-populate times from shift if not provided
        if 'shift' in validated_data:
            if 'start_time' not in validated_data:
                validated_data['start_time'] = validated_data['shift'].starttime
            if 'end_time' not in validated_data:
                validated_data['end_time'] = validated_data['shift'].endtime

        # Auto-populate assigned_by from request context
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['assigned_by'] = request.user

        return super().create(validated_data)


# ==================== POST ORDER ACKNOWLEDGEMENT SERIALIZERS ====================

class PostOrderAcknowledgementSerializer(serializers.ModelSerializer):
    """Serializer for post order acknowledgements"""

    worker_name = serializers.SerializerMethodField()
    post_code = serializers.CharField(source='post.post_code', read_only=True)
    post_name = serializers.CharField(source='post.post_name', read_only=True)
    integrity_verified = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = PostOrderAcknowledgement
        fields = [
            'id',
            'worker',
            'worker_name',
            'post',
            'post_code',
            'post_name',
            'post_assignment',
            'post_orders_version',
            'acknowledged_at',
            'acknowledgement_date',
            'is_valid',
            'is_expired',
            'integrity_verified',
            'post_orders_acknowledged',
            'quiz_taken',
            'quiz_passed',
            'quiz_score',
            'supervisor_verified',
            'acknowledgement_method',
        ]
        read_only_fields = [
            'id',
            'acknowledged_at',
            'acknowledgement_date',
            'post_orders_content_hash',
        ]

    def get_worker_name(self, obj):
        """Get worker full name"""
        return obj.worker.get_full_name() if hasattr(obj.worker, 'get_full_name') else str(obj.worker)

    def get_integrity_verified(self, obj):
        """Check integrity"""
        return obj.verify_integrity()

    def get_is_expired(self, obj):
        """Check if expired"""
        return obj.is_expired()


class PostOrderAcknowledgementCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating acknowledgements (mobile app)"""

    class Meta:
        model = PostOrderAcknowledgement
        fields = [
            'post',
            'post_assignment',
            'device_id',
            'gps_location',
            'acknowledgement_method',
            'time_to_acknowledge_seconds',
            'digital_signature',
            'worker_comments',
            'quiz_taken',
            'quiz_score',
            'quiz_results',
        ]

    def validate(self, data):
        """Validate acknowledgement creation"""
        post = data.get('post')
        request = self.context.get('request')

        # Auto-populate worker from request
        if request and hasattr(request, 'user'):
            data['worker'] = request.user

        # Get current post orders version
        data['post_orders_version'] = post.post_orders_version

        # Validate minimum reading time (optional)
        time_spent = data.get('time_to_acknowledge_seconds', 0)
        if time_spent < 30:  # Less than 30 seconds
            data['minimum_read_time_met'] = False

        # Validate quiz if taken
        if data.get('quiz_taken'):
            score = data.get('quiz_score', 0)
            data['quiz_passed'] = score >= 70  # 70% passing score

        return data

    def create(self, validated_data):
        """Create acknowledgement with auto-populated fields"""
        # Generate content hash
        post = validated_data['post']
        import hashlib
        content = f"{post.post_orders}{post.duties_summary}{post.emergency_procedures}"
        validated_data['post_orders_content_hash'] = hashlib.sha256(content.encode()).hexdigest()

        return super().create(validated_data)


# ==================== NESTED SERIALIZERS ====================

class PostAssignmentNestedSerializer(serializers.ModelSerializer):
    """Nested serializer for including assignments in other responses"""

    worker_name = serializers.SerializerMethodField()
    post_code = serializers.CharField(source='post.post_code', read_only=True)

    class Meta:
        model = PostAssignment
        fields = [
            'id',
            'worker',
            'worker_name',
            'post',
            'post_code',
            'assignment_date',
            'status',
            'on_time_checkin',
        ]

    def get_worker_name(self, obj):
        return obj.worker.get_full_name() if hasattr(obj.worker, 'get_full_name') else str(obj.worker)


# ==================== POST ORDERS FOR MOBILE ====================

class PostOrdersForWorkerSerializer(serializers.Serializer):
    """Serializer for delivering post orders to mobile app"""

    post_id = serializers.IntegerField()
    post_code = serializers.CharField()
    post_name = serializers.CharField()
    post_type = serializers.CharField()
    risk_level = serializers.CharField()

    # Post orders content
    post_orders = serializers.CharField()
    post_orders_version = serializers.IntegerField()
    post_orders_last_updated = serializers.DateTimeField()
    duties_summary = serializers.CharField()
    emergency_procedures = serializers.CharField()
    reporting_instructions = serializers.CharField()

    # Assignment details
    assignment_id = serializers.IntegerField(allow_null=True)
    assignment_date = serializers.DateField()
    shift_start_time = serializers.TimeField()
    shift_end_time = serializers.TimeField()

    # Acknowledgement status
    already_acknowledged = serializers.BooleanField()
    acknowledged_version = serializers.IntegerField(allow_null=True)
    must_acknowledge = serializers.BooleanField()

    # Requirements
    armed_required = serializers.BooleanField()
    required_certifications = serializers.ListField(child=serializers.CharField())

    class Meta:
        fields = [
            'post_id', 'post_name', 'site_name', 'post_code', 'is_active',
            'current_status', 'assigned_person_id', 'assigned_person_name',
            'shift_start_time', 'shift_end_time', 'already_acknowledged',
            'acknowledged_version', 'must_acknowledge', 'armed_required',
            'required_certifications'
        ]  # Security: Explicit field list instead of '__all__'
