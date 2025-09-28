"""
GraphQL DataLoaders for N+1 Query Prevention

Implements batch loading to optimize GraphQL query performance.
"""

import logging
from promise import Promise
from promise.dataloader import DataLoader
from collections import defaultdict
from apps.onboarding.models import BT, Shift
from apps.peoples.models import People
from apps.activity.models.asset_model import Asset
from apps.activity.models.job_model import Job

logger = logging.getLogger('graphql.dataloaders')


class BatchLoadMixin:
    """
    Mixin to provide common batch loading functionality.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache = True
        self.max_batch_size = 100
    
    def load_many(self, keys):
        """
        Override to handle load_many more efficiently.
        """
        return Promise.all([self.load(key) for key in keys])


class PeopleByIdLoader(DataLoader, BatchLoadMixin):
    """
    DataLoader for batching People lookups by ID.
    """
    
    def batch_load_fn(self, person_ids):
        """
        Batch load people by IDs.
        """
        # Convert to list of integers
        person_ids = [int(id) for id in person_ids]
        
        # Fetch all people in one query with optimizations
        people = People.objects.select_related('department', 'designation', 'bu', 'client', 'peopletype').in_bulk(person_ids)
        
        # Return in the same order as requested
        return Promise.resolve([
            people.get(person_id) for person_id in person_ids
        ])


class PeopleByGroupLoader(DataLoader, BatchLoadMixin):
    """
    DataLoader for loading people by group ID.
    """
    
    def batch_load_fn(self, group_ids):
        """
        Batch load people belonging to groups.
        """
        # Convert to list of integers
        group_ids = [int(id) for id in group_ids]
        
        # Create a dictionary to store results
        people_by_group = defaultdict(list)
        
        # Fetch all people-group relationships with optimizations
        from apps.peoples.models import Pgbelonging
        belongings = Pgbelonging.objects.filter(
            group_id__in=group_ids
        ).select_related('people', 'people__department', 'people__bu', 'pgroup')
        
        # Group people by group_id
        for belonging in belongings:
            people_by_group[belonging.group_id].append(belonging.people)
        
        # Return results in the same order as requested
        return Promise.resolve([
            people_by_group.get(group_id, []) for group_id in group_ids
        ])


class GroupsByPersonLoader(DataLoader, BatchLoadMixin):
    """
    DataLoader for loading groups by person ID.
    """
    
    def batch_load_fn(self, person_ids):
        """
        Batch load groups for people.
        """
        # Convert to list of integers
        person_ids = [int(id) for id in person_ids]
        
        # Create a dictionary to store results
        groups_by_person = defaultdict(list)
        
        # Fetch all person-group relationships
        from apps.peoples.models import Pgbelonging
        belongings = Pgbelonging.objects.filter(
            people_id__in=person_ids
        ).select_related('group')
        
        # Group groups by person_id
        for belonging in belongings:
            groups_by_person[belonging.people_id].append(belonging.group)
        
        # Return results in the same order as requested
        return Promise.resolve([
            groups_by_person.get(person_id, []) for person_id in person_ids
        ])


class AssetByIdLoader(DataLoader, BatchLoadMixin):
    """
    DataLoader for batching Asset lookups by ID.
    """
    
    def batch_load_fn(self, asset_ids):
        """
        Batch load assets by IDs.
        """
        asset_ids = [int(id) for id in asset_ids]
        
        # Fetch all assets with related data
        assets = Asset.objects.filter(
            id__in=asset_ids
        ).select_related('location', 'created_by')
        
        # Create lookup dictionary
        asset_dict = {asset.id: asset for asset in assets}
        
        # Return in requested order
        return Promise.resolve([
            asset_dict.get(asset_id) for asset_id in asset_ids
        ])


class JobsByAssetLoader(DataLoader, BatchLoadMixin):
    """
    DataLoader for loading jobs by asset ID.
    """
    
    def batch_load_fn(self, asset_ids):
        """
        Batch load jobs for assets.
        """
        asset_ids = [int(id) for id in asset_ids]
        
        jobs_by_asset = defaultdict(list)
        
        # Fetch all jobs related to assets
        jobs = Job.objects.filter(
            asset_id__in=asset_ids
        ).select_related('jobneed', 'people')
        
        for job in jobs:
            jobs_by_asset[job.asset_id].append(job)
        
        return Promise.resolve([
            jobs_by_asset.get(asset_id, []) for asset_id in asset_ids
        ])


class JobneedByJobLoader(DataLoader, BatchLoadMixin):
    """
    DataLoader for loading jobneed by job ID.
    """
    
    def batch_load_fn(self, job_ids):
        """
        Batch load jobneeds for jobs.
        """
        job_ids = [int(id) for id in job_ids]
        
        # Fetch all jobs with jobneed
        jobs = Job.objects.filter(
            id__in=job_ids
        ).select_related('jobneed')
        
        job_dict = {job.id: job.jobneed for job in jobs}
        
        return Promise.resolve([
            job_dict.get(job_id) for job_id in job_ids
        ])


class ShiftByIdLoader(DataLoader, BatchLoadMixin):
    """
    DataLoader for batching Shift lookups.
    """
    
    def batch_load_fn(self, shift_ids):
        """
        Batch load shifts by IDs.
        """
        shift_ids = [int(id) for id in shift_ids if id]
        
        shifts = Shift.objects.in_bulk(shift_ids)
        
        return Promise.resolve([
            shifts.get(shift_id) if shift_id else None 
            for shift_id in shift_ids
        ])


class BTByIdLoader(DataLoader, BatchLoadMixin):
    """
    DataLoader for batching BT (Business Type) lookups.
    """
    
    def batch_load_fn(self, bt_ids):
        """
        Batch load BTs by IDs.
        """
        bt_ids = [int(id) for id in bt_ids if id]
        
        bts = BT.objects.in_bulk(bt_ids)
        
        return Promise.resolve([
            bts.get(bt_id) if bt_id else None 
            for bt_id in bt_ids
        ])


class CountLoader(DataLoader):
    """
    Generic DataLoader for counting related objects.
    """

    def __init__(self, model, field_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model
        self.field_name = field_name
        self.cache = True

    def batch_load_fn(self, parent_ids):
        """
        Batch load counts of related objects.
        """
        from django.db.models import Count

        parent_ids = [int(id) for id in parent_ids]

        # Get counts for all parent IDs
        counts = self.model.objects.filter(
            **{f"{self.field_name}__in": parent_ids}
        ).values(self.field_name).annotate(
            count=Count('id')
        )

        # Create lookup dictionary
        count_dict = {
            item[self.field_name]: item['count']
            for item in counts
        }

        # Return counts in requested order
        return Promise.resolve([
            count_dict.get(parent_id, 0) for parent_id in parent_ids
        ])


class JobsByPeopleLoader(DataLoader, BatchLoadMixin):
    """
    DataLoader for loading jobs by people ID with optimized relationships.
    """

    def batch_load_fn(self, people_ids):
        """
        Batch load jobs for people with full optimization.
        """
        people_ids = [int(id) for id in people_ids]

        jobs_by_people = defaultdict(list)

        # Fetch all jobs related to people with comprehensive select_related
        jobs = Job.objects.filter(
            people_id__in=people_ids
        ).select_related(
            'jobneed', 'asset', 'asset__location', 'asset__created_by',
            'people', 'people__shift', 'people__bt'
        )

        for job in jobs:
            jobs_by_people[job.people_id].append(job)

        return Promise.resolve([
            jobs_by_people.get(people_id, []) for people_id in people_ids
        ])


class JobsByJobneedLoader(DataLoader, BatchLoadMixin):
    """
    DataLoader for loading jobs by jobneed ID with optimized relationships.
    """

    def batch_load_fn(self, jobneed_ids):
        """
        Batch load jobs for jobneeds with full optimization.
        """
        jobneed_ids = [int(id) for id in jobneed_ids]

        jobs_by_jobneed = defaultdict(list)

        # Fetch all jobs related to jobneeds with comprehensive select_related
        jobs = Job.objects.filter(
            jobneed_id__in=jobneed_ids
        ).select_related(
            'jobneed', 'asset', 'asset__location', 'asset__created_by',
            'people', 'people__shift', 'people__bt'
        )

        for job in jobs:
            jobs_by_jobneed[job.jobneed_id].append(job)

        return Promise.resolve([
            jobs_by_jobneed.get(jobneed_id, []) for jobneed_id in jobneed_ids
        ])


class DataLoaderRegistry:
    """
    Registry for managing DataLoader instances per request.
    """
    
    def __init__(self):
        self.loaders = {}
    
    def get_loader(self, loader_class, *args, **kwargs):
        """
        Get or create a DataLoader instance.
        """
        loader_key = f"{loader_class.__name__}_{str(args)}_{str(kwargs)}"
        
        if loader_key not in self.loaders:
            self.loaders[loader_key] = loader_class(*args, **kwargs)
        
        return self.loaders[loader_key]
    
    def clear(self):
        """
        Clear all DataLoader instances.
        """
        self.loaders.clear()


def get_loaders(info):
    """
    Get DataLoader instances for a GraphQL request.
    
    Usage in GraphQL resolvers:
        loaders = get_loaders(info)
        person = await loaders.people_by_id.load(person_id)
    """
    # Get or create loader registry in context
    if not hasattr(info.context, 'dataloaders'):
        info.context.dataloaders = DataLoaderRegistry()
    
    registry = info.context.dataloaders
    
    # Return loader instances
    return {
        'people_by_id': registry.get_loader(PeopleByIdLoader),
        'people_by_group': registry.get_loader(PeopleByGroupLoader),
        'groups_by_person': registry.get_loader(GroupsByPersonLoader),
        'asset_by_id': registry.get_loader(AssetByIdLoader),
        'jobs_by_asset': registry.get_loader(JobsByAssetLoader),
        'jobs_by_people': registry.get_loader(JobsByPeopleLoader),
        'jobs_by_jobneed': registry.get_loader(JobsByJobneedLoader),
        'jobneed_by_job': registry.get_loader(JobneedByJobLoader),
        'shift_by_id': registry.get_loader(ShiftByIdLoader),
        'bt_by_id': registry.get_loader(BTByIdLoader),

        # Count loaders
        'people_count_by_group': registry.get_loader(
            CountLoader, People, 'groups'
        ),
        'job_count_by_asset': registry.get_loader(
            CountLoader, Job, 'asset'
        ),
        'job_count_by_people': registry.get_loader(
            CountLoader, Job, 'people'
        ),
        'job_count_by_jobneed': registry.get_loader(
            CountLoader, Job, 'jobneed'
        ),
    }


class DataLoaderMiddleware:
    """
    GraphQL middleware to manage DataLoader lifecycle.
    """
    
    def resolve(self, next, root, info, **args):
        """
        Middleware to clear DataLoaders after each request.
        """
        try:
            return next(root, info, **args)
        finally:
            # Clear DataLoaders after request
            if hasattr(info.context, 'dataloaders'):
                info.context.dataloaders.clear()


# Export all DataLoader classes
__all__ = [
    'PeopleByIdLoader',
    'PeopleByGroupLoader',
    'GroupsByPersonLoader',
    'AssetByIdLoader',
    'JobsByAssetLoader',
    'JobsByPeopleLoader',
    'JobsByJobneedLoader',
    'JobneedByJobLoader',
    'ShiftByIdLoader',
    'BTByIdLoader',
    'CountLoader',
    'DataLoaderRegistry',
    'get_loaders',
    'DataLoaderMiddleware',
]