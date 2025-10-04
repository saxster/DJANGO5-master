from django.core.management.base import BaseCommand
from django.db.utils import IntegrityError
from apps.core import utils
from apps.core import exceptions as excp
from apps.onboarding.models import Bt, TypeAssist
from apps.peoples.models import People
from apps.onboarding.admin import TaResource
from apps.peoples.admin import CapabilityResource
from django.conf import settings
from tablib import Dataset
import logging
import psycopg2
import uuid

log = logging.getLogger(__name__)

MAX_RETRY = 5
DEFAULT_PASSWORD = 'superadmin@2022#'

def create_dummy_client_and_site():
    try:
        client_type = TypeAssist.objects.get(tatype__tacode = 'BVIDENTIFIER', tacode='CLIENT')
        site_type = TypeAssist.objects.get(tatype__tacode = 'BVIDENTIFIER', tacode='SITE')
    except TypeAssist.DoesNotExist:
        log.warning("Required TypeAssist entries for CLIENT/SITE not found, skipping client/site creation")
        return None, None

    # Get the NONE Bt as parent for client
    try:
        parent_bt = Bt.objects.get(bucode='NONE')
    except Bt.DoesNotExist:
        parent_bt = None
    
    client, created = Bt.objects.get_or_create(
        bucode='SPS', 
        defaults={
            'buname': "Security Personnel Services", 
            'enable': True, 
            'identifier': client_type, 
            'parent': parent_bt  # Use the parent object instead of parent_id
        }
    )
    if created:
        log.info("Created dummy client: SPS")
    else:
        log.info("Client SPS already exists")

    site, created = Bt.objects.get_or_create(
        bucode='YTPL', 
        defaults={'buname': 'Youtility Technologies Pvt Ltd', 'enable': True, 'identifier':site_type, 'parent_id':client.id}
    )
    if created:
        log.info("Created dummy site: YTPL")
    else:
        log.info("Site YTPL already exists")
    
    return client, site

def create_sql_functions(db):
    from apps.core.raw_sql_functions import get_sqlfunctions
    sql_functions_list = get_sqlfunctions().values()
    # Connect to the database
    DBINFO = settings.DATABASES[db]
    conn = psycopg2.connect(
        database=DBINFO['NAME'],
        user=DBINFO['USER'],
        password=DBINFO['PASSWORD'],
        host=DBINFO['HOST'],
        port=DBINFO['PORT'])
    
    # Create a new cursor object
    cur = conn.cursor()
    
    for function in sql_functions_list:
        cur.execute(function)
        conn.commit()
    
    # Close the cursor and connection
    cur.close()
    conn.close()

    
    

def insert_default_entries(skip_existing=False):
    BASE_DIR = settings.BASE_DIR
    filepaths_and_resources = {
        f'{BASE_DIR}/docs/default_types.xlsx': TaResource,
        f'{BASE_DIR}/docs/caps.xlsx': CapabilityResource
    }

    for filepath, Resource in filepaths_and_resources.items():
        with open(filepath, 'rb') as f:
            default_types = Dataset().load(f)
            resource = Resource(is_superuser=True)
            try:
                # Try to import with skip_unchanged to handle existing records
                result = resource.import_data(
                    default_types, 
                    dry_run=False, 
                    use_transactions=True, 
                    raise_errors=not skip_existing  # Don't raise errors if skip_existing is True
                )
                if result.has_errors() and not skip_existing:
                    log.error(f"Import errors from {filepath}: {result.errors}")
                    raise Exception(f"Import failed with errors: {result.errors}")
                else:
                    log.info(f"Successfully imported data from {filepath}")
            except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError) as e:
                if skip_existing and "already exist" in str(e):
                    log.info(f"Skipping existing records from {filepath}")
                else:
                    raise

def create_superuser(client, site):
    if not client or not site:
        log.warning("Cannot create superuser without client and site")
        return None
    
    try:
        user = People.objects.get(loginid="superadmin")
        log.info("Superuser with loginid 'superadmin' already exists")
        return user
    except People.DoesNotExist:
        pass
    
    try:
        user = People.objects.create(
            peoplecode='SUPERADMIN', loginid="superadmin", peoplename='Super Admin',
            dateofbirth='1111-11-11', dateofjoin='1111-11-11',
            email='superadmin@youtility.in', isverified=True,
            is_staff=True, is_superuser=True,
            isadmin=True, client=client, bu=site
        )
        user.set_password(DEFAULT_PASSWORD)
        user.save()

        # SECURITY FIX: Never log passwords (PCI-DSS compliance, CVSS 9.1 violation)
        # Use correlation ID for tracking instead of exposing credentials
        correlation_id = str(uuid.uuid4())
        log.info(
            f"Superuser created successfully with loginid: {user.loginid}",
            extra={
                'user_id': user.id,
                'correlation_id': correlation_id,
                'security_event': 'superuser_creation',
                'peoplecode': user.peoplecode
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
        
        # Check if database is already initialized
        utils.set_db_for_router(db)
        self.stdout.write(self.style.SUCCESS(f"Current DB selected is {utils.get_current_db_name()}"))
        
        # Check if key data already exists
        from apps.onboarding.models import TypeAssist, Bt
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

            except excp.RecordsAlreadyExist as ex:
                self.stdout.write(self.style.WARNING(f'Database with this alias "{db}" is not empty. Operation terminated!'))
                break

            except excp.NoDbError:
                self.stdout.write(self.style.ERROR(f"Database with alias '{db}' does not exist. Operation cannot be performed."))
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

           
