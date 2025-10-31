from logging import getLogger
from datetime import datetime
import re

from django.core.exceptions import ValidationError
from django.utils import timezone

log = getLogger("mobile_service_log")


def checkHex(s):
    return not any(((ch < "0" or ch > "9") and (ch < "A" or ch > "F")) for ch in s)


def clean_point_field(val):
    from django.contrib.gis.geos import GEOSGeometry
    from math import isnan

    # Handle NaN and float values
    if isinstance(val, float):
        if isnan(val):
            return None
        # Convert float to string if it's a valid number
        val = str(val)
    
    if not val or val in ["None", "NONE", "nan", "NaN"]:
        return None
    
    # Ensure val is a string before processing
    val = str(val).strip()
    
    if not val:
        return None
    
    if checkHex(val):
        return GEOSGeometry(val)
    if "SRID" not in val:
        lat, lng = val.split(",")
        return GEOSGeometry(f"SRID=4326;POINT({lng} {lat})")
    return GEOSGeometry(val)


def clean_code(val):
    if val:
        val = str(val)
        return val.upper()


def clean_text(val):
    if val:
        val = str(val)
        return val


def clean_datetimes(val, offset):

    if val:
        log.info(f"beforing cleaning {val}")
        if val in ["None", "NONE", ""]:
            return None
        val = val.replace("+00:00", "")
        val = datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
        val = val.replace(tzinfo=timezone.utc, microsecond=0)
        log.info(f"after cleaning {val}")
    return val


def clean_date(val):
    from datetime import datetime

    return datetime.strptime(val, "%Y-%m-%d")


def clean_record(record):
    """
    Cleans the record like code,
    desc, gps fields, datetime fields etc
    """
    # Handle Tracking model field mapping
    if "identifier" in record and record.get("identifier") == "TRACKING":
        # Map fields for Tracking model
        tracking_record = {}
        
        # Direct mappings
        if "uuid" in record:
            tracking_record["uuid"] = record["uuid"]
        if "deviceid" in record:
            tracking_record["deviceid"] = record["deviceid"]
        if "people_id" in record:
            tracking_record["people_id"] = record["people_id"]
        if "transportmode" in record:
            tracking_record["transportmode"] = record["transportmode"]
        if "reference" in record:
            tracking_record["reference"] = record["reference"]
        if "identifier" in record:
            tracking_record["identifier"] = record["identifier"]
        
        # Convert lat/lng to gpslocation PointField
        if "latitude" in record and "longitude" in record:
            lat = record["latitude"]
            lng = record["longitude"]
            tracking_record["gpslocation"] = clean_point_field(f"{lat},{lng}")
        
        # Map datetime to receiveddate
        if "datetime" in record:
            tracking_record["receiveddate"] = clean_datetimes(record["datetime"], record.get("ctzoffset", 0))
        
        return tracking_record
    
    # Handle Jobneed model field mapping
    # Check for jobneed records - they have jobdesc and may or may not have details
    if "jobdesc" in record or "jobType" in record or "endTime" in record:
        # This is a Jobneed record from mobile app - map field names
        jobneed_record = {}
        
        # Field name mappings from mobile app to Django model
        field_mappings = {
            "gpsLocation": "gpslocation",
            "endTime": "endtime", 
            "startTime": "starttime",
            "planDateTime": "plandatetime",
            "receivedOnServer": "receivedonserver",
            "scanType": "scantype",
            "jobType": "jobtype",
            "otherInfo": "other_info"
        }
        
        # Apply field name mappings
        for mobile_field, django_field in field_mappings.items():
            if mobile_field in record:
                jobneed_record[django_field] = record[mobile_field]
        
        # Copy fields that don't need mapping
        direct_fields = [
            "uuid", "jobdesc", "gracetime", "remarks", "asset_id", "job_id", 
            "jobstatus", "performedby_id", "priority", "qset_id", "people_id",
            "pgroup_id", "sgroup_id", "identifier", "parent_id", "alerts", "seqno",
            "client_id", "bu_id", "ticketcategory_id", "multifactor",
            "raisedtktflag", "ismailsent", "attachmentcount", "deviation", "remarkstype_id",
            "cdtz", "mdtz", "cuser_id", "muser_id", "ctzoffset", "jobtype"
        ]
        
        for field in direct_fields:
            if field in record:
                jobneed_record[field] = record[field]
        
        # Check if this is an ADHOC record before handling ticket_id
        is_adhoc_record = (record.get("jobtype") == "ADHOC" or 
                          record.get("identifier", "").startswith("ADHOC") or
                          "ADHOC" in record.get("identifier", ""))
        
        # Handle ticket_id specially - for ADHOC records, create proper ticket
        if "ticket_id" in record:
            ticket_id = record["ticket_id"]
            # For ADHOC records with ticket_id=0, get/create a proper none ticket
            if is_adhoc_record and ticket_id == 0:
                from apps.core.utils_new.db_utils import get_or_create_none_ticket
                none_ticket = get_or_create_none_ticket()
                jobneed_record["ticket_id"] = none_ticket.id
            else:
                jobneed_record["ticket_id"] = None if ticket_id == 0 else ticket_id
        elif is_adhoc_record:
            # For ADHOC records where ticket_id is missing entirely, create a proper ticket
            from apps.core.utils_new.db_utils import get_or_create_none_ticket
            none_ticket = get_or_create_none_ticket()
            jobneed_record["ticket_id"] = none_ticket.id
        else:
            # For non-ADHOC records (like TOUR), if ticket_id is missing, set it to 1
            jobneed_record["ticket_id"] = 1
        
        # Handle special field conversions
        if "gpsLocation" in record:
            jobneed_record["gpslocation"] = clean_point_field(record["gpsLocation"])
        
        # Handle isDynamic -> other_info conversion
        if "isDynamic" in record or "otherInfo" in record:
            other_info_data = {}
            if "otherInfo" in record:
                import json
                if isinstance(record["otherInfo"], str):
                    try:
                        other_info_data = json.loads(record["otherInfo"])
                    except json.JSONDecodeError:
                        other_info_data = {}
                else:
                    other_info_data = record["otherInfo"]
            
            if "isDynamic" in record:
                other_info_data["isdynamic"] = record["isDynamic"] == "true"
            
            jobneed_record["other_info"] = other_info_data
        
        # Handle ADHOC identifier mapping
        if "identifier" in jobneed_record:
            identifier_mappings = {
                "ADHOCINTERNALTOUR": "INTERNALTOUR",
                "ADHOCEXTERNALTOUR": "EXTERNALTOUR",
                "ADHOC": "TASK"
            }
            if jobneed_record["identifier"] in identifier_mappings:
                jobneed_record["identifier"] = identifier_mappings[jobneed_record["identifier"]]
        
        # Set default values for required fields in ADHOC records
        is_adhoc = (record.get("jobtype") == "ADHOC" or 
                   record.get("identifier", "").startswith("ADHOC") or
                   "ADHOC" in record.get("identifier", ""))
        
        if is_adhoc:
            # Set default values for required fields that are missing
            defaults = {
                "gracetime": 0,
                "priority": "MEDIUM",
                "seqno": 1
            }
            
            for field, default_value in defaults.items():
                if field not in jobneed_record or not jobneed_record[field]:
                    jobneed_record[field] = default_value
            
            # Use existing values from the record for foreign keys, don't override to None
            # Only set defaults if the field is completely missing
            fk_defaults = {
                "job_id": jobneed_record.get("parent_id", 1),  # Use parent_id as job_id if available
                "cuser_id": jobneed_record.get("people_id") or jobneed_record.get("performedby_id", 1),
                "muser_id": jobneed_record.get("people_id") or jobneed_record.get("performedby_id", 1),
            }
            
            for field, default_value in fk_defaults.items():
                if field not in jobneed_record or not jobneed_record[field]:
                    jobneed_record[field] = default_value
            
            # Set defaults for remaining required fields
            additional_fk_defaults = {
                "ticketcategory_id": jobneed_record.get("remarkstype_id", 1),  # Use remarkstype_id as fallback
                "pgroup_id": 1,  # Default pgroup
            }
            
            for field, default_value in additional_fk_defaults.items():
                if field not in jobneed_record or not jobneed_record[field]:
                    jobneed_record[field] = default_value
        
        # Include the 'details' field if present - it will be processed separately
        if "details" in record:
            jobneed_record["details"] = record["details"]
        
        return jobneed_record
    
    # Handle JobneedDetails model field mapping
    if "question_id" in record or "answerType" in record or "isAvpt" in record:
        # This is a JobneedDetails record from mobile app - map field names
        detail_record = {}
        
        # Field name mappings from mobile app to Django model
        detail_field_mappings = {
            "answerType": "answertype",
            "isAvpt": "isavpt",
            "avptType": "avpttype",
            "isMandatory": "ismandatory",
            "alertOn": "alerton",
            "attachmentCount": "attachmentcount",
            "qsetId": "qset_id"
        }
        
        # Apply field name mappings
        for mobile_field, django_field in detail_field_mappings.items():
            if mobile_field in record:
                detail_record[django_field] = record[mobile_field]
        
        # Copy fields that don't need mapping
        detail_direct_fields = [
            "uuid", "seqno", "question_id", "answer", "options", "min", "max",
            "jobneed_id", "alerts", "cdtz", "mdtz", "cuser_id", "muser_id", "ctzoffset"
        ]
        
        for field in detail_direct_fields:
            if field in record:
                detail_record[field] = record[field]
        
        # Convert string boolean values to actual booleans
        if "isavpt" in detail_record and isinstance(detail_record["isavpt"], str):
            detail_record["isavpt"] = detail_record["isavpt"].lower() == "true"
        if "ismandatory" in detail_record and isinstance(detail_record["ismandatory"], str):
            detail_record["ismandatory"] = detail_record["ismandatory"] != "0"
        
        # Handle datetime fields
        for dt_field in ["cdtz", "mdtz"]:
            if dt_field in detail_record:
                ctzoffset = detail_record.get("ctzoffset", 0)
                detail_record[dt_field] = clean_datetimes(detail_record[dt_field], ctzoffset)
        
        # Skip fields that don't belong in the model
        # 'people_id', 'tablename' are not fields in JobneedDetails model
        
        return detail_record
    
    # Original clean_record logic for other models
    for k, v in record.items():
        if k in ["jobdesc", "remarks"]:
            record[k] = clean_text(v)
        elif k in ["gpslocation", "startlocation", "endlocation"]:
            record[k] = clean_point_field(v)
        elif k in [
            "cdtz",
            "mdtz",
            "starttime",
            "endtime",
            "punchintime",
            "punchouttime",
            "plandatetime",
            "expirydatetime",
        ]:
            # Use ctzoffset if available, otherwise default to 0
            ctzoffset = record.get("ctzoffset", 0)
            record[k] = clean_datetimes(v, ctzoffset)
        elif k in ["geofencecode"]:
            record[k] = clean_code(v)
        elif k in ["approvers", "categories", "transportmodes", "approverfor", "sites"]:
            record[k] = clean_array_string(v, service=True)
        elif k in ["answer"]:
            record[k] = v.replace('["', "").replace('"]', "")
    return record


def clean_string(input_string, code=False):
    if not input_string:
        return
    cleaned_string = " ".join(input_string.split())
    if code:
        cleaned_string = cleaned_string.replace(" ", "_").upper()
    return cleaned_string


def validate_email(email):
    if email:
        email = email.strip()  # Remove any leading or trailing whitespace
        # Regular expression for validating an Email
        regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        # Using re.fullmatch to validate an Email
        return bool(re.fullmatch(regex, email))
    return False


def clean_array_string(string, service=False):
    if string:
        string = string.replace(" ", "")
        return string.split(",")
    return []


def validate_cron(cron):
    try:
        croniter(cron)
        if cron.startswith("*"):
            raise ValidationError(f"Warning: Scheduling every minute is not allowed!")
        return True
    except ValueError:
        return False
