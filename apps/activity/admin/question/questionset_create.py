"""
QuestionSet CREATE Resource for Django Admin Import/Export.

Handles creation of new QuestionSet records with ArrayField support.
Import template: Question Set Name*, QuestionSet Type*, Client*, Site*, Seq No*, etc.

Special Features:
- ArrayField widgets for includes (Asset/Site/Site Group/Site Type)
- Boolean field handling (Show To All Sites)
- Hierarchical parent relationships (Belongs To*)
- NaN value sanitization for pandas imports

Extracted from: apps/activity/admin/question_admin.py (lines 688-976)
Date: 2025-10-10
"""

from django.core.exceptions import ValidationError
from django.apps import apps
from import_export import fields, resources
from import_export import widgets as wg
from apps.activity.models.question_model import QuestionSet
from apps.client_onboarding.models import Bt, Shift
from apps.core_onboarding.models import TypeAssist, GeofenceMaster, Bu
from apps.core import utils

from .base import default_ta, AUTHORIZED_QUESTIONSET_TYPES
from .widgets import ArrayFieldWidget


class QuestionSetResource(resources.ModelResource):
    """
    Import/Export resource for creating new QuestionSet records.

    Field Definitions:
    - CLIENT: Client* (required) - Foreign key to Bt (bucode)
    - BV: Site* (required) - Foreign key to Bt (bucode)
    - BelongsTo: Belongs To* - Foreign key to parent QuestionSet (qsetname), defaults to NONE
    - id: ID - QuestionSet ID (auto-assigned)
    - SEQNO: Seq No* (required, default=-1) - Sequence number for ordering
    - QSETNAME: Question Set Name* (required) - Unique name for the question set
    - Type: QuestionSet Type* (required) - Must be one of AUTHORIZED_QUESTIONSET_TYPES
    - ASSETINCLUDES: Asset Includes - ArrayField of asset codes (default=[])
    - SITEINCLUDES: Site Includes - ArrayField of site codes (default=[])
    - SITEGRPINCLUDES: Site Group Includes - ArrayField of site group names (default=[])
    - SITETYPEINCLUDES: Site Type Includes - ArrayField of site type codes (default=[])
    - SHOWTOALLSITES: Show To All Sites - Boolean field (default=False)
    - URL: URL - String field (default="NONE")

    Import Workflow:
    1. Clean NaN values (pandas compatibility)
    2. Check required fields (QuestionSet Type*, Question Set Name*, Seq No*)
    3. Clean boolean fields (Show To All Sites)
    4. Validate row data (check foreign key references)
    5. Unique record check (prevent duplicates)
    6. Verify valid questionset type (must be in AUTHORIZED_QUESTIONSET_TYPES)
    7. Before save: Set tenant_id and save common stuff
    """
    CLIENT = fields.Field(
        column_name="Client*",
        attribute="client",
        widget=wg.ForeignKeyWidget(om.Bt, "bucode"),
        default=default_ta,
    )
    BV = fields.Field(
        column_name="Site*",
        attribute="bu",
        widget=wg.ForeignKeyWidget(om.Bt, "bucode"),
        default=default_ta,
    )

    BelongsTo = fields.Field(
        column_name="Belongs To*",
        default=default_ta,
        attribute="parent",
        widget=wg.ForeignKeyWidget(QuestionSet, "qsetname"),
    )

    id = fields.Field(attribute="id", column_name="ID")
    SEQNO = fields.Field(attribute="seqno", column_name="Seq No*", default=-1)
    QSETNAME = fields.Field(attribute="qsetname", column_name="Question Set Name*")
    Type = fields.Field(attribute="type", column_name="QuestionSet Type*")
    ASSETINCLUDES = fields.Field(
        attribute="assetincludes", column_name="Asset Includes",
        widget=ArrayFieldWidget(), default=[]
    )
    SITEINCLUDES = fields.Field(
        attribute="buincludes", column_name="Site Includes",
        widget=ArrayFieldWidget(), default=[]
    )
    SITEGRPINCLUDES = fields.Field(
        attribute="site_grp_includes", column_name="Site Group Includes",
        widget=ArrayFieldWidget(), default=[]
    )
    SITETYPEINCLUDES = fields.Field(
        attribute="site_type_includes", column_name="Site Type Includes",
        widget=ArrayFieldWidget(), default=[]
    )
    SHOWTOALLSITES = fields.Field(
        attribute="show_to_all_sites", column_name="Show To All Sites", default=False
    )
    URL = fields.Field(attribute="url", column_name="URL", default="NONE")

    class Meta:
        model = QuestionSet
        skip_unchanged = True
        report_skipped = True
        fields = [
            "Question Set Name*",
            "ASSETINCLUDES",
            "SITEINCLUDES",
            "SITEGRPINCLUDES",
            "SITETYPEINCLUDES",
            "SHOWTOALLSITES",
            "URL",
            "BV",
            "CLIENT",
            "Type",
            "BelongsTo",
            "SEQNO",
            "ID",
            "Name",
        ]

    def __init__(self, *args, **kwargs):
        super(QuestionSetResource, self).__init__(*args, **kwargs)
        self.is_superuser = kwargs.pop("is_superuser", None)
        self.request = kwargs.pop("request", None)

    def before_import_row(self, row, row_number, **kwargs):
        self.clean_nan_values(row)  # Clean all nan values first
        self.check_required_fields(row)
        self.clean_boolean_fields(row)
        self.validate_row(row)
        self.unique_record_check(row)
        self.verify_valid_questionset_type(row)
        super().before_import_row(row, **kwargs)

    def clean_nan_values(self, row):
        """Clean all nan values from the row before processing"""
        import math

        # List of ArrayField columns that should be empty lists instead of nan
        array_fields = ["Site Group Includes", "Site Includes", "Asset Includes", "Site Type Includes"]

        for field in array_fields:
            value = row.get(field)
            if value is None:
                row[field] = []
            elif isinstance(value, float) and math.isnan(value):
                row[field] = []
            elif isinstance(value, str) and value.strip() == "":
                row[field] = []

        # Clean Seq No* field - convert nan to -1 (default)
        seq_no = row.get("Seq No*")
        if seq_no is None or (isinstance(seq_no, float) and math.isnan(seq_no)):
            row["Seq No*"] = -1

        # Clean Belongs To* field - convert nan to "NONE"
        belongs_to = row.get("Belongs To*")
        if belongs_to is None or (isinstance(belongs_to, float) and math.isnan(belongs_to)):
            row["Belongs To*"] = "NONE"

    def clean_boolean_fields(self, row):
        """Clean boolean fields by converting nan values to False"""
        boolean_field = "Show To All Sites"
        field_value = row.get(boolean_field)

        # Handle nan, None, empty string
        if field_value is None or field_value == "":
            row[boolean_field] = False
        elif isinstance(field_value, float):
            import math
            if math.isnan(field_value):
                row[boolean_field] = False
            else:
                # Convert float to boolean (0 = False, non-zero = True)
                row[boolean_field] = bool(field_value)
        elif isinstance(field_value, str):
            # Handle string values
            field_value_upper = field_value.strip().upper()
            if field_value_upper in ["TRUE", "YES", "1", "Y"]:
                row[boolean_field] = True
            elif field_value_upper in ["FALSE", "NO", "0", "N", ""]:
                row[boolean_field] = False
            else:
                # Default to False for unrecognized values
                row[boolean_field] = False
        elif isinstance(field_value, bool):
            # Already a boolean, keep as is
            pass
        else:
            # Default to False for other types
            row[boolean_field] = False

        # Also clean the URL field - convert nan to "NONE"
        url_value = row.get("URL")
        if url_value is None or url_value == "":
            row["URL"] = "NONE"
        elif isinstance(url_value, float):
            import math
            if math.isnan(url_value):
                row["URL"] = "NONE"
        # If it's already a string, leave it as is

    def verify_valid_questionset_type(self, row):
        """
        Validate that questionset type is in AUTHORIZED_QUESTIONSET_TYPES.

        Valid types:
        - CHECKLIST
        - RPCHECKLIST
        - INCIDENTREPORT
        - SITEREPORT
        - WORKPERMIT
        - RETURN_WORK_PERMIT
        - KPITEMPLATE
        - SCRAPPEDTEMPLATE
        - ASSETAUDIT
        - ASSETMAINTENANCE
        - WORK_ORDER
        """
        questionset_type = row.get("QuestionSet Type*")
        if questionset_type not in AUTHORIZED_QUESTIONSET_TYPES:
            raise ValidationError(
                {
                    questionset_type: f"{questionset_type} is not a valid Questionset Type. Please select a valid QuestionSet."
                }
            )

    def check_required_fields(self, row):
        """
        Check that all required fields are present and non-empty.

        Required fields:
        - QuestionSet Type*
        - Question Set Name*
        - Seq No*
        """
        required_fields = ["QuestionSet Type*", "Question Set Name*", "Seq No*"]
        for field in required_fields:
            if not row.get(field):
                raise ValidationError({field: f"{field} is a required field"})

        """ optional_fields = ['Site Group Includes', 'Site Includes', 'Asset Includes', 'Site Type Includes']
        if all(not row.get(field) for field in optional_fields):
            raise ValidationError("You should provide a value for at least one field from the following: "
                                "'Site Group Includes', 'Site Includes', 'Asset Includes', 'Site Type Includes'") """

    def validate_row(self, row):
        """
        Validate that all foreign key references exist in the database.

        Validates:
        - Site Group Includes: Pgroup.groupname (stores group names)
        - Site Includes: Bt.bucode (stores site codes)
        - Asset Includes: Asset.assetcode (stores asset codes)
        - Site Type Includes: TypeAssist.tacode (stores type codes)

        All fields are ArrayFields that store the actual values (not IDs).
        """
        models_mapping = {
            "Site Group Includes": ("peoples", "Pgroup", "groupname", "groupname"),  # ArrayField - store group names
            "Site Includes": ("onboarding", "Bt", "bucode", "bucode"),  # ArrayField - store codes
            "Asset Includes": ("activity", "Asset", "assetcode", "assetcode"),  # ArrayField - store codes
            "Site Type Includes": ("onboarding", "TypeAssist", "tacode", "tacode"),  # ArrayField - store codes
        }

        for field, (app_name, model_name, lookup_field, result_field) in models_mapping.items():
            field_value = row.get(field)

            # Handle already processed list values (from ArrayFieldWidget)
            if isinstance(field_value, list):
                # If it's already a list (processed by widget), validate if not empty
                if field_value and field_value != []:
                    model = apps.get_model(app_name, model_name)
                    # Filter out empty strings from the list
                    values = [v for v in field_value if v and v.strip()]

                    if values:  # Only validate if there are actual values
                        existing_records = model.objects.filter(**{f"{lookup_field}__in": values})
                        existing_values = list(existing_records.values_list(lookup_field, flat=True))

                        if len(values) != len(existing_values):
                            missing = set(values) - set(existing_values)
                            raise ValidationError(
                                {
                                    field: f"Some of the values specified in {field} do not exist in the system: {', '.join(missing)}"
                                }
                            )
                        # Store the validated values
                        row[field] = values
                    else:
                        # Empty list after filtering
                        row[field] = []
                else:
                    # Empty list, keep as is
                    row[field] = []
                continue

            # Skip if field_value is None, nan (float), or empty
            if field_value is not None:
                # Check if it's a nan float value
                if isinstance(field_value, float):
                    import math
                    if math.isnan(field_value):
                        # Set to empty list for ArrayFields instead of leaving as nan
                        row[field] = []
                        continue
                # Convert to string and process
                field_value = str(field_value).strip()
                if field_value:  # Check again after stripping
                    model = apps.get_model(app_name, model_name)
                    values = field_value.replace(" ", "").split(",")
                    # Filter out empty values
                    values = [v.strip() for v in values if v.strip()]

                    if values:  # Only validate if there are actual values
                        # Validate that all values exist
                        existing_records = model.objects.filter(**{f"{lookup_field}__in": values})
                        existing_values = list(existing_records.values_list(lookup_field, flat=True))

                        if len(values) != len(existing_values):
                            missing = set(values) - set(existing_values)
                            raise ValidationError(
                                {
                                    field: f"Some of the values specified in {field} do not exist in the system: {', '.join(missing)}"
                                }
                            )

                        # All fields are ArrayFields in QuestionSet model
                        # Store the actual values (codes/names) not IDs
                        row[field] = values
                    else:
                        # No values after filtering, set to empty list
                        row[field] = []
                else:
                    # Empty string, set to empty list
                    row[field] = []
            else:
                # None value, set to empty list
                row[field] = []

    def unique_record_check(self, row):
        """
        Check that no duplicate QuestionSet record exists.

        Uniqueness constraint: (qsetname, type, client, parent, bu)
        """
        # unique record check
        if (
            QuestionSet.objects.select_related()
            .filter(
                qsetname=row["Question Set Name*"],
                type=row["QuestionSet Type*"],
                client__bucode=row["Client*"],
                parent__qsetname=row["Belongs To*"],
                bu__bucode=row["Site*"],
            )
            .exists()
        ):
            raise ValidationError(
                f"Record with these values already exist {row.values()}"
            )

    def before_save_instance(self, instance, row, **kwargs):
        """
        Apply instance-level defaults before saving.

        - Set tenant_id to 1 if not set
        - Apply common stuff (cuser, muser, timestamps)
        """
        # Set tenant_id to 1 as default if not already set
        if not hasattr(instance, 'tenant_id') or instance.tenant_id is None:
            instance.tenant_id = 1

        utils.save_common_stuff(self.request, instance, self.is_superuser)
