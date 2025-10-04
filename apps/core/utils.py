"""
DEFINE FUNCTIONS AND CLASSES WERE CAN BE USED GLOBALLY.
"""

import json
from pprint import pformat
from django.db.models import Q

import logging

logger = logging.getLogger("django")


# Explicit imports to avoid namespace pollution
from apps.core.utils_new.string_utils import (
    CustomJsonEncoderWithDistance, encrypt, decrypt, clean_record,
    getformatedjson, sumDig, orderedRandom, format_data
)

# Explicit imports from business_logic (23 items)
from apps.core.utils_new.business_logic import (
    JobFields, Instructions, get_appropriate_client_url,
    save_capsinfo_inside_session, save_user_session, update_timeline_data,
    process_wizard_form, update_wizard_form, update_prev_step,
    update_next_step, update_other_info, update_wizard_steps,
    save_msg, initailize_form_fields, apply_error_classes,
    get_instance_for_update, get_model_obj, get_index_for_deletion,
    delete_object, delete_unsaved_objects, cache_it, get_from_cache
)

# Explicit imports from date_utils (7 items)
from apps.core.utils_new.date_utils import (
    get_current_year, to_utc, getawaredatetime, format_timedelta,
    convert_seconds_to_human_readable, get_timezone, find_closest_shift
)

# Explicit imports from db_utils (32 items)
from apps.core.utils_new.db_utils import (
    save_common_stuff, create_tenant_with_alias, check_nones,
    get_record_from_input, dictfetchall, namedtuplefetchall,
    runrawsql, get_action_on_ticket_states, store_ticket_history,
    get_or_create_none_people, get_none_typeassist, get_or_create_none_pgroup,
    get_or_create_none_location, hostname_from_request, get_tenants_map,
    tenant_db_from_request, get_or_create_none_cap, get_or_create_none_bv,
    get_or_create_none_typeassist, get_or_create_none_tenant,
    get_or_create_none_jobneed, get_or_create_none_wom, get_or_create_none_qset,
    get_or_create_none_question, get_or_create_none_qsetblng,
    get_or_create_none_asset, get_or_create_none_ticket, get_or_create_none_job,
    get_or_create_none_gf, create_none_entries, create_super_admin,
    THREAD_LOCAL, get_current_db_name, set_db_for_router
)

# Explicit imports from file_utils (11 items)
from apps.core.utils_new.file_utils import (
    HEADER_MAPPING, Example_data, HEADER_MAPPING_UPDATE, Example_data_update,
    get_home_dir, upload, upload_vendor_file, download_qrcode,
    excel_file_creation, excel_file_creation_update, get_type_data
)

# Explicit imports from http_utils (20 items)
from apps.core.utils_new.http_utils import (
    clean_encoded_form_data, get_clean_form_data, handle_other_exception,
    handle_does_not_exist, get_filter, searchValue, searchValue2,
    render_form, handle_DoesNotExist, handle_Exception, render_form_for_delete,
    handle_RestrictedError, handle_EmptyResultSet, handle_intergrity_error,
    render_form_for_update, handle_invalid_form, render_grid,
    paginate_results, get_paginated_results, get_paginated_results2
)

# Explicit imports from validation (7 items)
from apps.core.utils_new.validation import (
    clean_gpslocation, isValidEMEI, verify_mobno, verify_emailaddr,
    verify_loginid, verify_peoplename, validate_date_format
)

# Keep module references for backwards compatibility
from apps.core.utils_new import business_logic
from apps.core.utils_new import date_utils
from apps.core.utils_new import db_utils
from apps.core.utils_new import file_utils
from apps.core.utils_new import http_utils
from apps.core.utils_new import string_utils
from apps.core.utils_new import validation


__all__ = (
    business_logic.__all__ +
    date_utils.__all__ +
    db_utils.__all__ +
    file_utils.__all__ +
    http_utils.__all__ +
    string_utils.__all__ +
    validation.__all__ +
    [
        'display_post_data',
        'PD',
        'alert_observation',
        'printsql',
        'get_select_output',
        'get_qobjs_dir_fields_start_length',
        'ok',
        'failed',
        'get_email_addresses',
        'send_email',
        'create_client_site',
        'create_user',
        'basic_user_setup',
        'get_changed_keys',
        'generate_timezone_choices',
    ]
)


def display_post_data(post_data):
    logger.info("\n%s", (pformat(post_data, compact=True)))


def PD(data=None, post=None, get=None, instance=None, cleaned=None):
    """
    Prints Data (DD)
    """
    if post:
        logger.debug(
            f"POST data recived from client: {pformat(post, compact = True)}\n"
        )
    elif get:
        logger.debug(f"GET data recived from client: {pformat(get, compact = True)}\n")
    elif cleaned:
        logger.debug(
            f"CLEANED data after processing {pformat(cleaned, compact = True)}\n"
        )
    elif instance:
        logger.debug(
            f"INSTANCE data recived from DB {pformat(instance, compact = True)}\n"
        )
    else:
        logger.debug(f"{pformat(data, compact = True)}\n")


# import face_recognition
def alert_observation(pk, event):
    raise NotImplementedError()


def printsql(objs):
    from django.core.exceptions import EmptyResultSet

    try:
        logger.info(f"SQL QUERY:\n {objs.query.__str__()}")
    except EmptyResultSet:
        logger.info("NO SQL")


def get_select_output(objs):
    if not objs:
        return None, 0, "No records"
    records = json.dumps(list(objs), default=str)
    count = objs.count()
    msg = f"Total {count} records fetched successfully!"
    return records, count, msg


def get_qobjs_dir_fields_start_length(R):
    qobjs = None
    if R.get("search[value]"):
        qobjs = searchValue2(R.getlist("fields[]"), R["search[value]"])

    orderby, fields = R.getlist("order[0][column]"), R.getlist("fields[]")
    orderby = [orderby] if not isinstance(orderby, list) else orderby
    length, start = int(R["length"]), int(R["start"])

    for order in orderby:
        if order:
            key = R[f"columns[{order}][data]"]
            dir = f"-{key}" if R["order[0][dir]"] == "desc" else f"{key}"
        else:
            dir = "-mdtz"
    if not orderby:
        dir = "-mdtz"
    return qobjs, dir, fields, length, start


def ok(self):
    self.stdout.write(self.style.SUCCESS("DONE"))


def failed(self):
    self.stdout.write(self.style.ERROR("FAILED"))


def get_email_addresses(people_ids, group_ids=None, buids=None):
    from apps.peoples.models import People, Pgbelonging

    p_emails, g_emails = [], []
    if people_ids:
        p_emails = list(
            People.objects.filter(~Q(peoplecode="NONE"), id__in=people_ids).values_list(
                "email", flat=True
            )
        )
    if group_ids:
        g_emails = list(
            Pgbelonging.objects.select_related("pgroup")
            .filter(~Q(people_id=1), pgroup_id__in=group_ids, assignsites_id=1)
            .values_list("people__email", flat=True)
        )
    return list(set(p_emails + g_emails)) or []


def send_email(subject, body, to, from_email=None, atts=None, cc=None):
    if atts is None:
        atts = []
    from django.core.mail import EmailMessage
    from django.conf import settings

    logger.info("email sending process started")
    msg = EmailMessage()
    msg.subject = subject
    logger.info(f"subject of email is {subject}")
    msg.body = body
    msg.from_email = from_email or settings.DEFAULT_FROM_EMAIL
    msg.to = to
    if cc:
        msg.cc = cc
    logger.info(f"recipents of email are  {to}")
    msg.content_subtype = "html"
    for attachment in atts:
        msg.attach_file(attachment)
    if atts:
        logger.info(f"Total {len(atts)} found and added to the message")
    msg.send()
    logger.info("email successfully sent")


def create_client_site():
    from apps.onboarding.models import Bt, TypeAssist

    client_type, _ = TypeAssist.objects.get_or_create(tacode="CLIENT", taname="Client")
    site_type, _ = TypeAssist.objects.get_or_create(
        tacode="SITE",
        taname="Site",
    )
    client, _ = Bt.objects.get_or_create(
        bucode="TESTCLIENT", buname="Test Client", identifier=client_type, id=4
    )
    site, _ = Bt.objects.get_or_create(
        bucode="TESTBT", buname="Test Bt", identifier=site_type, parent=client, id=5
    )
    return client, site


def create_user():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user, _ = User.objects.get_or_create(
        loginid="testuser",
        id=4,
        dateofbirth="2022-05-22",
        peoplecode="TESTUSER",
        peoplename="Test User",
        email="testuser@gmail.com",
        isverified=True,
    )
    user.set_password("testpassword")
    user.save()
    return user


def basic_user_setup():
    """
    sets up the basic user setup
    and returns the client
    """
    from django.urls import reverse
    from django.test import Client

    # create user, client and site and assign (client, site) it to user
    user = create_user()
    (
        _client,
        _site,
    ) = create_client_site()
    user.client = _client
    user.bu = _site
    user.save()

    # initialize the test client
    client = Client()

    # request the login page, this sets up test_cookies like browser
    client.get(reverse("login"))

    # post request to login, this saves the session data for the user
    response = client.post(
        reverse("login"),
        data={"username": "testuser", "password": "testpassword", "timezone": 330},
    )

    # get request from the response
    request = response.wsgi_request

    # simulate the login of the client
    client.login(
        **{"username": "testuser", "password": "testpassword", "timezone": 330}
    )

    # update the default session data with user session data got from post request
    session = client.session
    session.update(dict(request.session))
    session.save()
    return client


def get_changed_keys(dict1, dict2):
    """
    This function takes two dictionaries as input and returns a list of keys
    where the corresponding values have changed from the first dictionary to the second.
    """

    # Handle edge cases where either of the inputs is not a dictionary
    if not isinstance(dict1, dict) or not isinstance(dict2, dict):
        raise TypeError("Both arguments should be of dict type")

    # Create a list to hold keys with changed values
    changed_keys = []

    # Compare values of common keys in the dictionaries
    for key in dict1.keys() & dict2.keys():
        if dict1[key] != dict2[key]:
            changed_keys.append(key)

    return changed_keys


def generate_timezone_choices():
    from pytz import common_timezones
    from pytz import timezone as pytimezone
    from datetime import datetime

    utc = pytimezone("UTC")
    now = datetime.now(utc)
    choices = [("", "")]

    for tz_name in common_timezones:
        tz = pytimezone(tz_name)
        offset = now.astimezone(tz).strftime("%z")
        offset_sign = "+" if offset[0] == "+" else "-"
        offset_digits = int(
            offset.lstrip("+").lstrip("-")
        )  # Remove the sign before converting to int
        offset_hours = abs(
            int(offset_digits // 100)
        )  # Integer division to get the hours
        offset_minutes = offset_digits % 100  # Modulus to get the minutes
        formatted_offset = f"UTC {offset_sign}{offset_hours:02d}:{offset_minutes:02d}"
        choices.append(
            (f"{tz_name} ({formatted_offset})", f"{tz_name} ({formatted_offset})")
        )

    return choices
