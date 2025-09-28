import apps.onboarding.models as ob
from apps.activity.models.location_model import Location
from apps.peoples import models as pm
from apps.tenants.models import Tenant
from apps.activity.models.job_model import Job, Jobneed
from apps.work_order_management.models import Wom
from apps.activity.models.asset_model import Asset
from apps.activity.models.question_model import (
    Question,
    QuestionSet,
    QuestionSetBelonging,
)
from apps.core import exceptions as excp
from django.utils import timezone
from datetime import datetime, timezone as dt_timezone
import threading
import logging
import ast
import json

logger = logging.getLogger("django")
error_logger = logging.getLogger("error_logger")
debug_logger = logging.getLogger("debug_logger")


__all__ = [
    'save_common_stuff',
    'create_tenant_with_alias',
    'check_nones',
    'get_record_from_input',
    'dictfetchall',
    'namedtuplefetchall',
    'runrawsql',
    'get_action_on_ticket_states',
    'store_ticket_history',
    'get_or_create_none_people',
    'get_none_typeassist',
    'get_or_create_none_pgroup',
    'get_or_create_none_location',
    'hostname_from_request',
    'get_tenants_map',
    'tenant_db_from_request',
    'get_or_create_none_cap',
    'get_or_create_none_bv',
    'get_or_create_none_typeassist',
    'get_or_create_none_tenant',
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
    'create_super_admin',
    'THREAD_LOCAL',
    'get_current_db_name',
    'set_db_for_router',
]


def save_common_stuff(request, instance, is_superuser=False, ctzoffset=-1):
    from django.utils import timezone

    if request and hasattr(request, 'user'):
        logger.debug("Request User ID: %s and %s", request.user.id, request)
    userid = (
        1 if is_superuser else request.user.id if request else 1
    )  # Default user if request is None
    if instance.cuser is not None:
        instance.muser_id = userid
        instance.mdtz = timezone.now().replace(microsecond=0)
        instance.ctzoffset = ctzoffset
    else:
        instance.cuser_id = instance.muser_id = userid

    # Check if the request object exists and has a session
    if request and hasattr(request, "session"):
        instance.ctzoffset = int(request.session.get("ctzoffset", 330))
    else:
        instance.ctzoffset = (
            330  # Use default offset if request or session is not available
        )

    return instance


def create_tenant_with_alias(db):
    Tenant.objects.create(tenantname=db.upper(), subdomain_prefix=db)


def check_nones(none_fields, tablename, cleaned_data, json=False):
    none_instance_map = {
        "question": get_or_create_none_question,
        "asset": get_or_create_none_asset,
        "people": get_or_create_none_people,
        "pgroup": get_or_create_none_pgroup,
        "typeassist": get_or_create_none_typeassist,
    }

    for field in none_fields:
        cleaned_data[field] = 1 if json else none_instance_map[tablename]()
    return cleaned_data


def get_record_from_input(input):
    values = ast.literal_eval(json.dumps(input.values))
    return dict(zip(input.columns, values))


def dictfetchall(cursor):
    "Return all rows from a cursor as a dict"
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def namedtuplefetchall(cursor):
    from collections import namedtuple

    "Return all rows from a cursor as a namedtuple"
    desc = cursor.description
    nt_result = namedtuple("Result", [col[0] for col in desc])
    return [nt_result(*row) for row in cursor.fetchall()]


def runrawsql(
    sql, args=None, db="default", named=False, count=False, named_params=False
):
    """
    Runs raw SQL and returns namedtuple or dict type results.

    SECURITY: This function now uses parameterized queries to prevent SQL injection.
    For named parameters, use psycopg2's named parameter style with %(name)s placeholders.

    Args:
        sql: SQL query string with %s or %(name)s placeholders
        args: tuple/list for positional params or dict for named params
        db: database alias to use
        named: return namedtuple (True) or dict (False)
        count: return row count instead of results
        named_params: DEPRECATED - use dict args instead

    Example:
        # Positional parameters (recommended)
        runrawsql("SELECT * FROM users WHERE id = %s", [user_id])

        # Named parameters (when needed)
        runrawsql("SELECT * FROM users WHERE id = %(user_id)s", {"user_id": user_id})
    """
    from django.db import connections

    cursor = connections[db].cursor()

    # Handle deprecated named_params argument
    if named_params and isinstance(args, dict):
        # Convert format-style to psycopg2 named parameter style
        import re

        # Replace {param} with %(param)s for psycopg2
        sql = re.sub(r"\{(\w+)\}", r"%(\1)s", sql)
        logger.warning(
            "named_params is deprecated. Use dict args with %(name)s placeholders instead."
        )

    # Log query safely (without injecting parameters)
    logger.debug(f"\n\nSQL QUERY: {sql} | ARGS: {args}\n")

    # Execute with proper parameterization
    cursor.execute(sql, args)

    if count:
        return cursor.rowcount
    else:
        return namedtuplefetchall(cursor) if named else dictfetchall(cursor)


def get_action_on_ticket_states(prev_tkt, current_state):
    actions = []
    if prev_tkt and prev_tkt[-1]["previous_state"] and current_state:
        prev_state = prev_tkt[-1]["previous_state"]
        if prev_state["status"] != current_state["status"]:
            actions.append(
                f'''Status Changed From "{prev_state['status']}" To "{current_state['status']}"'''
            )

        if prev_state["priority"] != current_state["priority"]:
            actions.append(
                f'''Priority Changed from "{prev_state['priority']}" To "{current_state['priority']}"'''
            )

        if prev_state["location"] != current_state["location"]:
            actions.append(
                f'''Location Changed from "{prev_state['location']}" To "{current_state['location']}"'''
            )

        if prev_state["ticketdesc"] != current_state["ticketdesc"]:
            actions.append(
                f'''Ticket Description Changed From "{prev_state['ticketdesc']}" To "{current_state['ticketdesc']}"'''
            )

        if prev_state["assignedtopeople"] != current_state["assignedtopeople"]:
            actions.append(
                f'''Ticket Is Reassigned From "{prev_state['assignedtopeople']}" To "{current_state['assignedtopeople']}"'''
            )

        if prev_state["assignedtogroup"] != current_state["assignedtogroup"]:
            actions.append(
                f'''Ticket Is Reassigned From "{prev_state['assignedtogroup']}" To "{current_state['assignedtogroup']}"'''
            )

        if prev_state["comments"] != current_state["comments"] and current_state[
            "comments"
        ] not in ["None", None]:
            actions.append(
                f'''New Comments "{current_state['comments']}" are added after "{prev_state['comments']}"'''
            )
        if prev_state["level"] != current_state["level"]:
            actions.append(
                f"""Ticket level is changed from {prev_state['level']} to {current_state["level"]}"""
            )
        return actions
    return ["Ticket Created"]


def store_ticket_history(instance, request=None, user=None):
    from background_tasks.tasks import send_ticket_email

    now = datetime.now(dt_timezone.utc).replace(microsecond=0, second=0)
    peopleid = request.user.id if request else user.id
    peoplename = request.user.peoplename if request else user.peoplename

    # Get the current state of the ticket
    current_state = {
        "ticketdesc": instance.ticketdesc,
        "assignedtopeople": instance.assignedtopeople.peoplename if instance.assignedtopeople else "Unassigned",
        "assignedtogroup": instance.assignedtogroup.groupname if instance.assignedtogroup else "Unassigned",
        "comments": instance.comments,
        "status": instance.status,
        "priority": instance.priority,
        "location": instance.location.locname if instance.location else "No Location",
        "level": instance.level,
        "isescalated": instance.isescalated,
    }

    # Get the previous state of the ticket, if it exists
    ticketstate = instance.ticketlog["ticket_history"]
    
    details = get_action_on_ticket_states(ticketstate, current_state)

    # Create a dictionary to represent the changes made to the ticket
    history_item = {
        "people_id": peopleid,
        "when": str(now),
        "who": peoplename,
        "assignto": (instance.assignedtogroup.groupname if instance.assignedtogroup else "Unassigned")
        if instance.assignedtopeople_id in [1, None]
        else (instance.assignedtopeople.peoplename if instance.assignedtopeople else "Unassigned"),
        "action": "created",
        "details": details,
        "previous_state": current_state,
    }

    logger.debug(f"{instance.mdtz=} {instance.cdtz=} {ticketstate=} {details=}")

    # Check if there have been any changes to the ticket
    if (
        instance.mdtz > instance.cdtz
        and ticketstate
        and ticketstate[-1]["previous_state"] != current_state
    ):
        history_item["action"] = "updated"

        # Append the history item to the ticket_history list within the ticketlog JSONField
        ticket_history = instance.ticketlog["ticket_history"]
        ticket_history.append(history_item)
        instance.ticketlog = {"ticket_history": ticket_history}
        logger.info("changes have been made to ticket")
    elif instance.mdtz > instance.cdtz:
        history_item["details"] = "No changes detected"
        history_item["action"] = "updated"
        instance.ticketlog["ticket_history"].append(history_item)
        logger.info("no changed detected")
    else:
        instance.ticketlog["ticket_history"] = [history_item]
        send_ticket_email.delay(id=instance.id)
        logger.info("new ticket is created..")
    instance.save()
    logger.info("saving ticket history ended...")


def get_or_create_none_people(using=None):
    # First check if NONE already exists
    try:
        return pm.People.objects.get(peoplecode="NONE")
    except pm.People.DoesNotExist:
        pass
    
    # Create NONE people without triggering dependencies
    obj = pm.People(
        peoplecode="NONE",
        peoplename="NONE",
        email="none@youtility.in",
        dateofbirth="1111-01-01",
        dateofjoin="1111-01-01",
        client_id=None,
        bu_id=None,
        cuser_id=None,
        muser_id=None,
        cdtz=timezone.now().replace(microsecond=0),
        mdtz=timezone.now().replace(microsecond=0),
        ctzoffset=330,
        loginid="none_user"  # Add a unique loginid to avoid constraint issues
    )
    obj.save_base(raw=True)
    return obj


def get_none_typeassist():
    try:
        return ob.TypeAssist.objects.get(id=1)
    except ob.TypeAssist.DoesNotExist:
        o, _ = get_or_create_none_typeassist()
        return o


def get_or_create_none_pgroup():
    obj, _ = pm.Pgroup.objects.get_or_create(
        groupname="NONE",
        defaults={},
    )
    return obj


def get_or_create_none_location():
    try:
        # Try to get existing NONE location first
        obj = Location.objects.get(loccode="NONE", locname="NONE")
        return obj
    except Location.DoesNotExist:
        # If not found, create new one with proper defaults
        from django.db import transaction
        with transaction.atomic():
            obj, created = Location.objects.get_or_create(
                loccode="NONE", 
                locname="NONE",
                defaults={
                    "locstatus": "SCRAPPED",
                    "bu_id": 1,
                    "client_id": 1, 
                    "tenant_id": 1,
                    "cuser_id": 1,
                    "muser_id": 1,
                }
            )
            return obj


def hostname_from_request(request):
    return request.get_host().split(":")[0].lower()


def get_tenants_map():
    return {
        "intelliwiz.youtility.local": "intelliwiz_django",
        "sps.youtility.local": "sps",
        "capgemini.youtility.local": "capgemini",
        "dell.youtility.local": "dell",
        "icicibank.youtility.local": "icicibank",
        "redmine.youtility.in": "sps",
        "django-local.youtility.in": "default",
        "barfi.youtility.in": "icicibank",
        "intelliwiz.youtility.in": "default",
        "testdb.youtility.local": "testDB",
    }


def tenant_db_from_request(request):
    hostname = hostname_from_request(request)
    tenants_map = get_tenants_map()
    return tenants_map.get(hostname, "default")


def get_or_create_none_cap():
    obj, _ = pm.Capability.objects.get_or_create(
        capscode="NONE", capsname="NONE", defaults={}
    )
    return obj


def get_or_create_none_bv():
    # First check if NONE already exists
    try:
        return ob.Bt.objects.get(bucode="NONE")
    except ob.Bt.DoesNotExist:
        pass
    
    # Create without triggering the save override that requires People
    obj = ob.Bt(
        bucode="NONE",
        buname="NONE",
        enable=False,
        siteincharge_id=None,  # Leave as None initially
        cuser_id=None,
        muser_id=None,
        cdtz=timezone.now().replace(microsecond=0),
        mdtz=timezone.now().replace(microsecond=0),
        ctzoffset=330
    )
    # Use save_base to bypass the custom save method
    obj.save_base(raw=True)
    return obj


def get_or_create_none_typeassist():
    obj, iscreated = ob.TypeAssist.objects.get_or_create(
        tacode="NONE", taname="NONE", defaults={}
    )
    return obj, iscreated


def get_or_create_none_tenant():
    return Tenant.objects.get_or_create(
        tenantname="Intelliwiz", subdomain_prefix="intelliwiz", defaults={}
    )[0]


def get_or_create_none_jobneed():
    from datetime import datetime, timezone

    date = datetime(1970, 1, 1, 00, 00, 00).replace(tzinfo=timezone.utc)
    obj, _ = Jobneed.objects.get_or_create(
        jobdesc="NONE",
        scantype="NONE",
        seqno=-1,
        defaults={
            "plandatetime": date,
            "expirydatetime": date,
            "gracetime": 0,
            "receivedonserver": date,
        },
    )
    return obj


def get_or_create_none_wom():
    from datetime import datetime, timezone

    date = datetime(1970, 1, 1, 00, 00, 00).replace(tzinfo=timezone.utc)
    obj, _ = Wom.objects.get_or_create(
        description="NONE",
        expirydatetime=date,
        plandatetime=date,
        defaults={
            "workpermit": Wom.WorkPermitStatus.NOTNEED,
            "attachmentcount": 0,
            "priority": Wom.Priority.LOW,
        },
    )
    return obj


def get_or_create_none_qset():
    obj, _ = QuestionSet.objects.get_or_create(qsetname="NONE", defaults={})
    return obj


def get_or_create_none_question():
    obj, _ = Question.objects.get_or_create(quesname="NONE", defaults={})
    return obj


def get_or_create_none_qsetblng():
    "A None qsetblng with seqno -1"
    obj, _ = QuestionSetBelonging.objects.get_or_create(
        answertype="NONE",
        ismandatory=False,
        seqno=-1,
        defaults={
            "qset": get_or_create_none_qset(),
            "question": get_or_create_none_question(),
        },
    )
    return obj


def get_or_create_none_asset():
    obj, _ = Asset.objects.get_or_create(
        assetcode="NONE",
        assetname="NONE",
        identifier="NONE",
        defaults={"iscritical": False},
    )
    return obj


def get_or_create_none_ticket():
    from apps.y_helpdesk.models import Ticket

    obj, _ = Ticket.objects.get_or_create(ticketdesc="NONE", defaults={})
    return obj


def get_or_create_none_job():
    from datetime import datetime, timezone

    date = datetime(1970, 1, 1, 00, 00, 00).replace(tzinfo=timezone.utc)
    obj, _ = Job.objects.get_or_create(
        jobname="NONE",
        jobdesc="NONE",
        defaults={
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
        },
    )
    return obj


def get_or_create_none_gf():
    obj, _ = ob.GeofenceMaster.objects.get_or_create(
        gfcode="NONE", gfname="NONE", defaults={"alerttext": "NONE", "enable": False}
    )
    return obj


def create_none_entries(self):
    """
    Creates None entries in self relationship models.
    """
    try:
        db = get_current_db_name()
        
        # Create NONE Bt entry first as it's needed for TypeAssist imports
        get_or_create_none_bv()
        
        _, iscreated = get_or_create_none_typeassist()
        if not iscreated:
            # Even if TypeAssist exists, ensure all other NONE entries exist
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


def create_super_admin(db):
    try:
        set_db_for_router(db)
    except ValueError:
        logger.info("Database with this alias not exist operation can't be performed")
    else:
        logger.info(f"Creating SuperUser for {db}")
        from apps.peoples.models import People

        logger.info(
            "please provide required fields in this order single space separated\n"
        )
        logger.info(
            "loginid  password  peoplecode  peoplename  dateofbirth  dateofjoin  email"
        )
        inputs = input().split(" ")
        if len(inputs) == 7:
            user = People.objects.create_superuser(
                loginid=inputs[0],
                password=inputs[1],
                peoplecode=inputs[2],
                peoplename=inputs[3],
                dateofbirth=inputs[4],
                dateofjoin=inputs[5],
                email=inputs[6],
            )
            logger.info(
                f"Operation Successfull!\n Superuser with this loginid {user.loginid} is created"
            )
        else:
            raise ValueError("Please provide all fields!")


THREAD_LOCAL = threading.local()


def get_current_db_name():
    return getattr(THREAD_LOCAL, "DB", "default")


def set_db_for_router(db):
    from django.conf import settings

    dbs = settings.DATABASES
    if db not in dbs:
        raise excp.NoDbError("Database with this alias not exist!")
    setattr(THREAD_LOCAL, "DB", db)
