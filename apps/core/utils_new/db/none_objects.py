"""
NONE Object Factory Functions

Creates sentinel "NONE" records for model relationships to handle missing data
gracefully. These are placeholder records used throughout the system when
actual data is not available.
"""

import logging
import json
from datetime import datetime, timezone as dt_timezone
from django.utils import timezone
from django.db.utils import IntegrityError, DatabaseError
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger("django")
error_logger = logging.getLogger("error_logger")


def check_nones(none_fields, tablename, cleaned_data, json_format=False):
    """
    Populate cleaned_data with NONE instances for missing fields.

    Args:
        none_fields: List of field names needing NONE values
        tablename: Name of table to determine NONE factory
        cleaned_data: Dictionary to populate
        json_format: Return JSON ID (True) or instance (False)
    """
    none_instance_map = {
        "question": get_or_create_none_question,
        "asset": get_or_create_none_asset,
        "people": get_or_create_none_people,
        "pgroup": get_or_create_none_pgroup,
        "typeassist": get_or_create_none_typeassist,
    }

    for field in none_fields:
        cleaned_data[field] = 1 if json_format else none_instance_map[tablename]()
    return cleaned_data


def get_or_create_none_people(using=None):
    """Create NONE sentinel People record."""
    from apps.peoples import models as pm
    tenant = get_or_create_none_tenant()

    try:
        return pm.People.objects.get(peoplecode="NONE")
    except pm.People.DoesNotExist:
        pass

    fields = dict(
        peoplecode="NONE",
        peoplename="NONE",
        email="none@youtility.in",
        dateofbirth="1111-01-01",
        dateofjoin="1111-01-01",
        cuser_id=None,
        muser_id=None,
        cdtz=timezone.now().replace(microsecond=0),
        mdtz=timezone.now().replace(microsecond=0),
        ctzoffset=330,
        loginid="none_user",
    )
    if hasattr(pm.People, 'tenant'):
        fields['tenant'] = tenant

    obj = pm.People(**fields)
    obj.save_base(raw=True)
    return obj


def get_or_create_none_pgroup():
    """Create NONE sentinel Pgroup record."""
    from apps.peoples import models as pm
    tenant = get_or_create_none_tenant()

    obj, _ = pm.Pgroup.objects.get_or_create(
        groupname="NONE",
        defaults={'tenant': tenant} if hasattr(pm.Pgroup, 'tenant') else {},
    )
    return obj


def get_or_create_none_cap():
    """Create NONE sentinel Capability record."""
    from apps.peoples import models as pm
    tenant = get_or_create_none_tenant()

    obj, _ = pm.Capability.objects.get_or_create(
        capscode="NONE",
        capsname="NONE",
        defaults={"tenant": tenant} if hasattr(pm.Capability, 'tenant') else {},
    )
    return obj


def get_or_create_none_typeassist():
    """Create NONE sentinel TypeAssist record."""
    from apps.core_onboarding.models import TypeAssist
    tenant = get_or_create_none_tenant()

    obj, iscreated = TypeAssist.objects.get_or_create(
        tacode="NONE",
        taname="NONE",
        defaults={"tenant": tenant},
    )
    return obj, iscreated


def get_none_typeassist():
    """Get NONE TypeAssist record, creating if needed."""
    from apps.core_onboarding.models import TypeAssist

    try:
        return TypeAssist.objects.get(id=1)
    except TypeAssist.DoesNotExist:
        o, _ = get_or_create_none_typeassist()
        return o


def get_or_create_none_bv():
    """Create NONE sentinel Business Unit (Bt) record."""
    Bt = _get_bt_model()
    tenant = get_or_create_none_tenant()

    try:
        return Bt.objects.get(bucode="NONE")
    except Bt.DoesNotExist:
        pass

    fields = dict(
        bucode="NONE",
        buname="NONE",
        enable=False,
        siteincharge_id=None,
        cuser_id=None,
        muser_id=None,
        cdtz=timezone.now().replace(microsecond=0),
        mdtz=timezone.now().replace(microsecond=0),
        ctzoffset=330,
    )
    if hasattr(Bt, 'tenant'):
        fields['tenant'] = tenant

    obj = Bt(**fields)
    obj.save_base(raw=True)
    return obj


def get_or_create_none_tenant():
    """Create NONE sentinel Tenant record."""
    from apps.tenants.models import Tenant
    return Tenant.objects.get_or_create(
        tenantname="Intelliwiz", subdomain_prefix="intelliwiz", defaults={}
    )[0]


def get_or_create_none_location():
    """Create NONE sentinel Location record."""
    from apps.activity.models.location_model import Location
    from django.db import transaction
    tenant = get_or_create_none_tenant()

    try:
        obj = Location.objects.get(loccode="NONE", locname="NONE")
        return obj
    except Location.DoesNotExist:
        with transaction.atomic():
            defaults = {
                "locstatus": "SCRAPPED",
                "bu_id": 1,
                "client_id": 1,
                "tenant_id": 1,
                "cuser_id": 1,
                "muser_id": 1,
            }
            if hasattr(Location, 'tenant'):
                defaults['tenant'] = tenant

            obj, created = Location.objects.get_or_create(
                loccode="NONE",
                locname="NONE",
                defaults=defaults,
            )
            return obj


def get_or_create_none_jobneed():
    """Create NONE sentinel Jobneed record."""
    from apps.activity.models.job_model import Jobneed
    tenant = get_or_create_none_tenant()

    date = datetime(1970, 1, 1, 00, 00, 00).replace(tzinfo=dt_timezone.utc)
    defaults = {
        "plandatetime": date,
        "expirydatetime": date,
        "gracetime": 0,
        "receivedonserver": date,
    }
    if hasattr(Jobneed, 'tenant'):
        defaults['tenant'] = tenant

    obj, _ = Jobneed.objects.get_or_create(
        jobdesc="NONE",
        scantype="NONE",
        seqno=-1,
        defaults=defaults,
    )
    return obj


def get_or_create_none_wom():
    """Create NONE sentinel Work Order Management record."""
    from apps.work_order_management.models import Wom
    tenant = get_or_create_none_tenant()

    date = datetime(1970, 1, 1, 00, 00, 00).replace(tzinfo=dt_timezone.utc)
    defaults = {
        "workpermit": Wom.WorkPermitStatus.NOTNEED,
        "attachmentcount": 0,
        "priority": Wom.Priority.LOW,
    }
    if hasattr(Wom, 'tenant'):
        defaults['tenant'] = tenant

    obj, _ = Wom.objects.get_or_create(
        description="NONE",
        expirydatetime=date,
        plandatetime=date,
        defaults=defaults,
    )
    return obj


def get_or_create_none_qset():
    """Create NONE sentinel QuestionSet record."""
    from apps.activity.models.question_model import QuestionSet
    tenant = get_or_create_none_tenant()

    defaults = {}
    if hasattr(QuestionSet, 'tenant'):
        defaults['tenant'] = tenant

    obj, _ = QuestionSet.objects.get_or_create(
        qsetname="NONE",
        defaults=defaults,
    )
    return obj


def get_or_create_none_question():
    """Create NONE sentinel Question record."""
    from apps.activity.models.question_model import Question
    tenant = get_or_create_none_tenant()

    defaults = {}
    if hasattr(Question, 'tenant'):
        defaults['tenant'] = tenant

    obj, _ = Question.objects.get_or_create(
        quesname="NONE",
        defaults=defaults,
    )
    return obj


def get_or_create_none_qsetblng():
    """Create NONE sentinel QuestionSetBelonging record."""
    from apps.activity.models.question_model import QuestionSetBelonging
    tenant = get_or_create_none_tenant()

    defaults = {
        "qset": get_or_create_none_qset(),
        "question": get_or_create_none_question(),
    }
    if hasattr(QuestionSetBelonging, 'tenant'):
        defaults['tenant'] = tenant

    obj, _ = QuestionSetBelonging.objects.get_or_create(
        answertype="NONE",
        ismandatory=False,
        seqno=-1,
        defaults=defaults,
    )
    return obj


def get_or_create_none_asset():
    """Create NONE sentinel Asset record."""
    from apps.activity.models.asset_model import Asset
    tenant = get_or_create_none_tenant()

    defaults = {"iscritical": False}
    if hasattr(Asset, 'tenant'):
        defaults['tenant'] = tenant

    obj, _ = Asset.objects.get_or_create(
        assetcode="NONE",
        assetname="NONE",
        identifier="NONE",
        defaults=defaults,
    )
    return obj


def get_or_create_none_ticket():
    """Create NONE sentinel Ticket record."""
    from apps.y_helpdesk.models import Ticket
    tenant = get_or_create_none_tenant()

    obj, _ = Ticket.objects.get_or_create(
        ticketdesc="NONE",
        defaults={"tenant": tenant},
    )
    return obj


def get_or_create_none_job():
    """Create NONE sentinel Job record."""
    from apps.activity.models.job_model import Job
    tenant = get_or_create_none_tenant()

    date = datetime(1970, 1, 1, 00, 00, 00).replace(tzinfo=dt_timezone.utc)
    defaults = {
        "fromdate": date,
        "uptodate": date,
        "cron": "no_cron",
        "lastgeneratedon": date,
        "planduration": 0,
        "expirytime": 0,
        "gracetime": 0,
        "priority": "LOW",
        "seqno": -1,
        "scantype": "SKIP",
    }
    if hasattr(Job, 'tenant'):
        defaults['tenant'] = tenant

    obj, _ = Job.objects.get_or_create(
        jobname="NONE",
        jobdesc="NONE",
        defaults=defaults,
    )
    return obj


def get_or_create_none_gf():
    """Create NONE sentinel GeofenceMaster record."""
    from apps.core_onboarding.models import GeofenceMaster

    obj, _ = GeofenceMaster.objects.get_or_create(
        gfcode="NONE", gfname="NONE", defaults={"alerttext": "NONE", "enable": False}
    )
    return obj


def create_none_entries(self):
    """
    Creates all NONE sentinel entries in database.

    Called during system initialization to ensure all sentinel records exist.
    """
    from apps.core.utils_new.db.connection import get_current_db_name

    try:
        db = get_current_db_name()

        get_or_create_none_bv()
        _, iscreated = get_or_create_none_typeassist()
        if not iscreated:
            logger.debug("NONE TypeAssist already exists, checking other entries...")

        get_or_create_none_people()
        get_or_create_none_ticket()
        get_or_create_none_cap()
        get_or_create_none_pgroup()
        get_or_create_none_job()
        get_or_create_none_jobneed()
        get_or_create_none_qset()
        get_or_create_none_asset()
        get_or_create_none_tenant()
        get_or_create_none_question()
        get_or_create_none_qsetblng()
        get_or_create_none_gf()
        get_or_create_none_wom()
        logger.debug("NONE entries are successfully inserted...")
    except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError, json.JSONDecodeError) as e:
        error_logger.error("create none entries", exc_info=True)
        raise


__all__ = [
    'check_nones',
    'get_or_create_none_people',
    'get_or_create_none_pgroup',
    'get_or_create_none_cap',
    'get_or_create_none_typeassist',
    'get_none_typeassist',
    'get_or_create_none_bv',
    'get_or_create_none_tenant',
    'get_or_create_none_location',
    'get_or_create_none_jobneed',
    'get_or_create_none_wom',
    'get_or_create_none_qset',
    'get_or_create_none_question',
    'get_or_create_none_qsetblng',
    'get_or_create_none_asset',
    'get_or_create_none_ticket',
    'get_or_create_none_job',
    'get_or_create_none_gf',
    'create_none_entries',
]
def _get_bt_model():
    """
    Resolve the Business Unit model location. The model was moved from
    apps.core_onboarding to apps.client_onboarding during the onboarding split.
    """
    try:
        from apps.client_onboarding.models import Bt  # type: ignore
        return Bt
    except ImportError:
        from apps.core_onboarding.models import Bt  # Legacy fallback
        return Bt
