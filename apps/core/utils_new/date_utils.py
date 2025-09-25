from datetime import datetime, timedelta, timezone
import logging
import re


logger = logging.getLogger("django")


def get_current_year():
    return datetime.now().year


def to_utc(date, format=None):
    logger.info("to_utc() start [+]")
    import pytz

    if isinstance(date, list) and date:
        logger.info(f"found total {len(date)} datetimes")
        logger.info(f"before conversion datetimes {date}")
        dtlist = []
        for dt in date:
            dt = dt.astimezone(pytz.utc).replace(microsecond=0, tzinfo=pytz.utc)
            dtlist.append(dt)
        logger.info(f"after conversion datetime list returned {dtlist=}")
        return dtlist
    dt = date.astimezone(pytz.utc).replace(microsecond=0, tzinfo=pytz.utc)
    if format:
        dt.strftime(format)
    logger.info("to_utc() end [-]")
    return dt


def getawaredatetime(dt, offset):
    from datetime import datetime, timedelta, timezone

    tz = timezone(timedelta(minutes=int(offset)))
    if isinstance(dt, datetime):
        val = dt
    else:
        val = dt.replace("+00:00", "")
        val = datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
    return val.replace(tzinfo=tz, microsecond=0)


def format_timedelta(td):
    if not td:
        return None
    total_seconds = int(td.total_seconds())
    days, remainder = divmod(total_seconds, 60 * 60 * 24)
    hours, remainder = divmod(remainder, 60 * 60)
    minutes, seconds = divmod(remainder, 60)

    result = ""
    if days > 0:
        result += f"{days} day{'s' if days != 1 else ''}, "
    if hours > 0:
        result += f"{hours} hour{'s' if hours != 1 else ''}, "
    if minutes > 0:
        result += f"{minutes} minute{'s' if minutes != 1 else ''}, "
    if seconds > 0 or len(result) == 0:
        result += f"{seconds} second{'s' if seconds != 1 else ''}"
    return result.rstrip(", ")


def convert_seconds_to_human_readable(seconds):
    # Calculate the time units
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)

    # Create a human readable string
    result = []
    if days:
        result.append(f"{int(days)} day{'s' if days > 1 else ''}")
    if hours:
        result.append(f"{int(hours)} hour{'s' if hours > 1 else ''}")
    if minutes:
        result.append(f"{int(minutes)} minute{'s' if minutes > 1 else ''}")
    if sec:
        result.append(
            f"{sec:.2f} second{'s' if sec > 1 else ''}"
        )  # limit decimal places to 2

    return ", ".join(result)


def get_timezone(offset):  # sourcery skip: aware-datetime-for-utc
    import pytz
    from datetime import datetime, timedelta

    # Convert the offset string to a timedelta object
    offset = f"+{offset}" if int(offset) > 0 else str(offset)
    sign = offset[0]  # The sign of the offset (+ or -)
    mins = int(offset[1:])
    delta = timedelta(minutes=mins)  # The timedelta object
    if sign == "-":  # If the sign is negative, invert the delta
        delta = -delta

    # Loop through all the timezones and find the ones that match the offset
    matching_zones = []  # A list to store the matching zones
    for zone in pytz.all_timezones:  # For each timezone
        tz = pytz.timezone(zone)  # Get the timezone object
        utc_offset = tz.utcoffset(datetime.utcnow())  # Get the current UTC offset
        if utc_offset == delta:  # If the offset matches the input
            matching_zones.append(zone)  # Add the zone to the list

    # Return the list of matching zones or None if no match found
    return matching_zones[0] if matching_zones else None


def find_closest_shift(log_starttime, shifts):
    closest_shift_id = None
    closest_time_diff = timedelta.max  # Start with the maximum possible timedelta
    logger.info(f"The closest_time_diff{closest_time_diff}")

    for shift in shifts:
        # Extract the start time from the shift's string representation using regex
        match = re.search(r"\((\d{2}:\d{2}:\d{2}) -", str(shift))
        if not match:
            raise ValueError(f"Could not parse start time from shift: {shift}")

        shift_start_time = datetime.strptime(match.group(1), "%H:%M:%S").time()

        # Combine the shift's start time with the logger's date, and make it offset-aware
        shift_datetime = datetime.combine(
            log_starttime.date(), shift_start_time, tzinfo=timezone.utc
        )

        # Calculate the time difference
        time_diff = abs(shift_datetime - log_starttime)
        logger.info(f"the time difference before if condition {time_diff}")

        # Update the closest shift if this one is closer
        if time_diff < closest_time_diff:
            closest_time_diff = time_diff
            logger.info(f"closseset time difference is {closest_time_diff}")
            closest_shift_id = shift.id

    return closest_shift_id
