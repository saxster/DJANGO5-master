"""
This file contains functions related to executing
reports in background
"""
from apps.reports.utils import ReportEssentials
from apps.reports.models import ScheduleReport
from django.conf import settings
from croniter import croniter
from datetime import datetime, timedelta, timezone as dt_timezone
from django.utils import timezone
from django.core.mail import EmailMessage
from django.db import DatabaseError, IntegrityError
from django.db.models import Q
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from apps.core.exceptions import IntegrationException
from apps.tenants.constants import DEFAULT_DB_ALIAS
from apps.tenants.models import Tenant
from apps.tenants.utils import tenant_context, slug_to_db_alias
from logging import getLogger
from pprint import pformat
import json
import traceback as tb
import os
from io import BytesIO

# Celery task imports
from celery import shared_task
from apps.core.tasks.base import IdempotentTask


# make it false when u deploy
MOCK = False
now = timezone.now() if not MOCK else datetime(2023, 8, 19, 12, 2, 0)

log = getLogger("reports")
DATETIME_FORMAT = "%d-%b-%Y %H-%M-%S"
DATE_FORMAT = "%d-%b-%Y"
TIME_FORMAT = "%H-%M-%S"


def set_state(state_map, reset=False, set=""):
    if reset:
        for k in state_map:
            state_map[k] = 0
    if set:
        state_map[set] += 1
    return state_map


# def get_scheduled_reports_fromdb():
#     query =f"""
#         SELECT *
#         FROM schedule_report
#         WHERE enable = TRUE AND
#         (
#             fromdatetime is NULL and uptodatetime is NULL
#             OR
#             (
#                 CASE crontype
#                     WHEN 'daily' THEN lastgeneratedon <= {now_insql} - INTERVAL '1 day'
#                     WHEN 'weekly' THEN lastgeneratedon <= {now_insql} - INTERVAL '1 week'
#                     WHEN 'monthly' THEN lastgeneratedon <= {now_insql} - INTERVAL '1 month'
#                     WHEN 'workingdays' THEN lastgeneratedon <= {now_insql} - INTERVAL '7 days'
#                     WHEN 'workingdays' THEN lastgeneratedon <= {now_insql} - INTERVAL '8 days'
#                 END
#             )
#             AND (fromdatetime <= {now_insql} OR fromdatetime is NULL)
#             AND (uptodatetime <= {now_insql} OR uptodatetime is NULL)
#         )
#     """
#     return runrawsql(query)


REPORTS_PER_TENANT_PER_RUN = getattr(settings, "SCHEDULED_REPORTS_PER_RUN", 25)
REPORT_VALUE_FIELDS = [
    "id",
    "report_type",
    "report_params",
    "client_id",
    "report_sendtime",
    "crontype",
    "cron",
    "workingdays",
    "ctzoffset",
    "fromdatetime",
    "uptodatetime",
    "lastgeneratedon",
]


def _due_frequency_filters(reference_time):
    """Build Q objects representing each frequency window."""

    def _window(cron_type: str, delta: timedelta) -> Q:
        return Q(crontype=cron_type) & (
            Q(lastgeneratedon__lte=reference_time - delta)
            | Q(lastgeneratedon__isnull=True)
        )

    return (
        _window("daily", timedelta(days=1))
        | _window("weekly", timedelta(weeks=1))
        | _window("monthly", timedelta(days=31))
        | _window("workingdays", timedelta(days=7))
    )


def get_scheduled_reports_fromdb(limit: int | None = None, reference_time: datetime | None = None):
    """
    ORM replacement for the legacy raw query that scopes to the current tenant database.

    Args:
        limit: Optional maximum number of reports to return.
        reference_time: Override for current time (useful in tests).

    Returns:
        List of dictionaries describing due schedule_report rows.
    """
    reference_time = reference_time or timezone.now()

    open_window = Q(fromdatetime__isnull=True, uptodatetime__isnull=True)
    active_window = (
        (Q(fromdatetime__lte=reference_time) | Q(fromdatetime__isnull=True))
        & (Q(uptodatetime__gte=reference_time) | Q(uptodatetime__isnull=True))
    )

    qs = (
        ScheduleReport.objects.filter(enable=True)
        .filter(open_window | (_due_frequency_filters(reference_time) & active_window))
        .order_by("lastgeneratedon", "id")
    )

    if limit:
        qs = qs[:limit]

    return list(qs.values(*REPORT_VALUE_FIELDS))


def _get_db_alias_for_tenant_slug(slug: str | None) -> str:
    """Map tenant slug to database alias, falling back to default if missing."""
    if not slug:
        return DEFAULT_DB_ALIAS

    candidate = slug_to_db_alias(slug)
    if candidate in settings.DATABASES:
        return candidate

    log.warning(
        "Database alias '%s' for tenant slug '%s' not configured. Falling back to default.",
        candidate,
        slug,
    )
    return DEFAULT_DB_ALIAS


def _process_reports_for_tenant(tenant_label: str, db_alias: str, per_tenant_limit: int,
                                story: dict, state_map: dict) -> dict:
    """
    Fetch and generate scheduled reports for a single tenant/database alias.
    """
    tenant_summary = story.setdefault('tenants', {})

    try:
        with tenant_context(db_alias):
            scheduled_reports = get_scheduled_reports_fromdb(limit=per_tenant_limit)
            tenant_summary[tenant_label] = {
                'db_alias': db_alias,
                'queued': len(scheduled_reports),
            }

            if not scheduled_reports:
                log.debug("No scheduled reports due for tenant %s (db=%s)", tenant_label, db_alias)
                return state_map

            for record in scheduled_reports:
                try:
                    state_map = generate_scheduled_report(record, state_map)
                except (DatabaseError, IntegrityError, ValidationError, ValueError, TypeError) as e:
                    log.error(
                        "Error generating report %s for tenant %s: %s",
                        record.get('id', 'unknown'),
                        tenant_label,
                        e,
                        exc_info=True
                    )
                    story['errors'].append({
                        'tenant': tenant_label,
                        'report_id': record.get('id'),
                        'error': str(e),
                        'traceback': tb.format_exc()
                    })
                    state_map['not_generated'] += 1

    except DatabaseError as exc:
        log.error(
            "Database error processing scheduled reports for tenant %s (db=%s): %s",
            tenant_label,
            db_alias,
            exc,
            exc_info=True
        )
        story['errors'].append({
            'tenant': tenant_label,
            'error': f"Database error: {str(exc)}",
            'traceback': tb.format_exc()
        })
    except (ValidationError, ValueError, TypeError) as exc:
        log.error(
            "Validation error processing scheduled reports for tenant %s (db=%s): %s",
            tenant_label,
            db_alias,
            exc,
            exc_info=True
        )
        story['errors'].append({
            'tenant': tenant_label,
            'error': f"Validation error: {str(exc)}",
            'traceback': tb.format_exc()
        })
    except (KeyError, AttributeError) as exc:
        log.error(
            "Data processing error in scheduled reports for tenant %s (db=%s): %s",
            tenant_label,
            db_alias,
            exc,
            exc_info=True
        )
        story['errors'].append({
            'tenant': tenant_label,
            'error': f"Data error: {str(exc)}",
            'traceback': tb.format_exc()
        })

    return state_map


def remove_star(li):
    return [item.replace("*", "") for item in li]


def update_record(data, fromdatetime, uptodatetime, lastgeneratedon):
    ScheduleReport.objects.filter(pk=data["id"]).update(
        fromdatetime=fromdatetime,
        uptodatetime=uptodatetime,
        lastgeneratedon=lastgeneratedon,
    )


def get_report_dates_with_working_days(today_date, working_days, cron):
    # Validate working_days input
    if working_days not in [5, 6]:
        raise ValueError("Working days must be either 5 (Mon-Fri) or 6 (Mon-Sat).")

    hr, min = cron.split(" ")[:2]

    # Calculate the most recent Monday (or today if it's Monday)
    monday = today_date - timedelta(days=today_date.weekday())

    # Calculate the end of the work week based on working days
    end_of_week_day = (
        4 if working_days == 5 else 5
    )  # Friday for 5-day week, Saturday for 6-day week
    end_of_week = monday + timedelta(days=end_of_week_day)

    # Format dates with time
    fromdatetime = monday.replace(microsecond=0)
    uptodatetime = end_of_week.replace(microsecond=0)
    return fromdatetime, uptodatetime


def calculate_from_and_upto(data):
    log.info(f"Calculating from and upto dates for data: {data}")

    days_crontype_map = {
        "weekly": 7,
        "monthly": 31,
        "daily": 1,
        "workingdays": data["workingdays"],
    }
    tz = dt_timezone(timedelta(minutes=data["ctzoffset"]))
    log.info("The report is generating for the first time")
    if data["crontype"] != "workingdays":
        basedatetime = now - timedelta(days=days_crontype_map[data["crontype"]] + 1)
        log.info(f'{basedatetime = } {data["cron"] = }')
        cron = croniter(data["cron"], basedatetime)
        fromdatetime = cron.get_prev(datetime)
        log.info(f"{fromdatetime = } {type(fromdatetime)}")
        fromdatetime = fromdatetime.replace(tzinfo=tz, microsecond=0)
        uptodatetime = cron.get_next(datetime)
        uptodatetime = uptodatetime.replace(tzinfo=tz, microsecond=0)
        lastgeneratedon = now
        return fromdatetime, uptodatetime, lastgeneratedon
    else:
        fromdatetime, uptodatetime = get_report_dates_with_working_days(
            now, int(data["workingdays"]), data["cron"]
        )
        log.info(f"{fromdatetime = } {uptodatetime = } {now = }")
        if now > uptodatetime:
            return fromdatetime, uptodatetime, now
        log.info(
            f"The uptodatetime: {uptodatetime} is greater than current datetime {now}"
        )
        # skipped by returning none, because dates are not yet in range,
        return None, None, None


def build_form_data(data, report_params, behaviour):
    date_range = None
    fields = remove_star(behaviour["fields"])
    fromdatetime, uptodatetime, lastgeneratedon = calculate_from_and_upto(data)
    if fromdatetime and uptodatetime and lastgeneratedon:
        formdata = {
            "preview": False,
            "format": report_params["format"],
            "ctzoffset": data["ctzoffset"],
        }
        if "fromdate" in fields:
            formdata.update(
                {"fromdate": fromdatetime.date(), "uptodate": uptodatetime.date()}
            )
            date_range = f"{formdata['fromdate'].strftime(DATE_FORMAT)}--{formdata['uptodate'].strftime(DATE_FORMAT)}"
        if "fromdatetime" in fields:
            formdata.update(
                {"fromdatetime": fromdatetime, "uptodatetime": uptodatetime.date()}
            )
            date_range = f"{formdata['fromdatetime'].strftime(DATETIME_FORMAT)}--{formdata['uptodatetime'].strftime(DATETIME_FORMAT)}"
        log.debug(f"formdata = {pformat(formdata)}, fields = {fields}")
        required_params = {
            key: report_params[key] for key in fields if key not in formdata
        }
        formdata.update(required_params)
        updatevalues = {
            "fromdatetime": fromdatetime,
            "uptodatetime": uptodatetime,
            "lastgeneratedon": lastgeneratedon,
        }
        return formdata, date_range, updatevalues
    return None, None, None


def generate_filename(report_type, date_range, sendtime):
    # eg: filename = TaskSummary__2023-DEC-1--2023-DEC-30__23-34-23.pdf
    return f"{report_type}__{date_range}__{sendtime.strftime(TIME_FORMAT)}"


def execute_report(RE, report_type, client_id, formdata):
    report_export = RE(
        filename=report_type, client_id=client_id, returnfile=True, formdata=formdata
    )
    return report_export.execute()


def save_report_to_tmp_folder(filename, ext, report_output, dir=None):
    if report_output:
        directory = dir or settings.TEMP_REPORTS_GENERATED
        filepath = os.path.join(directory, f"{filename}.{ext}")

        if not os.path.exists(directory):
            os.makedirs(directory)

        mode = "wb" if ext in ["pdf", "xlsx"] else "w"
        try:
            with open(filepath, mode) as f:
                if isinstance(report_output, BytesIO):
                    report_output = report_output.getvalue()
                    if ext in ["csv", "json", "html"] and report_output:
                        report_output = report_output.decode("utf-8")
                if report_output:  # Check if report_output is not empty
                    f.write(report_output)
                else:
                    log.error(f"No data to write for {filename}.{ext}")
                    return None  # Return None to indicate no file was saved
        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError) as e:
            log.error(f"Error while saving file {filename}.{ext}: {e}")
            return None  # Return None on error
    else:
        log.error("No report output provided")
        return None

    return filepath


def update_report_record(record, updatevalues, filename):
    isupdated = ScheduleReport.objects.filter(id=record["id"]).update(
        filename=filename, **updatevalues
    )
    return isupdated


def generate_scheduled_report(record, state_map):
    """
    Generate a scheduled report based on the provided data.

    Args:
        data (dict): A dictionary containing information about the scheduled report.

    Returns:
        None: This method generates and saves the report but does not return any value.

    Raises:
        Any relevant exceptions: Document any exceptions that may be raised during report generation.
    """
    resp = dict()
    if record:
        report_params_raw = record.get("report_params")
        if isinstance(report_params_raw, str):
            try:
                report_params = json.loads(report_params_raw)
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                log.error(
                    "Invalid report_params payload for schedule_report %s: %s",
                    record.get("id"),
                    exc,
                )
                set_state(state_map, set="not_generated")
                return state_map
        elif isinstance(report_params_raw, dict):
            report_params = report_params_raw
        else:
            report_params = {}

        re = ReportEssentials(record["report_type"])
        behaviour = re.behaviour_json
        RE = re.get_report_export_object()
        log.info(f"Got RE of type {type(RE)}")
        formdata, date_range, updatevalues = build_form_data(
            record, report_params, behaviour
        )
        if formdata and date_range and updatevalues:
            log.info(f"formdata: {pformat(formdata)} {date_range = }")
            report_output = execute_report(
                RE, record["report_type"], record["client_id"], formdata
            )
            sendtime = record["report_sendtime"]
            report_type = record["report_type"]
            filename = generate_filename(report_type, date_range, sendtime)
            log.info(f"filename generated {filename = }")
            ext = report_params["format"]
            log.info(f"file extension {ext = }")
            filepath = save_report_to_tmp_folder(filename, ext, report_output)
            if report_output and filepath:
                if isupdated := update_report_record(record, updatevalues, filename):
                    log.info(f"Reoprt Record updated successfully")
                log.info(f"file saved at location {filepath =}")
                resp[str(record["id"])] = filepath
                set_state(state_map, set="generated")
            else:
                set_state(state_map, set="not_generated")
        else:
            set_state(state_map, set="skipped")
            resp["msg"] = "Report cannot be generated due to out of range"
    else:
        resp["msg"] = "No reports are currently due for being generated"
    return state_map


def walk_directory(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            yield os.path.join(root, file)


def get_report_record(filename_without_extension):
    return ScheduleReport.objects.filter(filename=filename_without_extension).first()


def send_email(record, file):
    log.info(f"Sending email to {record.to_addr} with file {os.path.basename(file)}")
    email = EmailMessage(
        "Test Subject", "Test Body", settings.EMAIL_HOST_USER, [record.to_addr]
    )
    email.attach_file(file)
    email.send()
    log.info(f"Email sent to {record.to_addr} with file {os.path.basename(file)}")


def handle_error(e):
    return {
        "time": timezone.now(),
        "error": str(e),
        "traceback": tb.format_exc(),
    }


from zoneinfo import ZoneInfo


def check_time_of_report(filename):
    log.info("Checking time of report for file: %s", filename)

    filename_with_extension = os.path.basename(filename)
    filename_without_extension, _ = os.path.splitext(filename_with_extension)
    parts = filename_without_extension.split("__")

    try:
        sendtime_str = parts[-1]  # e.g., '17:35'
        ist_zone = ZoneInfo("Asia/Kolkata")

        # Parse IST time and convert to UTC
        ist_time = datetime.strptime(sendtime_str, TIME_FORMAT).time()
        today = timezone.now().date()

        ist_datetime = datetime.combine(today, ist_time)
        ist_aware = ist_datetime.replace(tzinfo=ist_zone)
        utc_send_time = ist_aware.astimezone(dt_timezone.utc)

        # Current UTC time
        now_utc = timezone.now()
        time_diff = abs(now_utc - utc_send_time)

        log.info(
            f"Now UTC: {now_utc}, Scheduled UTC: {utc_send_time}, Diff: {time_diff}"
        )

        if time_diff <= timedelta(minutes=30):
            return True, filename_without_extension

    except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        log.warning(f"Time parse error for file {filename}: {e}")

    return False, None


# def check_time_of_report(filename):
#    log.info('Checking time of report for file: %s', filename)

#    filename_with_extension = os.path.basename(filename)
#    filename_without_extension, _ = os.path.splitext(filename_with_extension)
#    parts = filename_without_extension.split("__")
#    sendtime_str = parts[-1]
#    dt = datetime.strptime(sendtime_str, TIME_FORMAT)
#    T1 = dt.time()
#    current_time = timezone.localtime(timezone.now()).time()


#    # Convert datetime.time to datetime.datetime
#    today = datetime.today().date()
#    T1_datetime = datetime.combine(today, T1)
#    current_time_datetime = datetime.combine(today, current_time)

#    # Subtract datetime.datetime objects to get a timedelta
#    time_difference = current_time_datetime - T1_datetime
#    log.info('Time difference between current time and report time: %s', time_difference)

#    if abs(time_difference) <= timedelta(minutes=30):
#        log.info('Time difference is less than or equal to 30 minutes. Returning True for file: %s', filename_without_extension)
#        return True, filename_without_extension

#    log.info('Time difference is more than 30 minutes. Returning False for file: %s', filename)
#    return False, None


def remove_reportfile(file, story=None):
    try:
        os.remove(file)
        log.info(f"Successfully deleted file: {os.path.basename(file)}")
    except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        log.critical(f"Error deleting file {os.path.basename(file)}: {e}")
        if story:
            story["errors"].append(str(e))
    return story


# ============================================================================
# BACKWARD COMPATIBILITY STUBS
# ============================================================================
# These functions were referenced in __init__.py but not found in this file.
# Creating stubs to prevent import errors during refactoring.
# ============================================================================

def create_report_history(*args, **kwargs):
    """STUB: Function may have been refactored - implement or remove references."""
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("create_report_history called but not implemented - may need refactoring")
    pass


def create_save_report_async(*args, **kwargs):
    """STUB: Function may have been refactored - implement or remove references."""
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("create_save_report_async called but not implemented - may need refactoring")
    pass


@shared_task(
    base=IdempotentTask,
    bind=True,
    name='create_scheduled_reports',
    queue='reports',
    priority=6,
    max_retries=2,
    default_retry_delay=300
)
def create_scheduled_reports(self):
    """
    Generate scheduled reports based on database configuration.

    Runs every 15 minutes (scheduled in celery.py) and:
    1. Queries database for reports due for generation
    2. For each report:
       - Calculates date range based on cron configuration
       - Executes report generation
       - Saves output to temp directory
       - Updates database record
    3. Returns summary of reports generated

    Returns:
        dict: Summary with counts of generated, skipped, and failed reports

    Idempotency:
        - Scope: global (one execution per 15-min window)
        - TTL: 900 seconds (15 minutes)
        - Prevents duplicate report generation
    """
    # Configure idempotency
    self.idempotency_ttl = 900  # 15 minutes
    self.idempotency_scope = 'global'

    story = {
        'start_time': timezone.now(),
        'generated': 0,
        'skipped': 0,
        'not_generated': 0,
        'errors': [],
        'end_time': None,
        'tenants': {},
    }

    state_map = {'generated': 0, 'skipped': 0, 'not_generated': 0}
    per_tenant_limit = REPORTS_PER_TENANT_PER_RUN

    try:
        tenants = list(
            Tenant.objects.filter(is_active=True).values('id', 'tenantname', 'subdomain_prefix')
        )

        if not tenants:
            log.warning(
                "No active tenants found; falling back to default database for scheduled reports"
            )
            state_map = _process_reports_for_tenant(
                tenant_label='default',
                db_alias=DEFAULT_DB_ALIAS,
                per_tenant_limit=per_tenant_limit,
                story=story,
                state_map=state_map,
            )
        else:
            log.info("Processing scheduled reports for %s tenants", len(tenants))
            for tenant in tenants:
                tenant_label = tenant.get('subdomain_prefix') or f"tenant-{tenant['id']}"
                db_alias = _get_db_alias_for_tenant_slug(tenant.get('subdomain_prefix'))

                state_map = _process_reports_for_tenant(
                    tenant_label=tenant_label,
                    db_alias=db_alias,
                    per_tenant_limit=per_tenant_limit,
                    story=story,
                    state_map=state_map,
                )

        # Update story with final counts
        story.update(state_map)

    except (DatabaseError, IntegrityError, ValidationError, ValueError, TypeError) as e:
        error_info = handle_error(e)
        story['errors'].append(error_info)
        log.critical("Critical error in create_scheduled_reports", exc_info=True)

    story['end_time'] = timezone.now()
    duration = (story['end_time'] - story['start_time']).total_seconds()

    log.info(
        f"create_scheduled_reports completed: "
        f"{story['generated']} generated, {story['skipped']} skipped, "
        f"{story['not_generated']} failed in {duration:.2f}s"
    )

    return story


def send_report_on_email(*args, **kwargs):
    """STUB: Function may have been refactored - implement or remove references."""
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("send_report_on_email called but not implemented - may need refactoring")
    pass


@shared_task(
    base=IdempotentTask,
    bind=True,
    name='send_generated_report_on_mail',
    queue='email',
    priority=7,
    max_retries=3,
    default_retry_delay=120
)
def send_generated_report_on_mail(self):
    """
    Send generated reports via email at scheduled times.

    This task runs every 27 minutes (scheduled in celery.py) and:
    1. Scans TEMP_REPORTS_GENERATED directory for report files
    2. Checks if each report is ready to send (based on scheduled time)
    3. Retrieves report record from database with recipient email
    4. Sends email with report attachment
    5. Deletes file after successful send

    Returns:
        dict: Execution summary with files processed, emails sent, and errors

    Idempotency:
        - Scope: global (one execution per 27-min window)
        - TTL: 1620 seconds (27 minutes)
        - Prevents duplicate email sends
    """
    # Configure idempotency
    self.idempotency_ttl = 1620  # 27 minutes
    self.idempotency_scope = 'global'
    story = {
        "start_time": timezone.now(),
        "files_processed": 0,
        "emails_sent": 0,
        "errors": [],
        "end_time": None,
    }

    try:
        # Walk through temp reports directory
        for file in walk_directory(settings.TEMP_REPORTS_GENERATED):
            story["files_processed"] += 1

            # Check if report should be sent now
            sendmail, filename_without_extension = check_time_of_report(file)

            if sendmail:
                # Get report record with email addresses
                record = get_report_record(filename_without_extension)

                if record:
                    # Send email with report attachment
                    send_email(record, file)
                    story["emails_sent"] += 1

                    # Delete file after successful send
                    story = remove_reportfile(file, story)
                else:
                    log.info(f"No record found for file {os.path.basename(file)}")
            else:
                log.debug(f"Report {os.path.basename(file)} not ready to send yet")

    except (DatabaseError, FileNotFoundError, IOError, IntegrationException, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        error_info = handle_error(e)
        story["errors"].append(error_info)
        log.critical("Error in send_generated_report_on_mail", exc_info=True)

    story["end_time"] = timezone.now()
    log.info(f"send_generated_report_on_mail completed: {story['emails_sent']} emails sent, {story['files_processed']} files processed")

    return story


def send_generated_report_onfly_email(*args, **kwargs):
    """STUB: Function may have been refactored - implement or remove references."""
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("send_generated_report_onfly_email called but not implemented - may need refactoring")
    pass


def generate_pdf_async(*args, **kwargs):
    """STUB: Function may have been refactored - implement or remove references."""
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("generate_pdf_async called but not implemented - may need refactoring")
    pass


def cleanup_reports_which_are_12hrs_old(*args, **kwargs):
    """STUB: Function may have been refactored - implement or remove references."""
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("cleanup_reports_which_are_12hrs_old called but not implemented - may need refactoring")
    pass
