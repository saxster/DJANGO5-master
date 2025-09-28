from import_export import resources
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from apps.core import utils


class UserFriendlyResource(resources.ModelResource):
    """
    Base Resource class that provides user-friendly error messages for all imports.
    All Resource classes should inherit from this instead of resources.ModelResource.
    """
    
    def __init__(self, *args, **kwargs):
        self.is_superuser = kwargs.pop('is_superuser', None)
        self.request = kwargs.pop('request', None)
        self.ctzoffset = kwargs.pop('ctzoffset', -1)
        super().__init__(*args, **kwargs)
    
    def format_error_message(self, error, row=None, field=None):
        """Convert technical errors to user-friendly messages"""
        error_str = str(error)
        
        # Handle KeyError for missing fields
        if isinstance(error, KeyError):
            field_name = str(error).strip("'")
            return f"Missing required field: {field_name}. Please ensure this column exists in your import file."
        
        # Handle multiple results error
        if "get() returned more than one" in error_str:
            import re
            # Try to extract the model name and count
            model_match = re.search(r'(\w+)\.objects\.get\(\)', error_str) or re.search(r'(\w+) matching', error_str)
            count_match = re.search(r'returned (\d+)', error_str)
            
            model_name = model_match.group(1) if model_match else "records"
            count = count_match.group(1) if count_match else "multiple"
            
            if "Job" in error_str:
                belongs_to = row.get('Belongs To*', 'Unknown') if row else 'Unknown'
                return (f"Multiple tours found with name '{belongs_to}'. "
                       f"Found {count} tours with this name in the specified client and site. "
                       f"Please ensure tour names are unique within each site.")
            elif "TypeAssist" in error_str:
                # Debug info for TypeAssist issues
                debug_info = ""
                if row:
                    debug_info = f"\nLikely issue with: Employee Type='{row.get('Employee Type*', 'N/A')}', Work Type='{row.get('Work Type', 'N/A')}', Department='{row.get('Department', 'N/A')}', or Designation='{row.get('Designation', 'N/A')}'"
                return (f"Multiple TypeAssist records found. Found {count} matching records. "
                       f"This usually means there are duplicate TypeAssist entries in the database.{debug_info}")
            else:
                # Generic message with debug info
                debug_info = ""
                if row:
                    # Show first few values from the row for context
                    row_values = list(row.values())[:5]
                    debug_info = f"\nRow starts with: {row_values}"
                return f"Multiple {model_name} found. Found {count} matching records. Please ensure your data is unique.{debug_info}"
        
        # Handle specific error types
        if "DoesNotExist" in error_str or "matching query does not exist" in error_str:
            if "Bt matching query does not exist" in error_str:
                return f"Site or Client not found. Please ensure they exist in the system."
            elif "Asset matching query does not exist" in error_str:
                asset_name = row.get('Asset/Checkpoint*', row.get('Asset*', 'Unknown')) if row else 'Unknown'
                client_name = row.get('Client*', 'Unknown') if row else 'Unknown'
                return f"Asset '{asset_name}' not found. Please ensure it exists and is enabled for client '{client_name}'."
            elif "QuestionSet matching query does not exist" in error_str:
                qset_name = row.get('Question Set*', 'Unknown') if row else 'Unknown'
                client_name = row.get('Client*', 'Unknown') if row else 'Unknown'
                return f"Question Set '{qset_name}' not found. Please ensure it exists and is enabled for client '{client_name}'."
            elif "Job matching query does not exist" in error_str:
                belongs_to = row.get('Belongs To*', 'Unknown') if row else 'Unknown'
                return f"Parent tour '{belongs_to}' not found. Please ensure the tour exists with this exact name in the specified client and site."
            elif "People matching query does not exist" in error_str:
                people_name = row.get('People*', row.get('Person*', 'Unknown')) if row else 'Unknown'
                return f"Person '{people_name}' not found. Please ensure they exist in the system."
            elif "TypeAssist matching query does not exist" in error_str:
                # Try to identify which field caused the error
                if row:
                    # Check for common TypeAssist fields
                    type_fields = {
                        'Employee Type*': 'Employee Type',
                        'Work Type': 'Work Type',
                        'Department': 'Department',
                        'Designation': 'Designation'
                    }
                    for field_name, display_name in type_fields.items():
                        if field_name in row and row[field_name]:
                            return (f"{display_name} '{row[field_name]}' not found. "
                                   f"Please ensure this {display_name.lower()} exists in the system "
                                   f"for client '{row.get('Client*', 'Unknown')}'.")
                return f"User Defined Type not found. Please ensure the type exists in the system."
            else:
                return "Referenced record not found. Please check your data."
        
        elif "IntegrityError" in error_str:
            if "duplicate key value violates unique constraint" in error_str:
                # Extract details about the duplicate
                if "jobname_asset_qset_id_parent_identifier_client_uk" in error_str:
                    asset_name = row.get('Asset/Checkpoint*', 'Unknown') if row else 'Unknown'
                    qset_name = row.get('Question Set*', 'Unknown') if row else 'Unknown'
                    belongs_to = row.get('Belongs To*', 'Unknown') if row else 'Unknown'
                    return (f"This checkpoint already exists. A checkpoint with Asset/Checkpoint '{asset_name}', "
                           f"Question Set '{qset_name}' already exists for tour '{belongs_to}'. "
                           f"Each combination of Asset/Checkpoint and Question Set must be unique within a tour.")
                elif "unique constraint" in error_str:
                    return "This record already exists. Please ensure your data is unique."
                else:
                    return "This record already exists. Please ensure each record is unique."
            else:
                return "Data integrity error. This record may already exist or there's a data conflict."
        
        elif "ValueError" in error_str:
            if "must be a valid integer" in error_str:
                return "Invalid number format. Please ensure numeric fields contain valid numbers."
            elif "invalid literal for int()" in error_str:
                return "Invalid number format. Please check your numeric values."
            # Handle widget clean errors (improved error messages from our widgets)
            elif "not found" in error_str and "Please ensure" in error_str:
                return error_str  # Our custom widget error messages are already user-friendly
            return f"Invalid value format: {error_str}"
        
        elif "ValidationError" in error_str:
            return error_str  # ValidationErrors are already user-friendly
        
        elif "Permission denied" in error_str or "not allowed" in error_str:
            return "Permission denied. You don't have permission to perform this operation."
        
        else:
            return f"Error: {error_str}"
    
    def import_data(self, dataset, dry_run=False, raise_errors=False, use_transactions=None, collect_failed_rows=False, **kwargs):
        """Override to catch any remaining errors"""
        try:
            return super().import_data(dataset, dry_run, raise_errors, use_transactions, collect_failed_rows, **kwargs)
        except (TypeError, ValidationError, ValueError) as e:
            # Format any uncaught errors
            friendly_message = self.format_error_message(e)
            raise type(e)(friendly_message) from e

    def import_field(self, field, obj, data, is_m2m=False, **kwargs):
        """Override to catch field validation errors"""
        try:
            return super().import_field(field, obj, data, is_m2m, **kwargs)
        except (TypeError, ValidationError, ValueError) as e:
            # Format the error message with field context
            friendly_message = self.format_error_message(e, data, field.column_name)
            # Re-raise with the friendly message
            raise type(e)(friendly_message) from e
    
    def import_row(self, row, instance_loader, **kwargs):
        """Override to provide user-friendly error messages"""
        try:
            return super().import_row(row, instance_loader, **kwargs)
        except (TypeError, ValidationError, ValueError) as e:
            # Format the error message
            friendly_message = self.format_error_message(e, row)
            # Add row number if available
            row_number = kwargs.get('row_number', None)
            if row_number:
                friendly_message = f"Row {row_number}: {friendly_message}"
            # Re-raise with the friendly message
            raise type(e)(friendly_message) from e
    
    def save_instance(self, instance, *args, **kwargs):
        """Override to catch IntegrityError during save"""
        try:
            super().save_instance(instance, *args, **kwargs)
        except IntegrityError as e:
            error_str = str(e)
            if "duplicate key value violates unique constraint" in error_str:
                if "jobname_asset_qset_id_parent_identifier_client_uk" in error_str:
                    asset_name = instance.asset.assetname if hasattr(instance, 'asset') and instance.asset else 'Unknown'
                    qset_name = instance.qset.qsetname if hasattr(instance, 'qset') and instance.qset else 'Unknown'
                    tour_name = instance.jobname if hasattr(instance, 'jobname') and instance.jobname else 'Unknown'
                    raise ValidationError(
                        f"This checkpoint already exists. A checkpoint with Asset/Checkpoint '{asset_name}', "
                        f"Question Set '{qset_name}' already exists for tour '{tour_name}'. "
                        f"Each combination of Asset/Checkpoint and Question Set must be unique within a tour."
                    )
                else:
                    raise ValidationError(
                        "This record already exists. Please ensure each record is unique."
                    )
            else:
                raise ValidationError(f"Data integrity error: {error_str}")
    
    def before_save_instance(self, instance, using_transactions=True, dry_run=False):
        """Override to add common save functionality"""
        if hasattr(self, 'request') and self.request:
            utils.save_common_stuff(self.request, instance, self.is_superuser, getattr(self, 'ctzoffset', -1))
        super().before_save_instance(instance, using_transactions, dry_run)