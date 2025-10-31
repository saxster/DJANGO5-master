"""
JobManager - Custom Manager for Job Model.

Provides specialized query methods for Job records including:
- Geofence queries with GeoJSON annotations
- Scheduled tour and task retrieval
- Calendar event queries
- PPM job listings
- Checkpoint management

Extracted from: apps/activity/managers/job_manager.py (lines 22-399)
Date: 2025-10-10
"""

from .base import (
    models, Q, F, Count, Case, When, Concat, V,
    AsGeoJSON, ValidationError, ObjectDoesNotExist,
    datetime, timedelta, timezone,
    logger, json, utils, pm, settings,
    transaction, DatabaseError, OperationalError, IntegrityError,
    distributed_lock, LockAcquisitionError, ErrorHandler,
    TenantAwareManager
)

log = logger


class JobManager(TenantAwareManager):
    """
    Custom manager for Job model with specialized query methods.

    Extends TenantAwareManager to provide automatic tenant filtering while
    maintaining Job-specific business logic methods.

    Provides optimized queries for:
    - Geofence management with GeoJSON annotations
    - Scheduled tours (internal/external)
    - Task scheduling and calendar integration
    - PPM (Planned Preventive Maintenance) jobs
    - Checkpoint management with race condition protection

    All methods use unified parent handling (Q objects) for compatibility.

    Tenant Isolation:
    - All queries automatically filtered by current tenant
    - Cross-tenant queries require explicit cross_tenant_query() call
    - Inherited from TenantAwareManager (apps/tenants/managers.py)
    """
    use_in_migrations = True

    def getgeofence(self, peopleid, siteid):
        """
        Get geofence assignments for a person at a site.

        Returns geofence data with GeoJSON annotation for map rendering.

        Args:
            peopleid: ID of the person
            siteid: ID of the business unit (site)

        Returns:
            QuerySet with geofence details and GeoJSON geometry
        """
        qset = self.filter(
            people_id=peopleid, bu_id=siteid, identifier='GEOFENCE').select_related(
                'geofence',
            ).annotate(
                geofencejson=AsGeoJSON('geofence')).values(
                    'geofence__id', 'geofence__gfcode', 'people_id', 'fromdate',
                    'geofence__gfname', 'geofencejson', 'enable', 'uptodate', 'identifier',
                    'starttime', 'endtime', 'bu_id', 'asset_id')
        return qset or self.none()

    def get_scheduled_internal_tours(self, request, related, fields):
        """
        Get scheduled internal tours for a session.

        Uses unified parent handling for compatibility.

        Args:
            request: HTTP request with session data
            related: List of relations to select_related()
            fields: List of fields to return in values()

        Returns:
            QuerySet of internal tour jobs with assignment annotations
        """
        S = request.session
        qset = self.select_related(*related).annotate(
                assignedto=Case(
                When(Q(pgroup_id=1) | Q(pgroup_id__isnull=True), then=Concat(F('people__peoplename'), V(' [PEOPLE]'))),
                When(Q(people_id=1) | Q(people_id__isnull=True), then=Concat(F('pgroup__groupname'), V(' [GROUP]'))),
                ),
            ).filter(
            Q(parent__jobname='NONE') | Q(parent__isnull=True) | Q(parent_id=1),  # Unified
            ~Q(jobname='NONE') | ~Q(id=1),
            bu_id__in=S['assignedsites'],
            client_id=S['client_id'],
            identifier__exact='INTERNALTOUR',
            enable=True
        ).values(*fields).order_by('-cdtz')
        return qset or self.none()

    def get_checkpoints_for_externaltour(self, job):
        """
        Get checkpoint locations for an external tour.

        Args:
            job: Job object representing the external tour

        Returns:
            QuerySet of checkpoint business units with GPS locations
        """
        qset = self.select_related(
            'identifier', 'butype', 'parent').annotate(bu__buname=F('buname')).filter(
                parent_id=job.bu_id).values(
                'buname', 'id', 'bucode', 'gpslocation',
            )
        return qset or self.none()


    def get_scheduled_tasks(self, request, related, fields):
        """
        Get scheduled tasks for a session.

        Uses unified parent handling for compatibility.

        Args:
            request: HTTP request with session data
            related: List of relations to select_related()
            fields: List of fields to return in values()

        Returns:
            QuerySet of task jobs with assignment annotations
        """
        S = request.session
        qset = self.annotate(
            assignedto=Case(
                When(Q(pgroup_id=1) | Q(pgroup_id__isnull=True), then=Concat(F('people__peoplename'), V(' [PEOPLE]'))),
                When(Q(people_id=1) | Q(people_id__isnull=True), then=Concat(F('pgroup__groupname'), V(' [GROUP]'))),
            )
            ).filter(
            ~Q(jobname='NONE') | ~Q(id=1),
            Q(parent__jobname='NONE') | Q(parent__isnull=True) | Q(parent_id=1),  # Unified
            bu_id__in=S['assignedsites'],
            client_id=S['client_id'],
            identifier='TASK',
        ).select_related(*related).values(*fields)
        return qset or self.none()

    def get_listview_objs_schdexttour(self, request):
        """
        Get scheduled external tour list view objects.

        Uses unified parent handling for compatibility.

        Args:
            request: HTTP request with session data

        Returns:
            QuerySet of external tour jobs with site group and scheduling details
        """
        S = request.session
        qset = self.annotate(
            assignedto=Case(
                When(Q(pgroup_id=1) | Q(pgroup_id__isnull=True), then=Concat(F('people__peoplename'), V(' [PEOPLE]'))),
                When(Q(people_id=1) | Q(people_id__isnull=True), then=Concat(F('pgroup__groupname'), V(' [GROUP]'))),
            ),
            sitegrpname=F('sgroup__groupname'),
            israndomized=F('other_info__is_randomized'),
            tourfrequency=F('other_info__tour_frequency'),
            breaktime=F('other_info__breaktime'),
            deviation=F('other_info__deviation')
        ).filter(
            ~Q(jobname='NONE'),
            Q(parent__isnull=True) | Q(parent_id=1),  # Unified parent handling
            identifier='EXTERNALTOUR',
            bu_id__in=S['assignedsites'],
            enable=True,
            client_id=S['client_id']
        ).select_related('pgroup', 'sgroup', 'people').values(
            'assignedto', 'sitegrpname', 'israndomized', 'tourfrequency',
            'breaktime', 'deviation', 'fromdate', 'uptodate', 'gracetime',
            'expirytime', 'planduration', 'jobname', 'id', 'ctzoffset'
        ).order_by('-mdtz')
        return qset or self.none()

    def get_sitecheckpoints_exttour(self, job, child_jobid=None):
        """
        Get site checkpoints for an external tour.

        Returns checkpoint details with GPS locations and questionnaire info.

        Args:
            job: Dict with job details including 'id'
            child_jobid: Optional specific checkpoint job ID

        Returns:
            QuerySet of checkpoint jobs with location and questionnaire data
        """
        fields = ['id',
            'breaktime', 'distance', 'starttime', 'expirytime',
            'qsetid', 'jobid', 'assetid', 'seqno', 'jobdesc',
            'bu__buname', 'buid', 'bu__gpslocation', 'endtime', 'duration',
            'qsetname', 'solid', 'people__peoplename']
        qset = self.annotate(
            qsetid=F('qset_id'), assetid=F('asset_id'),
            jobid=F('id'), bu__gpslocation=AsGeoJSON('bu__gpslocation'),
            buid=F('bu_id'),
            breaktime=F('other_info__breaktime'),
            distance=F('other_info__distance'),
            duration=V(None, output_field=models.CharField(null=True)),
            solid=F('bu__solid'),
            qsetname=F('qset__qsetname')

        ).filter(parent_id=job['id']).select_related('asset', 'qset',).values(*fields).order_by('seqno')
        if child_jobid:
            return qset.filter(jobid=child_jobid).values(*fields).order_by('seqno') or self.none()
        return qset or self.none()

    def get_people_assigned_to_geofence(self, geofenceid):
        """
        Get people assigned to a specific geofence.

        Args:
            geofenceid: ID of the geofence

        Returns:
            QuerySet of people assignments with schedule details
        """
        if geofenceid in [None, "None"]:
            return self.none()
        objs = self.filter(
            identifier='GEOFENCE', enable=True, geofence_id=geofenceid
        ).values('people_id', 'people__peoplename', 'people__peoplecode', 'fromdate', 'uptodate', 'starttime', 'endtime', 'pk')
        return objs or self.none()


    def handle_geofencepostdata(self, request):
        """
        Handle post data submitted from geofence add people form.

        Supports create, edit, and delete operations for geofence assignments.

        Args:
            request: HTTP request with GET parameters

        Returns:
            Dict with 'data' (list of created/updated records) and optional 'error'
        """
        R, S = request.GET, request.session
        if R['action'] == 'create' or R['action'] == 'edit':
            # Parse dates and convert to timezone-aware datetime objects
            from_date = datetime.strptime(R['fromdate'], '%d-%b-%Y').date()
            upto_date = datetime.strptime(R['uptodate'], '%d-%b-%Y').date()
            # Combine date with midnight time and make timezone-aware
            fromdate = datetime.combine(from_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            uptodate = datetime.combine(upto_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            starttime = datetime.strptime(R['starttime'], '%H:%M').time()
            endtime = datetime.strptime(R['endtime'], '%H:%M').time()
            cdtz = datetime.now(tz=timezone.utc)
            mdtz = datetime.now(tz=timezone.utc)

            PostData = {
                'jobname': f"{R['gfcode']}-{R['people__peoplename']}", 'identifier': 'GEOFENCE',
                'jobdesc': f"{R['gfcode']}-{R['gfname']}-{R['people__peoplename']}",
                'fromdate': fromdate, 'uptodate': uptodate, 'starttime': starttime,
                'endtime': endtime, 'cdtz': cdtz, 'mdtz': mdtz, 'enable': True, 'bu_id': R['bu_id'],
                'client_id': S['client_id'], 'people_id': R['people_id'], 'geofence_id': R['geofence_id'],
                'seqno': -1, 'parent_id': 1, 'pgroup_id': 1, 'sgroup_id': 1, 'asset_id': 1, 'qset_id': 1,
                'planduration': 0, 'gracetime': 0, 'expirytime': 0, 'cuser': request.user, 'muser': request.user
            }
        else:
            pk = R['pk']
            # Parse dates and convert to timezone-aware datetime objects
            from_date = datetime.strptime(R[f'data[{pk}][fromdate]'], '%Y-%m-%dT%H:%M:%SZ').date()
            upto_date = datetime.strptime(R[f'data[{pk}][uptodate]'], '%Y-%m-%dT%H:%M:%SZ').date()
            # Combine date with midnight time and make timezone-aware
            fromdate = datetime.combine(from_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            uptodate = datetime.combine(upto_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            starttime = datetime.strptime(R[f'data[{pk}][starttime]'], '%H:%M:%S').time()
            endtime = datetime.strptime(R[f'data[{pk}][endtime]'], '%H:%M:%S').time()
            cdtz = datetime.now(tz=timezone.utc)
            mdtz = datetime.now(tz=timezone.utc)

            PostData = {
                'jobname': f"{R['gfcode']}-{R[f'data[{pk}][people__peoplename]']}", 'identifier': 'GEOFENCE',
                'jobdesc': f"{R['gfcode']}-{R['gfname']}-{R[f'data[{pk}][people__peoplename]']}",
                'fromdate': fromdate, 'uptodate': uptodate, 'starttime': starttime,
                'endtime': endtime, 'cdtz': cdtz, 'mdtz': mdtz, 'enable': True, 'bu_id': R['bu_id'],
                'client_id': S['client_id'], 'people_id': R['people_id'], 'geofence_id': R['geofence_id'],
                'seqno': -1, 'parent_id': 1, 'pgroup_id': 1, 'sgroup_id': 1, 'asset_id': 1, 'qset_id': 1,
                'planduration': 0, 'gracetime': 0, 'expirytime': 0, 'cuser': request.user, 'muser': request.user
            }
        if R['action'] == 'create':
            if self.filter(
                jobname=PostData['jobname'], asset_id=PostData['asset_id'],
                qset_id=PostData['qset_id'], parent_id=PostData['parent_id'],
                identifier='GEOFENCE').exists():
                return {'data': list(self.none()), 'error': 'Warning: Record already added!'}

            with transaction.atomic():
                ID = self.create(**PostData).id
                log.info(f"Created geofence job {ID}")

        elif R['action'] == 'edit':
            PostData.pop('cdtz')
            PostData.pop('cuser')

            with transaction.atomic():
                job_obj = self.select_for_update().get(pk=R['pk'])
                for field, value in PostData.items():
                    setattr(job_obj, field, value)
                job_obj.save()
                ID = R['pk']
                log.info(f"Updated geofence job {ID}")

        else:
            self.filter(pk=R['pk']).delete()
            return {'data': list(self.none()),}

        qset = self.filter(pk=ID).values('people__peoplename', 'people_id', 'fromdate', 'uptodate',
                                            'starttime', 'endtime', 'people__peoplecode', 'pk')
        return {'data': list(qset)}

    def get_jobppm_listview(self, request):
        """
        Get PPM (Planned Preventive Maintenance) job list view.

        Args:
            request: HTTP request with session data

        Returns:
            QuerySet of PPM jobs with asset and questionnaire details
        """
        R, S = request.GET, request.session
        qset = self.annotate(
            assignedto=Case(
                When(pgroup_id=1, then=Concat(F('people__peoplename'), V(' [PEOPLE]'))),
                When(people_id=1, then=Concat(F('pgroup__groupname'), V(' [GROUP]'))),
            )).filter(
            client_id=S['client_id'],
            bu_id=S['bu_id'],
            identifier='PPM',
            enable=True
        ).values('id', 'jobname', 'asset__assetname', 'qset__qsetname', 'assignedto', 'bu__bucode',
                 'uptodate', 'planduration', 'gracetime', 'expirytime', 'fromdate', 'bu__buname')
        return qset or self.none()

    def handle_save_checkpoint_guardtour(self, request):
        """
        Handle checkpoint save with race condition protection.

        Uses distributed lock to prevent concurrent parent updates that could
        cause data inconsistency.

        Args:
            request: HTTP POST request with checkpoint data

        Returns:
            Dict with 'data' (list of saved checkpoint) and optional 'error'
        """
        R, S = request.POST, request.session
        from apps.scheduler import utils as sutils

        parent_job = self.filter(id=R['parentid']).select_related('bu').values(
            'id', 'jobname', 'cron', 'identifier', 'priority', 'pgroup_id', 'geofence_id',
            'fromdate', 'uptodate', 'planduration', 'gracetime', 'frequency', 'people_id',
            'scantype', 'ctzoffset', 'bu_id', 'client_id', 'ticketcategory_id', 'lastgeneratedon',
            'bu__buname'
        ).first()

        cdtz = datetime.now(tz=timezone.utc)
        mdtz = datetime.now(tz=timezone.utc)
        checkpoint = {
            'expirytime': R['expirytime'],
            'qsetid': R['qset_id'],
            'assetid': R['asset_id'],
            'seqno': R['seqno'],
            'qsetname': R['qsetname'],
            'bu__buname': parent_job['bu__buname']
        }

        if not R['action'] == 'remove':
            child_job = sutils.job_fields(parent_job, checkpoint)

        # Use distributed lock to prevent concurrent parent updates
        lock_key = f"parent_job_update:{R['parentid']}"

        try:
            with distributed_lock(lock_key, timeout=15, blocking_timeout=10):
                with transaction.atomic():
                    if R['action'] == 'create':
                        if self.filter(
                            qset_id=checkpoint['qsetid'], asset_id=checkpoint['assetid'],
                            parent_id=parent_job['id']).exists():
                            return {'data': list(self.none()), 'error': 'Warning: Record already added!'}

                        ID = self.create(**child_job, cuser=request.user, muser=request.user,
                                         cdtz=cdtz, mdtz=mdtz).id
                    elif R['action'] == 'edit':
                        if updated := self.filter(pk=R['pk']).update(**child_job, muser=request.user, mdtz=mdtz):
                            ID = R['pk']
                        else:
                            return {'data': [], 'error': 'Update failed'}
                    else:
                        self.filter(pk=R['pk']).delete()
                        return {'data': list(self.none()),}

                    # Update parent timestamp atomically within same lock and transaction
                    parent_obj = self.select_for_update().get(pk=R['parentid'])
                    parent_obj.mdtz = timezone.now()
                    parent_obj.muser = request.user
                    parent_obj.save(update_fields=['mdtz', 'muser'])

                    qset = self.filter(pk=ID).values('seqno', 'qset__qsetname', 'asset__assetname', 'expirytime', 'pk', 'asset_id', 'qset_id')
                    return {'data': list(qset)}

        except LockAcquisitionError as e:
            log.error("Failed to acquire lock for parent job update: %s", str(e), exc_info=True)
            return {'data': [], 'error': 'System busy, please try again'}
        except IntegrityError as e:
            log.error("Integrity error in checkpoint save: %s", str(e), exc_info=True)
            if 'expirytime_gte_0_ck' in str(e):
                return {'data': [], 'error': "Invalid Expiry Time. It must be greater than or equal to 0."}
            return {'data': [], 'error': 'Data integrity error'}
        except (DatabaseError, OperationalError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'operation': 'save_checkpoint_guardtour',
                    'parent_id': R['parentid'],
                    'action': R['action']
                },
                level='error'
            )
            log.critical(
                "Database error in checkpoint save: %s",
                str(e),
                extra={'correlation_id': correlation_id},
                exc_info=True
            )
            return {'data': [], 'error': 'Database service unavailable, please try again'}
        except (ValidationError, ValueError, TypeError) as e:
            log.error(
                "Validation error in checkpoint save: %s",
                str(e),
                extra={'parent_id': R['parentid']},
                exc_info=True
            )
            return {'data': [], 'error': f'Invalid checkpoint data: {str(e)}'}
        except ObjectDoesNotExist as e:
            log.error(
                "Parent job not found: %s",
                str(e),
                extra={'parent_id': R['parentid']}
            )
            return {'data': [], 'error': 'Parent job not found'}

    def handle_save_checkpoint_sitetour(self, request):
        """
        Handle site tour checkpoint save with race condition protection.

        Updates checkpoint sequence and questionnaire assignment with distributed
        lock to prevent concurrent modifications.

        Args:
            request: HTTP POST request with checkpoint data

        Returns:
            Dict with 'data' (list of updated checkpoint) and optional 'error'
        """
        R, S = request.POST, request.session

        lock_key = f"parent_job_update:{R['parent_id']}"

        try:
            with distributed_lock(lock_key, timeout=15, blocking_timeout=10):
                with transaction.atomic():
                    mdtz = datetime.now(tz=timezone.utc)
                    if R['action'] == 'edit':
                        child_job_post_data = {'seqno': R['seqno'], 'qset_id': R['qset_id']}
                        if updated := self.filter(id=R['jobid']).update(**child_job_post_data, muser=request.user, mdtz=mdtz):
                            ID = R['jobid']

                            # Update parent timestamp atomically
                            parent_obj = self.select_for_update().get(pk=R['parent_id'])
                            parent_obj.mdtz = timezone.now()
                            parent_obj.muser = request.user
                            parent_obj.save(update_fields=['mdtz', 'muser'])

                            qset = self.get_sitecheckpoints_exttour({'id': R['parent_id']}, ID)
                            return {'data': list(qset)}
                        return {'data': []}
        except LockAcquisitionError as e:
            log.error("Failed to acquire lock for site tour update: %s", str(e), exc_info=True)
            return {'data': [], 'error': 'System busy, please try again'}
        except (DatabaseError, OperationalError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'operation': 'save_checkpoint_sitetour',
                    'parent_id': R['parent_id'],
                    'job_id': R.get('jobid')
                },
                level='error'
            )
            log.critical(
                "Database error in site tour checkpoint: %s",
                str(e),
                extra={'correlation_id': correlation_id},
                exc_info=True
            )
            return {'data': [], 'error': 'Database service unavailable, please try again'}
        except (ValidationError, ValueError, KeyError) as e:
            log.error(
                "Validation error in site tour checkpoint: %s",
                str(e),
                extra={'parent_id': R.get('parent_id')},
                exc_info=True
            )
            return {'data': [], 'error': f'Invalid request data: {str(e)}'}
        except ObjectDoesNotExist as e:
            log.error(
                "Job not found for site tour update: %s",
                str(e),
                extra={'job_id': R.get('jobid')}
            )
            return {'data': [], 'error': 'Job not found'}
