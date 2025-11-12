"""
Import Instructions and Data Model Classes

Provides instructions for bulk import operations and field mapping
for job scheduling and data ingestion.
"""

import logging

logger = logging.getLogger("django")


class JobFields:
    """Field list for Job model exports and imports."""
    fields = [
        "id",
        "jobname",
        "jobdesc",
        "geofence_id",
        "cron",
        "expirytime",
        "identifier",
        "cuser_id",
        "muser_id",
        "bu_id",
        "client_id",
        "sgroup__groupname",
        "pgroup_id",
        "sgroup_id",
        "ticketcategory_id",
        "frequency",
        "starttime",
        "endtime",
        "seqno",
        "ctzoffset",
        "people_id",
        "asset_id",
        "parent_id",
        "scantype",
        "planduration",
        "fromdate",
        "uptodate",
        "priority",
        "lastgeneratedon",
        "qset_id",
        "qset__qsetname",
        "asset__assetname",
        "other_info",
        "gracetime",
        "cdtz",
        "mdtz",
    ]


class Instructions(object):
    """
    Generates import/export instructions for bulk data operations.

    Provides column names, valid choices, format specifications, and
    step-by-step instructions for bulk importing various data types.
    """

    def __init__(self, tablename):
        from apps.core.data.excel_templates import HEADER_MAPPING, HEADER_MAPPING_UPDATE
        from apps.client_onboarding.views import MODEL_RESOURCE_MAP

        if tablename is None:
            raise ValueError("The tablename argument is required")
        self.tablename = tablename
        self.model_source_map = MODEL_RESOURCE_MAP
        self.header_mapping = HEADER_MAPPING
        self.header_mapping_update = HEADER_MAPPING_UPDATE

    def field_choices_map(self, choice_field):
        """Get valid choices for a specific field."""
        from django.apps import apps

        Question = apps.get_model("activity", "Question")
        Asset = apps.get_model("activity", "Asset")
        Location = apps.get_model("activity", "Location")
        QuestionSet = apps.get_model("activity", "QuestionSet")
        return {
            "Answer Type*": [choice[0] for choice in Question.AnswerType.choices],
            "AVPT Type": [choice[0] for choice in Question.AvptType.choices],
            "Identifier*": [choice[0] for choice in Asset.Identifier.choices],
            "Running Status*": [choice[0] for choice in Asset.RunningStatus.choices],
            "Status*": [choice[0] for choice in Location.LocationStatus.choices],
            "Type*": ["SITEGROUP", "PEOPLEGROUP"],
            "QuestionSet Type*": [choice[0] for choice in QuestionSet.Type.choices],
        }.get(choice_field)

    def get_insructions(self):
        """Get import instructions for the table."""
        if self.tablename != "BULKIMPORTIMAGE":
            general_instructions = self.get_general_instructions()
            custom_instructions = self.get_custom_instructions()
            column_names = self.get_column_names()
            valid_choices = self.get_valid_choices_if_any()
            format_info = self.get_valid_format_info()
            return {
                "general_instructions": general_instructions + custom_instructions
                if custom_instructions
                else general_instructions,
                "column_names": "Columns: ${}&".format(", ".join(column_names)),
                "valid_choices": valid_choices,
                "format_info": format_info,
            }
        else:
            bulk_import_image_instructions = self.get_bulk_import_image_instructions()
            return {"general_instructions": bulk_import_image_instructions}

    def get_insructions_update_info(self):
        """Get instructions for update imports."""
        if self.tablename != "BULKIMPORTIMAGE":
            general_instructions = self.get_instruction_update()
            return {
                "general_instructions": general_instructions,
            }

    def get_instruction_update(self):
        """Get step-by-step update instructions."""
        return [
            "Download the Import Update Sheet:",
            [
                'On clicking the "Bulk Import Update" section of the application, navigate to the field titled - "Select Type of Data."',
                'Download the Excel sheet for the specific table you want to update after the appropriate selection (e.g., "People", "Business Unit", etc.), by clicking on the Download button.',
                "This sheet will contain all records from the selected table.",
                'The first column, titled "ID*", contains the primary key for each record. Do not modify this column as it is used to match records in the database.',
            ],
            "Identify Records that Need Updates:",
            [
                "Review the downloaded sheet and determine which records require updates (e.g., adding missing data, altering incorrect information or changed value for the same data, or deleting existing data in specific fields (cells)).",
                "Only focus on the records that require changes. If a record does not require any updates, you must remove it from the sheet (see Step 5).",
            ],
            "Make the Required Changes to Records (For the records that require updates, make the following changes as needed):",
            [
                "Add Missing Data: Locate the fields (cells) that are currently blank or incomplete and fill them with the necessary information.",
                "Alter Existing Data: If any field (cell) contains incorrect or outdated information, modify the data by replacing it with the correct information.",
                'Delete Existing Data: If you want to delete data from a particular field (cell), simply leave the cell empty. Leaving a cell blank signals the system to delete the existing data in that field for the specific record. This is only for multi select type value fields(cells) such as mobile capability in "People". Or else use the disable function present in the adjacent cell for tables that download a disable column. Eg. Group Belongings',
            ],
            "Important Notes:",
            [
                "Do not make any changes to fields (cells) that do not require an update.",
                "This ensures that only the required fields (cells) are altered while leaving the existing data intact.",
                'Do not modify the "ID*" field (first column), as it is critical for identifying the correct record for updating.',
            ],
            "Remove Records that Do Not Need Updates:",
            [
                "If a record does not require any updates, delete the entire row from the Excel sheet.",
                "For example, if your downloaded sheet contains 100 records and you only want to update 10 of them, remove the other 90 records.",
                "This helps avoid unnecessary processing of unchanged records during the update process.",
            ],
            "Final Review Before Uploading:",
            [
                "Ensure that only the records requiring updates remain in the sheet.",
                "Double-check that all changes made are accurate and that fields (cells) not requiring updates remain unaltered.",
            ],
            "Save the Updated Sheet:",
            [
                "After making the necessary changes, save the Excel sheet in a compatible format (.xlsx)."
            ],
            "Upload the Sheet:",
            [
                "Go back to the application and upload the modified sheet to complete the import update process.",
                "The system will process the updates and reflect the changes in the database for the affected records only.",
            ],
        ]

    def get_bulk_import_image_instructions(self):
        """Get instructions for bulk image imports."""
        return [
            "Share the Google Drive link that contains all the images of people.",
            "Ensure the image name matches the people code.",
            "Uploaded images should be in JPEG or PNG format.",
            "Image size should be less than 300KB.",
        ]

    def get_general_instructions(self):
        """Get general instructions common to all imports."""
        return [
            "Make sure you correctly selected the type of data that you wanna import in bulk. before clicking 'download'",
            "Make sure while filling data in file, your column header does not contain value other than columns mentioned below.",
            "The column names marker asterisk (*) are mandatory to fill",
        ]

    def get_custom_instructions(self):
        """Get table-specific custom instructions."""
        return {
            "SCHEDULEDTOURS": [
                "Make sure you insert the tour details first then you insert its checkpoints.",
                "The Primary data of a checkpoint consist of Seq No, Asset, Question Set/Checklist, Expiry Time",
                "Once you entered the primary data of a checkpoint, for other columns you can copy it from tour details you have just entered",
                "This way repeat the above 3 steps for other tour details and its checkpoints",
            ],
            "TOURSCHECKPOINTS": [
                "Tour Checkpoints must be imported AFTER their parent tours are created.",
                "The 'Belongs To*' field must reference an existing, enabled tour name.",
                "Checkpoints inherit scheduling from their parent tour automatically.",
                "Sequence numbers must be positive integers and should be unique within each tour.",
                "Each checkpoint requires its own Asset/Checkpoint and Question Set.",
                "Expiry Time is in minutes - the time allowed to complete the checkpoint.",
            ]
        }.get(self.tablename)

    def get_column_names(self):
        """Get column names for the table."""
        return self.header_mapping.get(self.tablename)

    def get_column_names_update(self):
        """Get column names for update imports."""
        return self.header_mapping_update.get(self.tablename)

    def get_valid_choices_if_any(self):
        """Get valid choice values for choice fields."""
        table_choice_field_map = {
            "QUESTION": ["Answer Type*", "AVPT Type"],
            "QUESTIONSET": ["QuestionSet Type*"],
            "ASSET": ["Identifier*", "Running Status*"],
            "GROUP": ["Type*"],
            "LOCATION": ["Status*"],
        }
        if self.tablename in table_choice_field_map:
            valid_choices = []
            for choice_field in table_choice_field_map.get(self.tablename):
                instruction_str = f'Valid values for column: {choice_field} ${", ".join(self.field_choices_map(choice_field))}&'
                valid_choices.append(instruction_str)
            return valid_choices
        return []

    def get_valid_format_info(self):
        """Get format specifications for data fields."""
        return [
            "Valid Date Format: $YYYY-MM-DD, Example Date Format: 1998-06-22&",
            "Valid Mobile No Format: $[ country code ][ rest of number ] For example: 910123456789&",
            "Valid Time Format: $HH:MM:SS, Example Time Format: 23:55:00&",
            "Valid Date Time Format: $YYYY-MM-DD HH:MM:SS, Example DateTime Format: 1998-06-22 23:55:00&",
        ]


__all__ = [
    'JobFields',
    'Instructions',
]
