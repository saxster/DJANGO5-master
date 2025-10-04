import logging

logger = logging.getLogger("django")
from django.core.exceptions import ValidationError


__all__ = [
    'clean_gpslocation',
    'isValidEMEI',
    'verify_mobno',
    'verify_emailaddr',
    'verify_loginid',
    'verify_peoplename',
    'validate_date_format',
]


def clean_gpslocation(val):
    import re

    from django.contrib.gis.geos import GEOSGeometry
    from django.forms import ValidationError

    if gps := val:
        if gps == "NONE":
            return None
        regex = (
            r"^([-+]?)([\d]{1,2})(((\.)(\d+)(,)))(\s*)(([-+]?)([\d]{1,3})((\.)(\d+))?)$"
        )
        gps = gps.replace("(", "").replace(")", "")
        if not re.match(regex, gps):
            raise ValidationError("Invalid GPS location")
        gps.replace(" ", "")
        lat, lng = gps.split(",")
        gps = GEOSGeometry(f"SRID=4326;POINT({lng} {lat})")
    return gps


# Returns True if n is valid EMEI
def isValidEMEI(n):
    # Converting the number into
    # String for finding length
    s = str(n)
    l = len(s)

    if l != 15:
        return False
    return True


def verify_mobno(mobno):
    import phonenumbers as pn
    from phonenumbers.phonenumberutil import NumberParseException

    try:
        no = pn.parse(f"+{mobno}") if "+" not in mobno else pn.parse(mobno)
        if not pn.is_valid_number(no):
            return False
    except NumberParseException as e:
        return False
    else:
        return True


def verify_emailaddr(email):
    from email_validator import EmailNotValidError, validate_email

    try:
        validate_email(email)
        return True
    except EmailNotValidError as e:
        logger.warning("email is not valid")
        return False


def verify_loginid(loginid):
    import re

    return bool(re.match(r"^[a-zA-Z0-9@#_\-\_]+$", loginid))


def verify_peoplename(peoplename):
    import re

    return bool(re.match(r"^[a-zA-Z0-9\-_@#\(\|\) ]*$", peoplename))


def validate_date_format(date_value, field_name):
    from datetime import datetime

    if date_value:
        # Convert Timestamp to string, if necessary
        if isinstance(date_value, datetime):
            date_value = date_value.strftime("%Y-%m-%d")
        try:
            datetime.strptime(date_value, "%Y-%m-%d")  # Validate date format
        except ValueError:
            raise ValidationError(
                f"{field_name} must be a valid date in the format YYYY-MM-DD"
            )
