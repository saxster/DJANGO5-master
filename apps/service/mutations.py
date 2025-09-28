import graphene
    get_token,
    get_payload,
    get_refresh_token,
    create_refresh_token,
)
from graphql_jwt.decorators import login_required
from graphene.types.generic import GenericScalar
from graphql import GraphQLError
from apps.service import utils as sutils
from apps.peoples.models import People
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FileUploadParser, JSONParser
from rest_framework.response import Response
from django.core.serializers.json import DjangoJSONEncoder
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError
from . import types as ty
from graphene_file_upload.scalars import Upload
from rest_framework.permissions import AllowAny, IsAuthenticated
from pprint import pformat
import zipfile
from apps.core.utils_new.db_utils import get_current_db_name
import json
from .utils import get_json_data
from logging import getLogger
import traceback as tb
from apps.core import exceptions as excp

log = getLogger("message_q")
tlog = getLogger("tracking")
error_logger = getLogger("error_logger")
err = error_logger.error


class LoginUser(graphene.Mutation):
    """
    Authenticates user before log in
    """

    token = graphene.String()
    user = graphene.JSONString()
    payload = GenericScalar()
    msg = graphene.String()
    shiftid = graphene.Int()
    refreshtoken = graphene.String()

    class Arguments:
        input = ty.AuthInput(required=True)

    @classmethod
    def mutate(cls, root, info, input):
        log.warning("login mutations start [+]")
        try:
            log.info("%s, %s, %s", input.deviceid, input.loginid, input.password)
            from .auth import auth_check

            output, user = auth_check(info, input, cls.returnUser)
            cls.updateDeviceId(user, input)
            log.warning("login mutations end [-]")
            return output
        except (
            excp.MultiDevicesError,
            excp.NoClientPeopleError,
            excp.NoSiteError,
            excp.NotBelongsToClientError,
            excp.NotRegisteredError,
            excp.WrongCredsError,
        ) as exc:
            log.warning(exc, exc_info=True)
            raise GraphQLError(exc) from exc

        except (DatabaseError, ValueError, TypeError) as exc:
            err(f"Authentication system error: {exc}", exc_info=True)
            raise GraphQLError(f"Authentication system error") from exc

    @classmethod
    def returnUser(cls, user, request):
        user.last_login = timezone.now()
        user.save()
        token = get_token(user)
        request.jwt_refresh_token = create_refresh_token(user)
        log.info(f"user logged in successfully! {user.peoplename}")
        user = cls.get_user_json(user)
        return LoginUser(
            token=token,
            user=user,
            payload=get_payload(token, request),
            refreshtoken=request.jwt_refresh_token.get_token(),
        )

    @classmethod
    def updateDeviceId(cls, user, input):
        People.objects.update_deviceid(input.deviceid, user.id)

    @classmethod
    def get_user_json(cls, user):
        from django.db.models import F
        import json
        from apps.peoples.models import People  # Add this import
        from apps.onboarding.models import Bt    # Add this import

        emergencycontacts = set(
            People.objects.get_emergencycontacts(user.bu_id, user.client_id)
        )
        emergencyemails = set(
            People.objects.get_emergencyemails(user.bu_id, user.client_id)
        )
        log.info(f"emergencycontact: {pformat(emergencycontacts)}")
        log.info(f"emergencyemails: {pformat(emergencyemails)}")
        qset = (
            People.objects.annotate(
                loggername=F("peoplename"),
                mobilecapability=F("people_extras__mobilecapability"),
                pvideolength=F("client__bupreferences__pvideolength"),
                enablesleepingguard=F("client__enablesleepingguard"),
                skipsiteaudit=F("client__skipsiteaudit"),
                deviceevent=F("client__deviceevent"),
                isgpsenable=F("client__gpsenable"),
                clientcode=F("client__bucode"),
                clientname=F("client__buname"),
                clientenable=F("client__enable"),
                sitecode=F("bu__bucode"),
                sitename=F("bu__buname"),
            )
            .values(
                "loggername",
                "mobilecapability",
                "enablesleepingguard",
                "peopleimg",
                "skipsiteaudit",
                "deviceevent",
                "pvideolength",
                "client_id",
                "bu_id",
                "mobno",
                "email",
                "isverified",
                "deviceid",
                "id",
                "enable",
                "isadmin",
                "peoplecode",
                "dateofjoin",
                "tenant_id",
                "loginid",
                "clientcode",
                "clientname",
                "sitecode",
                "sitename",
                "clientenable",
                "isgpsenable",
            )
            .filter(id=user.id)
        )
        qsetList = list(qset)
        qsetList[0].update(
            {
                "emergencycontacts": list(emergencycontacts),
                "emergencyemails": list(emergencyemails),
            }
        )
        qsetList[0]["emergencyemails"] = (
            str(qsetList[0]["emergencyemails"])
            .replace("[", "")
            .replace("]", "")
            .replace("'", "")
        )
        qsetList[0]["emergencycontacts"] = (
            str(qsetList[0]["emergencycontacts"])
            .replace("[", "")
            .replace("]", "")
            .replace("'", "")
        )
        qsetList[0]["mobilecapability"] = (
            str(qsetList[0]["mobilecapability"])
            .replace("[", "")
            .replace("]", "")
            .replace("'", "")
        )

        # Add GPS location tracking logic
        track_user_location = False
        people_location = People.objects.filter(id=user.id).values_list('people_extras__enable_gps', flat=True).first()
        bt_location_enable = Bt.objects.filter(id=user.bu_id).values_list('gpsenable', flat=True).first()
        client_gps_enable = qsetList[0].get('isgpsenable')

        # Debug logging for GPS values
        log.info(f"GPS Debug - User ID: {user.id}, BU ID: {user.bu_id}, Client ID: {user.client_id}")
        log.info(f"GPS Debug - Client gpsenable (isgpsenable): {client_gps_enable}")
        log.info(f"GPS Debug - People enable_gps (people_location): {people_location}")
        log.info(f"GPS Debug - BU/Site gpsenable (bt_location_enable): {bt_location_enable}")

        # Check all three levels: client, site/BU, and user
        if people_location or bt_location_enable or client_gps_enable:
            track_user_location = True

        log.info(f"GPS Debug - Final track_user_location: {track_user_location}")
        qsetList[0].update({'track_user_location': track_user_location})

        print("qset",qset)
        return json.dumps(qsetList[0], cls=DjangoJSONEncoder)



class LogoutUser(graphene.Mutation):
    """
    Logs out user after resetting the deviceid
    """

    status = graphene.Int(default_value=404)
    msg = graphene.String(default_value="Failed")

    @classmethod
    @login_required
    def mutate(cls, root, info):
        updated = People.objects.reset_deviceid(info.context.user.id)
        if updated:
            status, msg = 200, "Success"
            # log.info(f'user logged out successfully! {user.}')

        return LogoutUser(status=status, msg=msg)


class TaskTourUpdate(graphene.Mutation):
    """
    Update Task, Tour fields.
    like 'cdtz', 'mdtz', 'jobstatus', 'performedby' etc
    """

    output = graphene.Field(ty.ServiceOutputType)

    class Arguments:
        records = graphene.List(graphene.String, required=True)

    @classmethod
    @login_required
    def mutate(cls, root, info, records):
        log.warning("\n\ntasktour-update mutations start [+]")
        db = get_current_db_name()
        o = sutils.perform_tasktourupdate(records=records, request=info.context, db=db)
        log.info(
            f"Response: # records updated:{o.recordcount}, msg:{o.msg}, rc:{o.rc}, traceback:{o.traceback}"
        )
        log.warning("tasktour-update mutations end [-]")
        return TaskTourUpdate(output=o)


class InsertRecord(graphene.Mutation):
    """
    Inserts new record in the specified table.
    """

    output = graphene.Field(ty.ServiceOutputType)

    class Arguments:
        records = graphene.List(graphene.String, required=True)

    @classmethod
    @login_required
    def mutate(cls, root, info, records):
        log.warning("\n\ninsert-record mutations start [+]")
        db = get_current_db_name()
        log.info(f"Records: {records}")
        o = sutils.perform_insertrecord(records=records, db=db)
        log.info(
            f"Response: # records updated:{o.recordcount}, msg:{o.msg}, rc:{o.rc}, traceback:{o.traceback}"
        )
        log.warning("insert-record mutations end [-]")
        return InsertRecord(output=o)


class ReportMutation(graphene.Mutation):
    output = graphene.Field(ty.ServiceOutputType)

    class Arguments:
        records = graphene.List(graphene.String, required=True)

    @classmethod
    @login_required
    def mutate(cls, root, info, records):
        log.warning("\n\nreport mutations start [+]")
        db = get_current_db_name()
        o = sutils.perform_reportmutation(records=records, db=db)
        log.info(f"Response: {o.recordcount}, {o.msg}, {o.rc}, {o.traceback}")
        log.warning("report mutations end [-]")
        return ReportMutation(output=o)


class UploadAttMutaion(graphene.Mutation):
    """
    DEPRECATED: Legacy Base64 upload mutation with security vulnerabilities.

    Security Issues:
    - Uses vulnerable perform_uploadattachment function
    - No file validation or content checks
    - Inefficient Base64 encoding

    Use SecureFileUploadMutation instead.
    """
    output = graphene.Field(ty.ServiceOutputType)

    class Arguments:
        bytes = graphene.String(required=True)  # Changed from List[Int] to String for Base64
        biodata = graphene.String(required=True)
        record = graphene.String(required=True)

    @classmethod
    @login_required
    def mutate(cls, root, info, bytes, record, biodata):
        """
        DEPRECATED ENDPOINT - MIGRATION REQUIRED

        This mutation has been deprecated due to security vulnerabilities.
        Please migrate to SecureFileUploadMutation.

        The function still works but logs deprecation warnings and applies
        additional security validation via the refactored perform_uploadattachment.
        """
        log.warning(
            "DEPRECATED API USAGE: UploadAttMutaion called",
            extra={
                'user_id': info.context.user.id if hasattr(info.context, 'user') else None,
                'migration_required': True,
                'recommended_mutation': 'SecureFileUploadMutation'
            }
        )

        try:
            import base64
            recordcount = 0

            file_bytes = base64.b64decode(bytes)

            record = json.loads(record)
            biodata = json.loads(biodata)

            log.info(
                "Legacy upload processing with enhanced security",
                extra={
                    'file_size': len(file_bytes),
                    'ownername': biodata.get('ownername'),
                    'user_id': info.context.user.id if hasattr(info.context, 'user') else None
                }
            )

            o = sutils.perform_uploadattachment(file_bytes, record, biodata)
            recordcount += o.recordcount

            if o.rc != 0:
                log.error(
                    "Legacy upload failed",
                    extra={'msg': o.msg, 'traceback': o.traceback}
                )

            o.recordcount = recordcount
            return UploadAttMutaion(output=o)

        except (IOError, OSError, ValidationError) as e:
            err(f"File operation error in deprecated upload: {e}", exc_info=True)
            return UploadAttMutaion(
                output=ty.ServiceOutputType(
                    rc=1, recordcount=0, msg=f"Upload Failed: {e}", traceback=str(e)
                )
            )
        except DatabaseError as e:
            err(f"Database error during deprecated upload: {e}", exc_info=True)
            return UploadAttMutaion(
                output=ty.ServiceOutputType(
                    rc=1, recordcount=0, msg="Database error during upload", traceback=str(e)
                )
            )


class SecureFileUploadMutation(graphene.Mutation):
    """
    Secure GraphQL file upload mutation with comprehensive validation.

    Features:
    - Requires authentication via login_required decorator
    - Uses SecureFileUploadService for file validation
    - Prevents path traversal attacks
    - Content type and size validation
    - Comprehensive error handling and logging
    """
    output = graphene.Field(ty.ServiceOutputType)

    class Arguments:
        file = Upload(required=True, description="File to upload")
        biodata = graphene.String(required=True, description="JSON string with upload metadata")
        record = graphene.String(required=True, description="JSON string with record data")
        file_type = graphene.String(
            required=False,
            description="File type: image, pdf, document. Auto-detected if not provided."
        )

    @classmethod
    @login_required
    def mutate(cls, root, info, file, biodata, record, file_type=None):
        from apps.core.services.secure_file_upload_service import SecureFileUploadService
        from django.core.exceptions import ValidationError

        correlation_id = f"gql_upload_{info.context.user.id}_{int(timezone.now().timestamp())}"

        log.info(
            "Starting secure GraphQL file upload",
            extra={
                'user_id': info.context.user.id,
                'correlation_id': correlation_id,
                'filename': getattr(file, 'name', 'unknown')
            }
        )

        try:
            # Validate user is authenticated
            if not info.context.user.is_authenticated:
                log.warning("Unauthenticated file upload attempt", extra={'correlation_id': correlation_id})
                return SecureFileUploadMutation(
                    output=ty.ServiceOutputType(
                        rc=1, recordcount=0, msg="Authentication required", traceback="Unauthenticated"
                    )
                )

            # Safely parse JSON inputs
            try:
                biodata_dict = json.loads(biodata)
                record_dict = json.loads(record)
            except (json.JSONDecodeError, TypeError) as e:
                log.error("Invalid JSON in GraphQL upload", extra={'correlation_id': correlation_id}, exc_info=True)
                return SecureFileUploadMutation(
                    output=ty.ServiceOutputType(
                        rc=1, recordcount=0, msg="Invalid JSON format", traceback=str(e)
                    )
                )

            # Validate required fields
            required_biodata_fields = ['filename', 'people_id', 'owner', 'ownername']
            for field in required_biodata_fields:
                if field not in biodata_dict:
                    return SecureFileUploadMutation(
                        output=ty.ServiceOutputType(
                            rc=1, recordcount=0, msg=f"Missing required field: {field}", traceback="Validation"
                        )
                    )

            # Auto-detect file type if not provided
            if not file_type:
                filename = biodata_dict['filename']
                file_extension = filename.lower().split('.')[-1] if '.' in filename else ''

                if file_extension in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                    file_type = 'image'
                elif file_extension in ['pdf']:
                    file_type = 'pdf'
                elif file_extension in ['doc', 'docx', 'txt', 'rtf']:
                    file_type = 'document'
                else:
                    return SecureFileUploadMutation(
                        output=ty.ServiceOutputType(
                            rc=1, recordcount=0, msg=f"Unsupported file type: .{file_extension}", traceback="Validation"
                        )
                    )

            # Create secure upload context
            upload_context = {
                'people_id': biodata_dict['people_id'],
                'folder_type': biodata_dict.get('path', 'general').strip('/'),
                'user_id': info.context.user.id,
                'correlation_id': correlation_id
            }

            # Use AdvancedFileValidationService for enhanced security validation and malware scanning
            try:
                from apps.core.services.advanced_file_validation_service import AdvancedFileValidationService

                file_metadata = AdvancedFileValidationService.validate_and_scan_file(
                    uploaded_file=file,
                    file_type=file_type,
                    upload_context=upload_context
                )

                # Save file securely
                secure_file_path = SecureFileUploadService.save_uploaded_file(file, file_metadata)

                # Update record with secure information
                record_dict['localfilepath'] = secure_file_path
                record_dict['filename'] = file_metadata['filename']
                record_dict['file_size'] = file_metadata['file_size']
                record_dict['correlation_id'] = file_metadata['correlation_id']

                # Process using secure attachment function
                output = sutils.perform_secure_uploadattachment(
                    file_path=secure_file_path,
                    record=record_dict,
                    biodata=biodata_dict,
                    file_metadata=file_metadata
                )

                log.info(
                    "Secure GraphQL file upload completed successfully",
                    extra={
                        'user_id': info.context.user.id,
                        'correlation_id': correlation_id,
                        'file_size': file_metadata['file_size'],
                        'file_type': file_type,
                        'rc': output.rc
                    }
                )

                # Return response with correlation ID
                output.traceback = output.traceback if output.rc != 0 else None
                return SecureFileUploadMutation(output=output)

            except ValidationError as e:
                log.warning(
                    "GraphQL file upload validation failed",
                    extra={
                        'user_id': info.context.user.id,
                        'correlation_id': correlation_id,
                        'error': str(e)
                    }
                )
                return SecureFileUploadMutation(
                    output=ty.ServiceOutputType(
                        rc=1, recordcount=0, msg=f"File validation failed: {str(e)}", traceback=str(e)
                    )
                )

        except (IOError, OSError, DatabaseError) as e:
            log.error(
                "File or database error in secure GraphQL file upload",
                extra={
                    'user_id': info.context.user.id if hasattr(info.context, 'user') else None,
                    'correlation_id': correlation_id,
                    'error': str(e)
                },
                exc_info=True
            )
            return SecureFileUploadMutation(
                output=ty.ServiceOutputType(
                    rc=1, recordcount=0, msg="File or database operation error", traceback=f"Error ID: {correlation_id}"
                )
            )


class SecureUploadFile(APIView):
    """
    Secure file upload endpoint with comprehensive validation.

    Replaces the vulnerable UploadFile class that had:
    - AllowAny permission (SECURITY RISK)
    - Path traversal vulnerability
    - No file validation

    This implementation:
    - Requires authentication
    - Uses SecureFileUploadService for validation
    - Prevents path traversal attacks
    - Validates file content and types
    """
    parser_classes = [MultiPartParser, FileUploadParser, JSONParser]
    permission_classes = [IsAuthenticated]

    def post(self, request, format=None):
        from apps.core.services.secure_file_upload_service import SecureFileUploadService
        from django.core.exceptions import ValidationError
        from rest_framework.permissions import IsAuthenticated

        try:
            # Extract and validate input data
            file = request.data.get("file")
            if not file:
                return Response(
                    data={"rc": 1, "msg": "No file provided", "recordcount": 0},
                    status=400
                )

            # Safely parse JSON data with validation
            try:
                biodata_raw = request.data.get("biodata")
                record_raw = request.data.get("record")

                if not biodata_raw or not record_raw:
                    return Response(
                        data={"rc": 1, "msg": "Missing biodata or record", "recordcount": 0},
                        status=400
                    )

                biodata = json.loads(biodata_raw)
                record = json.loads(record_raw)

            except (json.JSONDecodeError, TypeError) as e:
                log.error("Invalid JSON in upload request", exc_info=True)
                return Response(
                    data={"rc": 1, "msg": "Invalid JSON format", "recordcount": 0},
                    status=400
                )

            # Validate required fields in biodata
            required_fields = ['filename', 'people_id', 'owner', 'ownername']
            for field in required_fields:
                if field not in biodata:
                    return Response(
                        data={"rc": 1, "msg": f"Missing required field: {field}", "recordcount": 0},
                        status=400
                    )

            # Determine file type based on filename
            filename = biodata['filename']
            file_extension = filename.lower().split('.')[-1] if '.' in filename else ''

            if file_extension in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                file_type = 'image'
            elif file_extension in ['pdf']:
                file_type = 'pdf'
            elif file_extension in ['doc', 'docx', 'txt', 'rtf']:
                file_type = 'document'
            else:
                return Response(
                    data={"rc": 1, "msg": f"Unsupported file type: .{file_extension}", "recordcount": 0},
                    status=400
                )

            # Create secure upload context
            upload_context = {
                'people_id': biodata['people_id'],
                'folder_type': biodata.get('path', 'general').strip('/'),  # Sanitize path
                'user_id': request.user.id,
                'correlation_id': f"upload_{request.user.id}_{int(timezone.now().timestamp())}"
            }

            # Use AdvancedFileValidationService for enhanced security validation and malware scanning
            try:
                from apps.core.services.advanced_file_validation_service import AdvancedFileValidationService

                file_metadata = AdvancedFileValidationService.validate_and_scan_file(
                    uploaded_file=file,
                    file_type=file_type,
                    upload_context=upload_context
                )

                # Save file securely
                secure_file_path = SecureFileUploadService.save_uploaded_file(file, file_metadata)

                # Update record with secure path information
                record['localfilepath'] = secure_file_path
                record['filename'] = file_metadata['filename']
                record['file_size'] = file_metadata['file_size']
                record['correlation_id'] = file_metadata['correlation_id']

                # Use secure attachment processing
                output = sutils.perform_secure_uploadattachment(
                    file_path=secure_file_path,
                    record=record,
                    biodata=biodata,
                    file_metadata=file_metadata
                )

                log.info(
                    "Secure file upload completed successfully",
                    extra={
                        'user_id': request.user.id,
                        'correlation_id': file_metadata['correlation_id'],
                        'file_size': file_metadata['file_size'],
                        'file_type': file_type
                    }
                )

            except ValidationError as e:
                log.warning(
                    "File upload validation failed",
                    extra={
                        'user_id': request.user.id,
                        'error': str(e),
                        'filename': biodata.get('filename', 'unknown')
                    }
                )
                return Response(
                    data={"rc": 1, "msg": f"File validation failed: {str(e)}", "recordcount": 0},
                    status=400
                )

            resp = Response(
                data={
                    "rc": output.rc,
                    "msg": output.msg,
                    "recordcount": output.recordcount,
                    "file_id": file_metadata['correlation_id'],
                    "traceback": output.traceback if output.rc != 0 else None,
                }
            )

            log.info(f"Secure upload response: rc={output.rc}, msg={output.msg}")
            return resp

        except (IOError, OSError, DatabaseError, ValidationError) as e:
            correlation_id = f"error_{request.user.id if request.user.is_authenticated else 'anon'}_{int(timezone.now().timestamp())}"

            log.error(
                "File or database error in secure file upload",
                extra={
                    'user_id': request.user.id if request.user.is_authenticated else None,
                    'correlation_id': correlation_id,
                    'error': str(e),
                    'error_type': type(e).__name__
                },
                exc_info=True
            )

            return Response(
                data={
                    "rc": 1,
                    "msg": "Internal server error during file upload",
                    "recordcount": 0,
                    "error_id": correlation_id
                },
                status=500
            )


class AdhocMutation(graphene.Mutation):
    output = graphene.Field(ty.ServiceOutputType)

    class Arguments:
        records = graphene.List(graphene.String, required=True)

    @classmethod
    @login_required
    def mutate(cls, root, info, records):
        db = get_current_db_name()
        o = sutils.perform_adhocmutation(records=records, db=db)
        log.info(f"Response: {o.recordcount}, {o.msg}, {o.rc}, {o.traceback}")
        return AdhocMutation(output=o)


class InsertJsonMutation(graphene.Mutation):
    output = graphene.Field(ty.ServiceOutputType)

    class Arguments:
        jsondata = graphene.List(graphene.String, required=True)
        tablename = graphene.String(required=True)

    @classmethod
    @login_required
    def mutate(cls, root, info, jsondata, tablename):
        # sourcery skip: instance-method-first-arg-name
        from .utils import insertrecord_json
        from apps.core.utils import get_current_db_name
        import json

        tlog.info("\n\n\ninsert jsondata mutations start[+]")
        rc, traceback, resp, recordcount = 1, "NA", 0, 0
        msg = "Insert Failed!"
        uuids = []
        try:
            db = get_current_db_name()
            tlog.info(f"=================== jsondata:============= \n{jsondata}")
            uuids = insertrecord_json(jsondata, tablename)
            recordcount, msg, rc = 1, "Inserted Successfully", 0
        except (DatabaseError, IntegrityError) as e:
            err(f"Database error during insert: {e}", exc_info=True)
            msg, rc, traceback = f"Insert Failed: Database error", 1, str(e)
        except (ValidationError, ValueError, TypeError) as e:
            err(f"Data validation error during insert: {e}", exc_info=True)
            msg, rc, traceback = f"Validation Failed: {type(e).__name__}", 1, str(e)

        o = ty.ServiceOutputType(
            rc=rc, recordcount=recordcount, msg=msg, traceback=traceback, uuids=uuids
        )
        tlog.info(
            f"\n\n\nResponse: {o.recordcount}, {o.msg}, {o.rc}, {o.traceback} {uuids=}"
        )
        return InsertJsonMutation(output=o)


class SyncMutation(graphene.Mutation):
    rc = graphene.Int()

    class Arguments:
        file = Upload(required=True)
        filesize = graphene.Int(required=True)
        totalrecords = graphene.Int(required=True)

    @classmethod
    @login_required
    def mutate(cls, root, info, file, filesize, totalrecords):
        # sourcery skip: avoid-builtin-shadow
        from apps.core.utils import get_current_db_name

        log.info("\n\nsync now mutation is running")
        import zipfile
        from apps.service.utils import call_service_based_on_filename

        try:
            id = file.name.split("_")[1].split(".")[0]
            log.info(
                f"sync inputs: totalrecords:{totalrecords} filesize:{filesize} typeof file:{type(file)} by user with id {id}"
            )
            db = get_current_db_name()
            log.info(f"the type of file is {type(file)}")
            with zipfile.ZipFile(file) as zip:
                log.debug(f"{file = }")
                zipsize = TR = 0
                for file in zip.filelist:
                    log.debug(f"{file = }")
                    zipsize += file.file_size
                    log.info(f"filename: {file.filename} and size: {file.file_size}")
                    with zip.open(file) as f:
                        data = get_json_data(f)
                        # raise ValueError
                        TR += len(data)
                        call_service_based_on_filename(
                            data, file.filename, db=db, request=info.context, user=id
                        )
                log.info(f"file size given: {filesize = } and calculated {zipsize = }")
                if filesize != zipsize:
                    log.error(
                        f"file size is not matched with the actual zipfile {filesize} x {zipsize}"
                    )
                    raise excp.FileSizeMisMatchError
                if TR != totalrecords:
                    log.error(
                        f"totalrecords is not matched with th actual totalrecords after extraction... {totalrecords} x {TR}"
                    )
                    raise excp.TotalRecordsMisMatchError
        except (excp.FileSizeMisMatchError, excp.TotalRecordsMisMatchError) as e:
            err(f"Data integrity error in sync: {e}", exc_info=True)
            return SyncMutation(rc=1)
        except (DatabaseError, ValidationError) as e:
            err(f"Database or validation error in sync: {e}", exc_info=True)
            return SyncMutation(rc=1)
        except (ValueError, TypeError, zipfile.BadZipFile) as e:
            err(f"Data or file format error in sync: {e}", exc_info=True)
            return SyncMutation(rc=1)
        else:
            return SyncMutation(rc=0)


class TestMutation(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)

    output = graphene.String()

    @classmethod
    def mutate(cls, root, info, name):
        return TestMutation(output=f"Hello {name}")
