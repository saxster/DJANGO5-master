from apps.activity.models.asset_model import Asset
from apps.y_helpdesk.models import Ticket
from django.db.models import Value
from django.db.models.functions import Concat
from django.db.models import Q
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.utils import timezone
import apps.peoples.utils as putils
import json
import re
import logging
from datetime import datetime, timezone as dt_timezone

logger = logging.getLogger("django")


def serialize_obj(obj):
    """Convert a Django model instance to a dict and format GPS location."""
    from django.contrib.gis.geos import Point

    data = dict(obj)
    gps = data.get("gpslocation")
    if isinstance(gps, Point):
        data["gpslocation"] = [gps.y, gps.x]  # latitude, longitude
    return data


def get_assetincludes_choices(request):
    """Return a list of checkpoint asset choices for the current session."""
    S = request.session
    qset = (
        Asset.objects.filter(
            Q(identifier__in=["CHECKPOINT"])
            & Q(enable=True)
            & Q(bu_id=S["bu_id"])
            & Q(assetcode="NONE")
        )
        .select_related("parent")
        .annotate(checkpoint=Concat("assetname", Value(" ("), "assetcode", Value(")")))
    )
    return qset.values_list("id", "checkpoint")


def get_assetsmartplace_choices(request, idfs):
    """Return asset choices for the given identifiers and current session."""
    S = request.session
    qset = (
        Asset.objects.filter(
            Q(identifier__in=idfs)
            & Q(enable=True)
            & Q(bu_id=S["bu_id"])
            & Q(client_id=S["client_id"])
            | Q(assetcode="NONE")
        )
        .select_related("parent")
        .annotate(checkpoint=Concat("assetname", Value(" ("), "assetcode", Value(")")))
    )
    return qset.values_list("id", "checkpoint")


def validate_alertbelow(forms, data):
    """Ensure ``alertbelow`` is greater than ``min``."""
    min, alertbelow = float(data["min"]), float(data["alertbelow"])
    msg = "Alert below should be greater than minimum value."
    if alertbelow < min:
        raise forms.ValidationError(msg)
    return alertbelow


def validate_alertabove(forms, data):
    """Ensure ``alertabove`` is less than ``max``."""
    max, alertabove = float(data["max"]), float(data["alertabove"])
    msg = "Alert above should be smaller than maximum value."
    if alertabove > max:
        raise forms.ValidationError(msg)
    logger.debug("utils %s", alertabove)
    return alertabove


def validate_options(forms, val):
    """Extract option values from a JSON string or comma-separated values."""
    if not val:
        return val
    
    # First try to parse as JSON (for backward compatibility)
    try:
        obj = json.loads(val)
        if isinstance(obj, list) and obj and isinstance(obj[0], dict):
            # If it's a list of dicts with 'value' keys
            options = [i["value"] for i in obj]
            return ",".join(options)
    except (ValueError, TypeError, KeyError):
        pass
    
    # If not JSON or doesn't match expected format, treat as comma-separated string
    # Clean up the string: remove extra spaces around commas
    cleaned = val.strip()
    if cleaned:
        # Split by comma and clean each option
        options = [opt.strip() for opt in cleaned.split(',') if opt.strip()]
        return ",".join(options)
    
    return val


def validate_alerton(forms, val):
    """Normalize an ``alerton`` string into a comma-separated list."""
    input_string = val.replace("[", "")
    input_string = input_string.replace("]", "")
    input_string = input_string.replace("'", "")
    input_string = input_string.replace('"', "")
    clean_string = re.sub(r",\s*", ",", input_string)
    return clean_string


def initialize_alertbelow_alertabove(instance, form):
    """Populate ``alertbelow`` and ``alertabove`` form fields from ``alerton``."""
    alerton, below, above, li = instance.alerton, "", "", []
    logger.debug(alerton)
    if alerton and ("<" in alerton or ">" in alerton):
        s1 = alerton.replace(">", "")
        s2 = s1.replace(",", "")
        s3 = s2.replace("<", "")
        li = s3.split(" ")
        form.fields["alertbelow"].initial = float(li[0]) if len(li) > 0 else None
        form.fields["alertabove"].initial = float(li[1]) if len(li) > 1 else None


def init_assetincludes(form):
    """Initialize ``assetincludes`` field from the form instance."""
    form.fields["assetincludes"].initial = form.instance.assetincldes


def insert_questions_to_qsetblng(assigned_questions, model, fields, request):
    """Create or update question set bindings in bulk."""
    from django.db import transaction

    try:
        with transaction.atomic():
            for ques in assigned_questions:
                qsetbng, created = model.objects.update_or_create(
                    question_id=ques[2],
                    qset_id=fields["qset"],
                    client_id=fields["client"],
                    defaults={
                        "seqno": ques[0],
                        "question_id": ques[2],
                        "answertype": ques[3],
                        "min": float(ques[4]),
                        "max": float(ques[5]),
                        "options": ques[6].replace('"', "")
                        if isinstance(ques[6], str)
                        else "",
                        "alerton": ques[7].replace('"', "")
                        if isinstance(ques[7], str)
                        else "",
                        "ismandatory": ques[8],
                        "isavpt": ques[9],
                        "avpttype": ques[10],
                        "qset_id": fields["qset"],
                    },
                )
                qsetbng.save()
                putils.save_userinfo(qsetbng, request.user, request.session)

    except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError, json.JSONDecodeError):
        logger.critical("something went wrong", exc_info=True)
        raise


def get_assignedsitedata(request):
    """Return BU ids for sites assigned to the current user."""
    bu_list = []
    from apps.client_onboarding.models import Bt

    try:
        data = Bt.objects.get_people_bu_list(request.user).values(
            "id", "bu", "assignsites"
        )
        logger.debug("get_assignedsitedata data %s", data)
        for x in data:
            logger.debug("%s %s", x["assignsites"], x)
            bu_list.append(x["assignsites"])
        bu_list.append(request.user.bu_id)
        logger.debug("%s %s", data.query, bu_list)
    except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError, json.JSONDecodeError):
        logger.critical("get_assignedsitedata() exception", exc_info=True)
        bu_list.append(request.user.bu_id)
    return bu_list


def column_filter(
    col0,
    col1,
    col2,
    col3,
    col4,
    col5,
    colval0,
    colval1,
    colval2,
    colval3,
    colval4,
    colval5,
    start_utc,
):
    """Build ORM filter kwargs for datatable column search values."""
    # sourcery skip: extract-duplicate-method, extract-method
    kwargs = {}
    if (
        colval0 != ""
        or colval1 != ""
        or colval2 != ""
        or colval3 != ""
        or colval4 != ""
    ):
        logger.debug("1")
    if colval0 != "":
        val0 = colval0.split("(")[1].strip(")").strip()
        col0 = f"{col0}__icontains"
        kwargs[col0] = val0
    if colval2 != "":
        val2 = colval2.split("(")[1].strip(")").strip()
        logger.debug("ncal1 %s %s", type(val2), val2)
        col2 = f"{col2}__icontains"
        kwargs[col2] = val2
    if colval3 != "":
        val3 = colval3.split("(")[1].strip(")").strip()
        col3 = f"{col3}__icontains"
        kwargs[col3] = val3
    if colval4 != "":
        val4 = colval4.split("(")[1].strip(")").strip()
        col4 = f"{col4}__icontains"
        kwargs[col4] = val4
    if colval5 != "":
        val5 = colval5.split("(")[1].strip(")").strip()
        col5 = f"{col5}__icontains"
        kwargs[col5] = val5
    if colval1 != "":
        val1 = colval1.split("(")[1].strip(")").strip()
        if start_utc != "":
            val1 = val1.split("-")
            col1 = f"{col1}__range"
            mystr = "".join(map(str, val1[1].strip())) + " 23:59"
            date_time_obj_start = datetime.strptime(val1[0].strip(), "%m/%d/%Y")
            date_time_obj_end = datetime.strptime(mystr, "%m/%d/%Y %H:%M")
            startdateobj = date_time_obj_start.astimezone(dt_timezone.utc).replace(
                microsecond=0
            )
            enddateobj = date_time_obj_end.astimezone(dt_timezone.utc).replace(microsecond=0)
            kwargs[col1] = [startdateobj, enddateobj]
        else:
            kwargs[col1] = val1
    return kwargs


def getdatatable_filter(request):
    """Parse datatable request parameters and return filter values."""
    # SECURITY FIX (IDOR-004): Validate and sanitize datatable parameters
    logger.debug("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
    try:
        col0 = request.GET.get("columns[0][data]", "").strip()
        col1 = request.GET.get("columns[1][data]", "").strip()
        col2 = request.GET.get("columns[2][data]", "").strip()
        col3 = request.GET.get("columns[3][data]", "").strip()
        col4 = request.GET.get("columns[4][data]", "").strip()
        col5 = request.GET.get("columns[5][data]", "").strip()
        colval0 = request.GET.get("columns[0][search][value]", "").strip()
        colval1 = request.GET.get("columns[1][search][value]", "").strip()
        colval2 = request.GET.get("columns[2][search][value]", "").strip()
        colval3 = request.GET.get("columns[3][search][value]", "").strip()
        colval4 = request.GET.get("columns[4][search][value]", "").strip()
        colval5 = request.GET.get("columns[5][search][value]", "").strip()

        # Validate pagination parameters are positive integers
        length = request.GET.get("length", "10")
        start = request.GET.get("start", "0")
        try:
            length = int(length)
            start = int(start)
            if length < 1 or start < 0:
                raise ValueError("Invalid pagination parameters")
        except (ValueError, TypeError):
            length, start = 10, 0  # Default safe values
    except (KeyError, AttributeError) as e:
        logger.error(f"Error parsing datatable parameters: {e}")
        raise
    return (
        col0,
        col1,
        col2,
        col3,
        col4,
        col5,
        colval0,
        colval1,
        colval2,
        colval3,
        colval4,
        colval5,
        length,
        start,
    )


def datastatus(request, id_id):
    """Return formatted status history from a ticket log."""
    from datetime import datetime

    listObj = []
    for i in id_id.ticketlog["statusjbdata"]:
        jsonelement = json.loads(i)
        if jsonelement["performedby"] == jsonelement["assignedto"]:
            logger.debug("%s %s", jsonelement["performedby"], jsonelement["assignedto"])
            jsonelement["performedby"] = "You"
            jsonelement["assignedto"] = "Self"
        if str(jsonelement["performedby"]) == str(request.user):
            jsonelement["performedby"] = "You"
            logger.debug("%s %s", jsonelement["performedby"], request.user)
        x = jsonelement["datetime"]
        date_time_obj = datetime.strptime(x, "%Y-%m-%d %H:%M:%S")
        jsonelement["datetime"] = date_time_obj.strftime("%d %b %y %H:%M:%S")
        listObj.append(jsonelement)
    logger.debug("listObj %s", listObj)
    return listObj


def sendTicketMail(ticketid, oper):
    """Send notification emails for a ticket."""
    try:
        ticketdata = Ticket.objects.send_ticket_mail(ticketid)
        logger.debug("ticketdata: %s", ticketdata)
        records = [
            {
                "cdtz": record.createdon,
                "ticketlog": record.ticketlog,
                "modifiedon": record.modifiedon,
                "status": record.status,
                "ticketdesc": record.ticketdesc,
                "ticketno": record.ticketno,
                "creatoremail": record.creatoremail,
                "modifiermail": record.modifiermail,
                "modifiername": record.modifiername,
                "peopleemail": record.peopleemail,
                "pgroupemail": record.pgroupemail,
                "tescalationtemplate": record.tescalationtemplate,
                "priority": record.priority,
                "peoplename": record.peoplename,
                "next_escalation": record.next_escalation,
                "creatorid": record.creatorid,
                "modifierid": record.modifierid,
                "assignedtopeople_id": record.assignedtopeople_id,
                "assignedtogroup_id": record.assignedtogroup_id,
                "groupname": record.groupname,
                "buname": record.buname,
                "level": record.level,
                "comments": record.comments,
            }
            for record in ticketdata
        ]
        # sendEscalationTicketMail(records, oper, 'WEB')
    except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        logger.critical("sendTicketMail() exception: %s", e)


def savejsonbdata(request, id_id, asset, location):
    """Append a status entry to the ticket JSON log."""
    if str(id_id.assignedtogroup) != "NONE":
        assignedto = id_id.assignedtogroup
    elif str(id_id.assignedtopeople) != "NONE":
        assignedto = id_id.assignedtopeople
    ticketlog = {
        "performedby": id_id.performedby,
        "status": id_id.status,
        "datetime": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
        "comments": id_id.comments,
        "assignedto": assignedto,
        "asset": asset,
        "location": location,
    }

    id_id.ticketlog["statusjbdata"].append(json.dumps(ticketlog, default=str))
    return id_id


def increment_ticket_number():
    """Return the next available ticket number."""
    last_ticket = Ticket.objects.order_by("ticketno").last()
    if not last_ticket:
        return "1"
    logger.debug(last_ticket)
    last_id = last_ticket.ticketno
    return last_id + 1


# Note: converttodict function has been removed
# All SQL queries have been migrated to Django ORM
# Use Django ORM methods instead of raw SQL execution


def childlist_viewdata(request, hostname):
    """Return ticket event list for a specific host."""
    # SECURITY FIX (IDOR-005): Validate and sanitize parameters
    ticketno = request.GET.get("ticketno", "").strip()
    if not ticketno:
        raise ValueError("ticketno parameter is required")

    # Validate column index is numeric
    column = request.GET.get("order[0][column]", "0")
    try:
        column = int(column)
        if column < 0:
            column = 0
    except (ValueError, TypeError):
        column = 0

    logger.debug("childlist_viewdata column %s", column)
    columnname = request.GET.get(f"columns[{column}][data]", "").strip()
    columnsort = request.GET.get("order[0][dir]", "asc").strip()

    # Validate sort direction
    if columnsort not in ['asc', 'desc']:
        columnsort = 'asc'

    logger.debug("list_viewdata %s", columnname)

    # Validate pagination parameters
    try:
        length = int(request.GET.get("length", "10"))
        start = int(request.GET.get("start", "0"))
        if length < 1 or start < 0:
            raise ValueError("Invalid pagination parameters")
    except (ValueError, TypeError):
        length, start = 10, 0
    
    # Use the ORM version directly - no need for cursor
    records, _ = ticketevents_query(ticketno, columnsort, columnname)
    
    return records, length, start


def ticketevents_query(ticketno, columnsort, columnname):
    """
    DEPRECATED: This function has been replaced with Django ORM implementation.
    Use ticketevents_query_orm from utils_orm module instead.
    
    The ORM version eliminates PostgreSQL-specific array functions (string_to_array, unnest)
    and provides the same functionality with better security.
    """
    from .utils_orm import ticketevents_query_orm
    # Return the ORM results directly instead of SQL query
    results = ticketevents_query_orm(ticketno, columnsort, columnname)
    return results, None  # Return None for params since we're not using raw SQL


def list_viewdata(request, model, fields, kwargs):
    """Return objects for datatable pagination and sorting."""
    # SECURITY FIX (IDOR-006): Validate and sanitize parameters
    column = request.GET.get("order[0][column]", "0")
    try:
        column = int(column)
        if column < 0:
            column = 0
    except (ValueError, TypeError):
        column = 0

    columnname = request.GET.get(f"columns[{column}][data]", "").strip()
    columnsort = request.GET.get("order[0][dir]", "asc").strip()

    # Validate sort direction
    if columnsort not in ['asc', 'desc']:
        columnsort = 'asc'

    # Validate pagination parameters
    try:
        length = int(request.GET.get("length", "10"))
        start = int(request.GET.get("start", "0"))
        if length < 1 or start < 0:
            raise ValueError("Invalid pagination parameters")
    except (ValueError, TypeError):
        length, start = 10, 0
    objects = model.objects.filter(bu=request.session["bu_id"], **kwargs).values(
        *fields
    )
    if columnsort != "asc":
        objects = objects.order_by(f"-{columnname}")
    else:
        objects = objects.order_by(columnname)
    count = objects.count()
    filtered = count
    jsondata = {"data": list(objects[start : start + length])}
    return length, start, objects


def save_assetjsonform(jsonform, asset):
    """Persist extra asset metadata from a form."""
    try:
        logger.info("saving jsonform ...")
        for k in [
            "supplier",
            "meter",
            "invoice_no",
            "invoice_date",
            "is_nonengg_asset",
            "service",
            "sfdate",
            "stdate",
            "yom",
            "msn",
            "bill_val",
            "ismeter",
            "bill_date",
            "purchase_date",
            "inst_date",
            "po_number",
            "far_asset_id",
        ]:
            asset.asset_json[k] = jsonform.cleaned_data.get(k)
    except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError, json.JSONDecodeError):
        logger.critical("save_jsonform(jsonform, p)... FAILED", exc_info=True)
        raise
    else:
        logger.info("jsonform saved DONE ... ")
        return True


def get_asset_jsonform(people, request):
    """Return an AssetExtrasForm populated from a people instance."""
    try:
        logger.info("people prefform (json form) retrieving...")
        from apps.activity.forms.asset_form import AssetExtrasForm

        d = {
            k: v
            for k, v in people.asset_json.items()
            if k
            in (
                "supplier",
                "meter",
                "invoice_no",
                "invoice_date",
                "service",
                "sfdate",
                "stdate",
                "yom",
                "msn",
                "bill_val",
                "ismeter",
                "bill_date",
                "purchase_date",
                "inst_date",
                "po_number",
                "far_asset_id",
                "is_nonengg_asset",
            )
        }

    except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError, json.JSONDecodeError):
        logger.critical("get_asset_jsonform(people)... FAILED", exc_info=True)
        raise
    else:
        logger.info("people prefform (json form) retrieved... DONE")
        return AssetExtrasForm(data=d, request=request)


import qrcode
from qrcode.image.svg import SvgImage


def generate_qr_code_images(data, size=1):
    """Return a list containing a base64 encoded SVG QR code."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=size,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    qr_code_img = qr.make_image(
        image_factory=SvgImage, fill_color="black", back_color="white"
    )

    # Convert the SVG image to bytes
    img_bytes = io.BytesIO()
    qr_code_img.save(img_bytes)
    img_bytes.seek(0)

    # Encode image to base64 string
    img_base64 = base64.b64encode(img_bytes.getvalue()).decode("utf-8")
    return f"data:image/svg+xml;base64,{img_base64}"


from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from apps.core.utils_new.retry_mechanism import with_retry


@with_retry(
    exceptions=(GeocoderTimedOut, GeocoderServiceError),
    max_retries=3,
    retry_policy='EXTERNAL_API'
)
def get_address_from_coordinates(
    latitude: float, longitude: float, max_retries: int = 3
) -> dict:
    """Lookup an address using latitude and longitude via Nominatim.

    Uses exponential backoff retry mechanism for geocoding API calls.
    """
    # Initialize the geocoder with a custom user agent
    geolocator = Nominatim(user_agent="my_geocoder_app")

    # Get location data from coordinates
    location = geolocator.reverse((latitude, longitude), language="en")

    if location and location.raw.get("address"):
        address = location.raw["address"]

        # Create a structured response
        result = {
            "full_address": location.address,
            "street": address.get("road", ""),
            "city": address.get(
                "city", address.get("town", address.get("village", ""))
            ),
            "state": address.get("state", ""),
            "country": address.get("country", ""),
            "postal_code": address.get("postcode", ""),
        }

        return result

    return None
