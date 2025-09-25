"""
DEFINE FUNCTIONS AND CLASSES WERE CAN BE USED GLOBALLY.
"""

import json
from pprint import pformat
from django.db.models import Q

import logging

logger = logging.getLogger("django")


from apps.core.utils_new.business_logic import *
from apps.core.utils_new.date_utils import *
from apps.core.utils_new.db_utils import *
from apps.core.utils_new.file_utils import *
from apps.core.utils_new.http_utils import *
from apps.core.utils_new.string_utils import *
from apps.core.utils_new.validation import *


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
