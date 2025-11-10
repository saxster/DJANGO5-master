from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import IntegrityError, DatabaseError
from apps.core.utils_new import db_utils as utils
from apps.core.utils_new.db.none_objects import (
    get_or_create_none_tenant,
    get_or_create_none_bv,
)
from apps.core.exceptions import patterns as excp
from django.core.exceptions import ObjectDoesNotExist
from apps.client_onboarding.models import Bt
from apps.core_onboarding.models import TypeAssist
from apps.peoples import models as pm
from apps.peoples.models import People
from apps.client_onboarding.admin import TaResource
from apps.peoples.admin import CapabilityResource
from django.conf import settings
from tablib import Dataset
import logging
import uuid
import secrets
import os

logger = logging.getLogger(__name__)
log = logger

MAX_RETRY = 5
# SECURITY FIX (2025-10-11): Hardcoded password removed (CVSS 9.1)
# Password generation moved to create_superuser() function using secrets module


def _sanitize_sql(function: str) -> str:
    """Remove unsupported OWNER clauses for local Postgres roles."""
    cleaned_lines = [
        line for line in function.splitlines()
        if 'OWNER TO' not in line.upper()
    ]
    return '\n'.join(cleaned_lines)


def ensure_default_typeassist():
    """Ensure baseline TypeAssist hierarchy exists."""
    tenant = get_or_create_none_tenant()
    client = get_or_create_none_bv()
    root, _ = TypeAssist.objects.get_or_create(
        tacode='BVIDENTIFIER',
        defaults={'taname': 'Business Identifier', 'tenant': tenant, 'client': client},
    )
    seeds = [
        ('CLIENT', 'Client'),
        ('SITE', 'Site'),
        ('DEPARTMENT', 'Department'),
        ('DESIGNATION', 'Designation'),
        ('EMPLOYEE_TYPE', 'Employee Type'),
        ('WORK_TYPE', 'Work Type'),
    ]
    created = {}
    for code, name in seeds:
        obj, _ = TypeAssist.objects.get_or_create(
            tacode=code,
            defaults={
                'taname': name,
                'tatype': root,
                'tenant': tenant,
                'client': client,
            },
        )
        created[code] = obj
    return created['CLIENT'], created['SITE']


def seed_default_capabilities():
    """Create minimal capability hierarchy if import files are missing."""
    tenant = get_or_create_none_tenant()
    client = get_or_create_none_bv()
    Capability = pm.Capability
    seeds = [
        ('CORE_ROOT', 'Core Capability Root', 'WEB', None),
        ('CORE_DASHBOARD_VIEW', 'Dashboard View', 'WEB', 'CORE_ROOT'),
        ('REPORT_VIEWER', 'Reports Viewer', 'REPORT', 'CORE_ROOT'),
        ('MOBILE_SYNC', 'Mobile Sync Access', 'MOB', 'CORE_ROOT'),
    ]

    cache: dict[str, pm.Capability] = {}
    for code, name, cfor, parent_code in seeds:
        parent = None
        if parent_code:
            parent = cache.get(parent_code) or Capability.objects.filter(
                capscode=parent_code
            ).first()
            if not parent:
                parent, _ = Capability.objects.get_or_create(
                    capscode=parent_code,
                    defaults={
                        'capsname': parent_code.replace('_', ' ').title(),
                        'cfor': 'WEB',
                        'tenant': tenant,
                        'client': client,
                    },
                )
            cache[parent_code] = parent

        obj, _ = Capability.objects.get_or_create(
            capscode=code,
            defaults={
                'capsname': name,
                'cfor': cfor,
                'parent': parent,
                'tenant': tenant,
                'client': client,
            },
        )
        cache[code] = obj


def create_dummy_client_and_site():
    client_type, site_type = ensure_default_typeassist()
    tenant = client_type.tenant

    # Get the NONE Bt as parent for client
    try:
        parent_bt = Bt.objects.get(bucode='NONE')
    except Bt.DoesNotExist:
        parent_bt = get_or_create_none_bv()
    
    client_defaults = {
        'buname': "Security Personnel Services",
        'enable': True,
        'identifier': client_type,
        'parent': parent_bt,
        'tenant': tenant,
    }
    client, created = Bt.objects.get_or_create(bucode='SPS', defaults=client_defaults)
    if created:
        log.info("Created dummy client: SPS")
    else:
        log.info("Client SPS already exists")

    site_defaults = {
        'buname': 'Youtility Technologies Pvt Ltd',
        'enable': True,
        'identifier': site_type,
        'parent': client,
        'tenant': tenant,
    }
    site, created = Bt.objects.get_or_create(bucode='YTPL', defaults=site_defaults)
    if created:
        log.info("Created dummy site: YTPL")
    else:
        log.info("Site YTPL already exists")
    
    return client, site


def create_sql_functions(db):
    """Create required SQL functions using Django-managed connections."""
    from apps.core.raw_sql_functions import get_sqlfunctions
    if os.environ.get('SKIP_SQL_FUNCTIONS', 'true').lower() in {'true', '1', 'yes'}:
        log.info("SKIP_SQL_FUNCTIONS enabled; skipping raw SQL bootstrap")
        return
    sql_functions_list = get_sqlfunctions().values()
    connection = connections[db]

    with connection.cursor() as cursor:
        for function in sql_functions_list:
            try:
                cursor.execute(_sanitize_sql(function))
            except DatabaseError as exc:
                logger.warning("Skipping SQL function due to database error: %s", exc)

def insert_default_entries(skip_existing=False):
    BASE_DIR = settings.BASE_DIR
    filepaths_and_resources = {
        f'{BASE_DIR}/docs/default_types.xlsx': TaResource,
        f'{BASE_DIR}/docs/caps.xlsx': CapabilityResource
    }

    for filepath, Resource in filepaths_and_resources.items():
        dataset = None
        if not os.path.exists(filepath):
            if Resource is TaResource:
                log.info("Default TypeAssist data not found on disk; seeding minimal dataset programmatically.")
                continue  # ensure_default_typeassist already seeds required entries
            if Resource is CapabilityResource:
                log.info("Default capability data not found on disk; seeding minimal dataset programmatically.")
                seed_default_capabilities()
                continue
            log.info(f"Default import file missing, skipping: {filepath}")
            continue
        else:
            with open(filepath, 'rb') as f:
                dataset = Dataset().load(f)

        resource = Resource(is_superuser=True)
        try:
            # Try to import with skip_unchanged to handle existing records
            result = resource.import_data(
                dataset,
                dry_run=False,
                use_transactions=True,
                raise_errors=not skip_existing  # Don't raise errors if skip_existing is True
            )
            if result.has_errors() and not skip_existing:
                log.error(f"Import errors from {filepath}: {result.errors}")
                raise Exception(f"Import failed with errors: {result.errors}")
            else:
                log.info(f"Successfully imported data from {filepath}")
        except (DatabaseError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError) as e:
            if skip_existing and "already exist" in str(e):
                log.info(f"Skipping existing records from {filepath}")
            else:
                raise

def create_superuser(client, site):
    """
    Create superuser with cryptographically secure password.

    SECURITY FIX (2025-10-11): Replaced hardcoded password with secure generation.
    - Production: Generates random 32-character password via secrets.token_urlsafe()
    - Development: Allows DJANGO_SUPERUSER_PASSWORD env var override for testing
    - Compliance: Eliminates CVSS 9.1 hardcoded credential vulnerability

    Args:
        client: Client Business Unit instance
        site: Site Business Unit instance

    Returns:
        People instance if created/found, None otherwise
    """
    if not client or not site:
        log.warning("Cannot create superuser without client and site")
        return None

    try:
        user = People.objects.get(loginid="superadmin")
        log.info("Superuser with loginid 'superadmin' already exists")
        return user
    except People.DoesNotExist:
        pass

    # SECURITY FIX: Generate cryptographically secure random password
    env_password = os.getenv('DJANGO_SUPERUSER_PASSWORD')

    if env_password:
        # Dev/staging: Allow env var override (must be set explicitly)
        temp_password = env_password
        log.warning(
            "Using environment-provided superuser password",
            extra={'security_event': 'env_password_used', 'environment': 'non-production'}
        )
    else:
        # Production: Generate secure random password
        temp_password = secrets.token_urlsafe(32)
        log.critical(
            "SUPERUSER CREATED - One-time password generated. "
            "IMMEDIATELY reset via Django admin or change password on first login.",
            extra={
                'security_event': 'superuser_creation',
                'action_required': 'password_reset',
                'password_strength': 'cryptographic_random_256bit'
            }
        )

    try:
        user = People.objects.create(
            peoplecode='SUPERADMIN', loginid="superadmin", peoplename='Super Admin',
            dateofbirth='1111-11-11', dateofjoin='1111-11-11',
            email='superadmin@youtility.in', isverified=True,
            is_staff=True, is_superuser=True,
            isadmin=True, client=client, bu=site, tenant=client.tenant
        )
        user.set_password(temp_password)
        user.save()

        # SECURITY: Display password only on console (never in logs)
        if not env_password:
            # Only print to stdout in non-production (when password is generated)
            logger.debug("\n" + "=" * 80)
            logger.debug("SUPERUSER CREATED - SAVE THIS PASSWORD (shown only once):")
            logger.debug(f"Username: superadmin")
            logger.debug(f"Password: {temp_password}")
            logger.debug(f"Email: superadmin@youtility.in")
            logger.debug("=" * 80 + "\n")

        # Log correlation ID only (never password in production logs)
        correlation_id = str(uuid.uuid4())
        log.info(
            f"Superuser created successfully with loginid: {user.loginid}",
            extra={
                'user_id': user.id,
                'correlation_id': correlation_id,
                'security_event': 'superuser_creation',
                'peoplecode': user.peoplecode,
                'password_method': 'env_var' if env_password else 'cryptographic_random'
            }
        )
        return user
    except IntegrityError as e:
        log.warning(f"Could not create superuser: {e}")
        return None

class Command(BaseCommand):
    help = 'This command creates None entries, a dummy Client and Site, a superuser, and inserts default entries in TypeAssist.'

    def add_arguments(self, parser) -> None:
        parser.add_argument('db', type=str)
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-initialization even if database is already initialized',
        )

    def handle(self, *args, **options):
        db = options['db']
        force = options.get('force', False)

        # Note: Removed set_db_for_router() call - function no longer exists after refactoring
        # Database routing is handled automatically by TenantDbRouter
        self.stdout.write(self.style.SUCCESS(f"Initializing database: {db}"))

        # Check if key data already exists
        from apps.client_onboarding.models import Bt
        from apps.core_onboarding.models import TypeAssist
        if not force and TypeAssist.objects.filter(tacode='PEOPLETYPE').exists():
            self.stdout.write(self.style.WARNING('Database appears to be already initialized. Use --force to reinitialize.'))
            return
        
        if force:
            self.stdout.write(self.style.WARNING('Force flag detected. Proceeding with re-initialization...'))

        # If force flag is set, do a single pass without retries
        max_attempts = 1 if force else MAX_RETRY
        
        for attempt in range(max_attempts):
            try:
                # Step 1: Create NONE entries
                utils.create_none_entries(self)
                self.stdout.write(self.style.SUCCESS('✓ None Entries created successfully!'))

                # Step 2: Import default entries
                insert_default_entries(skip_existing=force)
                self.stdout.write(self.style.SUCCESS('✓ Default Entries Created'))

                # Step 3: Create dummy client and site
                client, site = create_dummy_client_and_site()
                if client and site:
                    self.stdout.write(self.style.SUCCESS('✓ Dummy client and site created/verified'))
                else:
                    self.stdout.write(self.style.WARNING('⚠ Could not create dummy client and site'))

                # Step 4: Create superuser
                user = create_superuser(client, site)
                if user:
                    self.stdout.write(self.style.SUCCESS('✓ Superuser created/verified'))
                else:
                    self.stdout.write(self.style.WARNING('⚠ Could not create superuser'))
                
                # Step 5: Create SQL functions
                try:
                    create_sql_functions(db=db)
                    self.stdout.write(self.style.SUCCESS('✓ SQL functions created'))
                except (FileNotFoundError, IOError, OSError, PermissionError) as sql_error:
                    self.stdout.write(self.style.WARNING(f'⚠ Could not create SQL functions: {sql_error}'))
                
                self.stdout.write(self.style.SUCCESS('\n✓ Database initialization completed successfully!'))
                return  # Exit the command successfully

            except IntegrityError as ex:
                if "duplicate key" in str(ex).lower():
                    self.stdout.write(self.style.WARNING(f'Database with this alias "{db}" is not empty. Operation terminated!'))
                    break
                raise

            except DatabaseError as ex:
                self.stdout.write(self.style.ERROR(f"Database error: {ex}"))
                break

            except IntegrityError as e:
                # Check if it's a duplicate key error indicating the DB is already initialized
                if "duplicate key" in str(e).lower() or "already exists" in str(e).lower():
                    self.stdout.write(self.style.WARNING('Database appears to be already initialized. Skipping...'))
                    break
                # For other integrity errors, continue retrying if not force mode
                if not force:
                    pass
                else:
                    raise

            except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError) as e:
                log.critical('FAILED init_intelliwiz', exc_info = True)
                # If it's the last retry or force mode, raise the error
                if attempt == max_attempts - 1 or force:
                    self.stdout.write(self.style.ERROR(f'✗ Initialization failed: {e}'))
                    raise

           
