"""
Enhanced GraphQL Schema with DataLoader Integration

Optimized GraphQL schema with performance improvements.
"""

import graphene
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from graphql_jwt.decorators import login_required
from graphene import relay
from django.db.models import Q
import logging

from apps.api.graphql.dataloaders import get_loaders
from apps.peoples.models import People, Pgroup
from apps.activity.models.asset_model import Asset
from apps.activity.models.job_model import Job, Jobneed

logger = logging.getLogger('graphql.schema')


class OptimizedDjangoObjectType(DjangoObjectType):
    """
    Base class for optimized Django GraphQL types.
    """
    
    class Meta:
        abstract = True
    
    @classmethod
    def get_queryset(cls, queryset, info):
        """
        Optimize queryset with select_related and prefetch_related.
        """
        # Override in subclasses to add optimizations
        return queryset


class PeopleType(OptimizedDjangoObjectType):
    """
    Optimized People type with DataLoader support.
    """
    
    groups = graphene.List(lambda: PgroupType)
    group_count = graphene.Int()
    full_name = graphene.String()
    jobs = graphene.List(lambda: JobType)
    job_count = graphene.Int()
    
    class Meta:
        model = People
        fields = '__all__'
        interfaces = (relay.Node,)
        filter_fields = {
            'email': ['exact', 'icontains'],
            'first_name': ['exact', 'icontains'],
            'last_name': ['exact', 'icontains'],
            'is_active': ['exact'],
            'created_at': ['exact', 'lte', 'gte'],
        }
    
    @classmethod
    def get_queryset(cls, queryset, info):
        """
        Optimize queryset for People.
        """
        return queryset.select_related('shift', 'bt').prefetch_related('groups')
    
    def resolve_groups(self, info):
        """
        Resolve groups using DataLoader.
        """
        loaders = get_loaders(info)
        return loaders['groups_by_person'].load(self.id)
    
    def resolve_group_count(self, info):
        """
        Resolve group count using DataLoader.
        """
        loaders = get_loaders(info)
        return loaders['people_count_by_group'].load(self.id)
    
    def resolve_full_name(self, info):
        """
        Resolve full name.
        """
        return f"{self.first_name} {self.last_name}".strip()
    
    def resolve_jobs(self, info):
        """
        Resolve jobs assigned to this person using DataLoader.
        """
        loaders = get_loaders(info)
        return loaders['jobs_by_people'].load(self.id)

    def resolve_job_count(self, info):
        """
        Resolve job count using DataLoader.
        """
        loaders = get_loaders(info)
        return loaders['job_count_by_people'].load(self.id)


class PgroupType(OptimizedDjangoObjectType):
    """
    Optimized Pgroup type with DataLoader support.
    """
    
    members = graphene.List(PeopleType)
    member_count = graphene.Int()
    
    class Meta:
        model = Pgroup
        fields = '__all__'
        interfaces = (relay.Node,)
        filter_fields = ['name', 'is_active']
    
    def resolve_members(self, info):
        """
        Resolve members using DataLoader.
        """
        loaders = get_loaders(info)
        return loaders['people_by_group'].load(self.id)
    
    def resolve_member_count(self, info):
        """
        Resolve member count using DataLoader.
        """
        loaders = get_loaders(info)
        return loaders['people_count_by_group'].load(self.id)


class AssetType(OptimizedDjangoObjectType):
    """
    Optimized Asset type with DataLoader support.
    """
    
    jobs = graphene.List(lambda: JobType)
    job_count = graphene.Int()
    location_name = graphene.String()
    
    class Meta:
        model = Asset
        fields = '__all__'
        interfaces = (relay.Node,)
        filter_fields = {
            'name': ['exact', 'icontains'],
            'is_active': ['exact'],
            'location': ['exact'],
        }
    
    @classmethod
    def get_queryset(cls, queryset, info):
        """
        Optimize queryset for Asset.
        """
        return queryset.select_related('location', 'created_by')
    
    def resolve_jobs(self, info):
        """
        Resolve jobs using DataLoader.
        """
        loaders = get_loaders(info)
        return loaders['jobs_by_asset'].load(self.id)
    
    def resolve_job_count(self, info):
        """
        Resolve job count using DataLoader.
        """
        loaders = get_loaders(info)
        return loaders['job_count_by_asset'].load(self.id)
    
    def resolve_location_name(self, info):
        """
        Resolve location name.
        """
        return self.location.name if self.location else None


class JobType(OptimizedDjangoObjectType):
    """
    Optimized Job type with DataLoader support.
    """
    
    jobneed_details = graphene.Field(lambda: JobneedType)
    asset_details = graphene.Field(AssetType)
    assigned_person = graphene.Field(PeopleType)
    
    class Meta:
        model = Job
        fields = '__all__'
        interfaces = (relay.Node,)
        filter_fields = {
            'status': ['exact'],
            'created_at': ['exact', 'lte', 'gte'],
            'asset': ['exact'],
            'people': ['exact'],
        }
    
    @classmethod
    def get_queryset(cls, queryset, info):
        """
        Optimize queryset for Job.
        """
        return queryset.select_related('jobneed', 'asset', 'people')
    
    def resolve_jobneed_details(self, info):
        """
        Resolve jobneed using DataLoader.
        """
        loaders = get_loaders(info)
        return loaders['jobneed_by_job'].load(self.id)
    
    def resolve_asset_details(self, info):
        """
        Resolve asset using DataLoader.
        """
        loaders = get_loaders(info)
        return loaders['asset_by_id'].load(self.asset_id)
    
    def resolve_assigned_person(self, info):
        """
        Resolve assigned person using DataLoader.
        """
        loaders = get_loaders(info)
        return loaders['people_by_id'].load(self.people_id) if self.people_id else None


class JobneedType(OptimizedDjangoObjectType):
    """
    Optimized Jobneed type.
    """
    
    jobs = graphene.List(JobType)
    job_count = graphene.Int()
    
    class Meta:
        model = Jobneed
        fields = '__all__'
        interfaces = (relay.Node,)
    
    def resolve_jobs(self, info):
        """
        Resolve related jobs using DataLoader.
        """
        loaders = get_loaders(info)
        return loaders['jobs_by_jobneed'].load(self.id)

    def resolve_job_count(self, info):
        """
        Resolve job count using DataLoader.
        """
        loaders = get_loaders(info)
        return loaders['job_count_by_jobneed'].load(self.id)


class Query(graphene.ObjectType):
    """
    Enhanced GraphQL Query with optimizations.
    """
    
    # Single object queries
    person = graphene.Field(PeopleType, id=graphene.Int(required=True))
    group = graphene.Field(PgroupType, id=graphene.Int(required=True))
    asset = graphene.Field(AssetType, id=graphene.Int(required=True))
    job = graphene.Field(JobType, id=graphene.Int(required=True))
    
    # List queries with filtering
    all_people = DjangoFilterConnectionField(PeopleType)
    all_groups = DjangoFilterConnectionField(PgroupType)
    all_assets = DjangoFilterConnectionField(AssetType)
    all_jobs = DjangoFilterConnectionField(JobType)
    
    # Custom queries
    search_people = graphene.List(
        PeopleType,
        query=graphene.String(required=True),
        limit=graphene.Int(default_value=10)
    )
    active_people = graphene.List(PeopleType)
    my_profile = graphene.Field(PeopleType)
    
    # Statistics
    statistics = graphene.JSONString()
    
    @login_required
    def resolve_person(self, info, id):
        """
        Resolve single person using DataLoader.
        """
        loaders = get_loaders(info)
        return loaders['people_by_id'].load(id)
    
    @login_required
    def resolve_group(self, info, id):
        """
        Resolve single group.
        """
        return Pgroup.objects.get(id=id)
    
    @login_required
    def resolve_asset(self, info, id):
        """
        Resolve single asset using DataLoader.
        """
        loaders = get_loaders(info)
        return loaders['asset_by_id'].load(id)
    
    @login_required
    def resolve_job(self, info, id):
        """
        Resolve single job.
        """
        return Job.objects.select_related('jobneed', 'asset', 'people').get(id=id)
    
    @login_required
    def resolve_search_people(self, info, query, limit):
        """
        Search people with query optimization.
        """
        q = Q(first_name__icontains=query) | \
            Q(last_name__icontains=query) | \
            Q(email__icontains=query) | \
            Q(employee_code__icontains=query)
        
        return People.objects.filter(q).select_related('shift', 'bt')[:limit]
    
    @login_required
    def resolve_active_people(self, info):
        """
        Get all active people.
        """
        return People.objects.filter(
            is_active=True
        ).select_related('shift', 'bt').prefetch_related('groups')
    
    @login_required
    def resolve_my_profile(self, info):
        """
        Get current user's profile.
        """
        user = info.context.user
        if user.is_authenticated:
            try:
                return People.objects.get(user=user)
            except People.DoesNotExist:
                return None
        return None
    
    @login_required
    def resolve_statistics(self, info):
        """
        Get system statistics.
        """
        from django.utils import timezone
        from datetime import timedelta
        
        stats = {
            'people': {
                'total': People.objects.count(),
                'active': People.objects.filter(is_active=True).count(),
                'recent': People.objects.filter(
                    created_at__gte=timezone.now() - timedelta(days=30)
                ).count(),
            },
            'groups': {
                'total': Pgroup.objects.count(),
                'active': Pgroup.objects.filter(is_active=True).count(),
            },
            'assets': {
                'total': Asset.objects.count(),
                'active': Asset.objects.filter(is_active=True).count(),
            },
            'jobs': {
                'total': Job.objects.count(),
                'pending': Job.objects.filter(status='pending').count(),
                'completed': Job.objects.filter(status='completed').count(),
            }
        }
        
        return stats


class CreatePerson(graphene.Mutation):
    """
    Mutation to create a new person.
    """
    
    class Arguments:
        first_name = graphene.String(required=True)
        last_name = graphene.String(required=True)
        email = graphene.String(required=True)
        employee_code = graphene.String(required=True)
        mobile = graphene.String()
        is_active = graphene.Boolean(default_value=True)
    
    person = graphene.Field(PeopleType)
    success = graphene.Boolean()
    errors = graphene.List(graphene.String)
    
    @login_required
    def mutate(self, info, **kwargs):
        """
        Create a new person.
        """
        try:
            person = People.objects.create(**kwargs)
            return CreatePerson(person=person, success=True, errors=[])
        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Error creating person: {e}")
            return CreatePerson(person=None, success=False, errors=[str(e)])


class UpdatePerson(graphene.Mutation):
    """
    Mutation to update a person.
    """
    
    class Arguments:
        id = graphene.Int(required=True)
        first_name = graphene.String()
        last_name = graphene.String()
        email = graphene.String()
        mobile = graphene.String()
        is_active = graphene.Boolean()
    
    person = graphene.Field(PeopleType)
    success = graphene.Boolean()
    errors = graphene.List(graphene.String)
    
    @login_required
    def mutate(self, info, id, **kwargs):
        """
        Update a person.
        """
        try:
            person = People.objects.get(id=id)
            
            for key, value in kwargs.items():
                if value is not None:
                    setattr(person, key, value)
            
            person.save()
            
            # Clear DataLoader cache for this person
            if hasattr(info.context, 'dataloaders'):
                loaders = get_loaders(info)
                loaders['people_by_id'].clear(id)
            
            return UpdatePerson(person=person, success=True, errors=[])
        except People.DoesNotExist:
            return UpdatePerson(
                person=None, 
                success=False, 
                errors=['Person not found']
            )
        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Error updating person: {e}")
            return UpdatePerson(
                person=None, 
                success=False, 
                errors=[str(e)]
            )


class DeletePerson(graphene.Mutation):
    """
    Mutation to delete a person.
    """
    
    class Arguments:
        id = graphene.Int(required=True)
    
    success = graphene.Boolean()
    errors = graphene.List(graphene.String)
    
    @login_required
    def mutate(self, info, id):
        """
        Delete a person.
        """
        try:
            person = People.objects.get(id=id)
            person.delete()
            
            # Clear DataLoader cache
            if hasattr(info.context, 'dataloaders'):
                loaders = get_loaders(info)
                loaders['people_by_id'].clear(id)
            
            return DeletePerson(success=True, errors=[])
        except People.DoesNotExist:
            return DeletePerson(success=False, errors=['Person not found'])
        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Error deleting person: {e}")
            return DeletePerson(success=False, errors=[str(e)])


class Mutation(graphene.ObjectType):
    """
    Enhanced GraphQL Mutations.
    """
    
    create_person = CreatePerson.Field()
    update_person = UpdatePerson.Field()
    delete_person = DeletePerson.Field()


# Create the schema
schema = graphene.Schema(
    query=Query,
    mutation=Mutation,
    types=[PeopleType, PgroupType, AssetType, JobType, JobneedType]
)


# Export schema
__all__ = ['schema']