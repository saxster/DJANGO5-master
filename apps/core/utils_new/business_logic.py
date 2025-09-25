import logging

logger = logging.getLogger("django")
import apps.peoples.utils as putils
from apps.work_order_management.models import Approver
from django.conf import settings
import django.shortcuts as scts
import apps.onboarding.models as ob
from apps.peoples import models as pm
from django.contrib import messages as msg
from pprint import pformat
from apps.core.utils_new.http_utils import handle_DoesNotExist

error_logger = logging.getLogger("error_logger")
debug_logger = logging.getLogger("debug_logger")


class JobFields:
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
    # constructor for the class
    def __init__(self, tablename):
        from apps.core.utils_new.file_utils import HEADER_MAPPING, HEADER_MAPPING_UPDATE

        """Imported MODEL_RESOURCE_MAP(which is a dictionary containing model and resource mapping(used to validate import data))
        and HEADER_MAPPING(which is a dictionary containing tablename and column names mapping)"""
        from apps.onboarding.views import MODEL_RESOURCE_MAP

        # Check if tablename is provided initializing the class
        if tablename is None:
            raise ValueError("The tablename argument is required")
        self.tablename = tablename
        self.model_source_map = MODEL_RESOURCE_MAP
        self.header_mapping = HEADER_MAPPING
        self.header_mapping_update = HEADER_MAPPING_UPDATE

    # Helper function for get_valid_choices_if_any() which returns the valid choices for the given choice field
    def field_choices_map(self, choice_field):
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

    # function is for getting the instructions for the given tablename
    def get_insructions(self):
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
        if self.tablename != "BULKIMPORTIMAGE":
            general_instructions = self.get_instruction_update()
            return {
                "general_instructions": general_instructions,
            }

    def get_instruction_update(self):
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
        """
        This functions return instrucitons for bulk import of people image
        Args:
            None
        Return:
            array: This is array of inistructions for bulk import of Image
        """
        return [
            "Share the Google Drive link that contains all the images of people.",
            "Ensure the image name matches the people code.",
            "Uploaded images should be in JPEG or PNG format.",
            "Image size should be less than 300KB.",
        ]

    # list returning general instructions which is common for all the tables
    def get_general_instructions(self):
        return [
            "Make sure you correctly selected the type of data that you wanna import in bulk. before clicking 'download'",
            "Make sure while filling data in file, your column header does not contain value other than columns mentioned below.",
            "The column names marker asterisk (*) are mandatory to fill",
        ]

    # list returning custom instructions for the given tablename
    def get_custom_instructions(self):
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

    # list returning column names for the given tablename
    def get_column_names(self):
        return self.header_mapping.get(self.tablename)

    def get_column_names_update(self):
        return self.header_mapping_update.get(self.tablename)

    # list returning valid choices for the given tablename
    def get_valid_choices_if_any(self):
        table_choice_field_map = {
            "QUESTION": ["Answer Type*", "AVPT Type"],
            "QUESTIONSET": ["QuestionSet Type*"],
            "ASSET": ["Identifier*", "Running Status*"],
            "GROUP": ["Type*"],
            "LOCATION": ["Status*"],
        }
        if self.tablename in table_choice_field_map:
            valid_choices = []
            # table_choice_field_map.get(self.tablename) will return the list of choice fields for the given tablename
            for choice_field in table_choice_field_map.get(self.tablename):
                instruction_str = f'Valid values for column: {choice_field} ${", ".join(self.field_choices_map(choice_field))}&'
                valid_choices.append(instruction_str)
            return valid_choices
        return []

    # list returning valid format info for the given tablename
    def get_valid_format_info(self):
        return [
            "Valid Date Format: $YYYY-MM-DD, Example Date Format: 1998-06-22&",
            "Valid Mobile No Format: $[ country code ][ rest of number ] For example: 910123456789&",
            "Valid Time Format: $HH:MM:SS, Example Time Format: 23:55:00&",
            "Valid Date Time Format: $YYYY-MM-DD HH:MM:SS, Example DateTime Format: 1998-06-22 23:55:00&",
        ]


def get_appropriate_client_url(client_code):
    return settings.CLIENT_DOMAINS.get(client_code)


def save_capsinfo_inside_session(people, request, admin):
    logger.info("save_capsinfo_inside_session... STARTED")
    from apps.core.queries import get_query
    from apps.peoples.models import Capability, People

    if admin:
        # extracting the capabilities from client
        web, mob, portlet, report, noc = putils.create_caps_choices_for_peopleform(
            request.user.client
        )
        request.session["client_webcaps"] = list(web)
        request.session["client_mobcaps"] = list(mob)
        request.session["client_portletcaps"] = list(portlet)
        request.session["client_reportcaps"] = list(report)
        request.session["client_noccaps"] = list(noc)
        request.session["people_webcaps"] = []
        request.session["people_mobcaps"] = []
        request.session["people_reportcaps"] = []
        request.session["people_portletcaps"] = []
        request.session["people_noccaps"] = []
    else:
        caps = get_query("get_web_caps_for_client")
        # extracting capabilities from people details
        request.session["client_webcaps"] = []
        request.session["client_mobcaps"] = []
        request.session["client_portletcaps"] = []
        request.session["client_reportcaps"] = []
        request.session["people_webcaps"] = list(
            Capability.objects.filter(
                capscode__in=people.people_extras["webcapability"], cfor="WEB"
            ).values_list("capscode", "capsname")
        )
        request.session["people_mobcaps"] = list(
            Capability.objects.filter(
                capscode__in=people.people_extras["mobilecapability"], cfor="MOB"
            ).values_list("capscode", "capsname")
        )
        request.session["people_reportcaps"] = list(
            Capability.objects.filter(
                capscode__in=people.people_extras["reportcapability"], cfor="REPORT"
            ).values_list("capscode", "capsname")
        )
        request.session["people_portletcaps"] = list(
            Capability.objects.filter(
                capscode__in=people.people_extras["portletcapability"], cfor="PORTLET"
            ).values_list("capscode", "capsname")
        )
        request.session["people_noccaps"] = list(
            Capability.objects.filter(
                capscode__in=people.people_extras.get("noccapability", ""), cfor="NOC"
            ).values_list("capscode", "capsname")
        )
        logger.info("save_capsinfo_inside_session... DONE")


def save_user_session(request, people, ctzoffset=None):
    """save user info in session"""
    from django.conf import settings
    from django.core.exceptions import ObjectDoesNotExist
    from apps.onboarding import models as Bt

    try:
        logger.info("saving user data into the session ... STARTED")
        if ctzoffset:
            request.session["ctzoffset"] = ctzoffset
        if people.is_superuser is True:
            request.session["is_superadmin"] = True
            session = request.session
            session["people_webcaps"] = session["client_webcaps"] = session[
                "people_mobcaps"
            ] = session["people_reportcaps"] = session["people_portletcaps"] = session[
                "client_mobcaps"
            ] = session[
                "client_reportcaps"
            ] = session[
                "client_portletcaps"
            ] = False
            logger.info(request.session["is_superadmin"])
            putils.save_tenant_client_info(request)
        else:
            putils.save_tenant_client_info(request)
            request.session["is_superadmin"] = people.peoplecode == "SUPERADMIN"
            request.session["is_admin"] = people.isadmin
            save_capsinfo_inside_session(people, request, people.isadmin)
            logger.info("saving user data into the session ... DONE")
        request.session["assignedsites"] = list(
            pm.Pgbelonging.objects.get_assigned_sites_to_people(people.id)
        )
        request.session["people_id"] = request.user.id
        request.session["assignedsitegroups"] = people.people_extras["assignsitegroup"]
        request.session["clientcode"] = request.user.client.bucode
        request.session["clientname"] = request.user.client.buname
        request.session["sitename"] = request.user.bu.buname
        request.session["sitecode"] = request.user.bu.bucode
        request.session["google_maps_secret_key"] = settings.GOOGLE_MAP_SECRET_KEY
        request.session["is_workpermit_approver"] = request.user.people_extras[
            "isworkpermit_approver"
        ]
        # Check if the user is an approver
        client_id = request.user.client.id
        site_id = request.user.bu.id
        is_wp_approver = Approver.objects.filter(
            client_id=client_id,
            people=request.user.id,
            approverfor__contains=["WORKPERMIT"],
        ).exists()
        is_sla_approver = Approver.objects.filter(
            client_id=client_id,
            people=request.user.id,
            approverfor__contains=["SLA_TEMPLATE"],
        ).exists()
        request.session["is_wp_approver"] = is_wp_approver
        request.session["is_sla_approver"] = is_sla_approver
    except ObjectDoesNotExist:
        error_logger.error("object not found...", exc_info=True)
        raise
    except Exception:
        logger.critical(
            "something went wrong please follow the traceback to fix it... ",
            exc_info=True,
        )
        raise


def update_timeline_data(ids, request, update=False):
    # sourcery skip: hoist-statement-from-if, remove-pass-body
    steps = {
        "taids": ob.TypeAssist,
        "buids": ob.Bt,
        "shiftids": ob.Shift,
        "peopleids": pm.People,
        "pgroupids": pm.Pgroup,
    }
    fields = {
        "buids": ["id", "bucode", "buname"],
        "taids": ["tacode", "taname", "tatype"],
        "peopleids": ["id", "peoplecode", "loginid"],
        "shiftids": ["id", "shiftname"],
        "pgroupids": ["id", "name"],
    }
    data = (
        steps[ids]
        .objects.filter(pk__in=request.session["wizard_data"][ids])
        .values(*fields[ids])
    )
    if not update:
        request.session["wizard_data"]["timeline_data"][ids] = list(data)
    else:
        request.session["wizard_data"]["timeline_data"][ids].pop()
        request.session["wizard_data"]["timeline_data"][ids] = list(data)


def process_wizard_form(request, wizard_data, update=False, instance=None):
    logger.info(
        "processing wizard started...",
    )
    debug_logger.debug("wizard_Data submitted by the view \n%s", wizard_data)
    wiz_session, resp = request.session["wizard_data"], None
    if not wizard_data["last_form"]:
        logger.info("wizard its NOT last form")
        if not update:
            logger.info("processing wizard not an update form")
            wiz_session[wizard_data["current_ids"]].append(wizard_data["instance_id"])
            request.session["wizard_data"].update(wiz_session)
            update_timeline_data(wizard_data["current_ids"], request, False)
            resp = scts.redirect(wizard_data["current_url"])
        else:
            resp = update_wizard_form(wizard_data, wiz_session, request)
            update_timeline_data(wizard_data["current_ids"], request, True)
    else:
        resp = scts.redirect("onboarding:wizard_view")
    return resp


def update_wizard_form(wizard_data, wiz_session, request):
    # sourcery skip: lift-return-into-if, remove-unnecessary-else
    resp = None
    logger.info("processing wizard is an update form")
    if wizard_data["instance_id"] not in wiz_session[wizard_data["current_ids"]]:
        wiz_session[wizard_data["current_ids"]].append(wizard_data["instance_id"])
    if wiz_session.get(wizard_data["next_ids"]):
        resp = scts.redirect(
            wizard_data["next_update_url"], pk=wiz_session[wizard_data["next_ids"]][-1]
        )
    else:
        request.session["wizard_data"].update(wiz_session)
        resp = scts.redirect(wizard_data["current_url"])
    debug_logger.debug(f"response from update_wizard_form {resp}")
    return resp


def update_prev_step(step_url, request):
    url, ids = step_url
    session = request.session["wizard_data"]
    instance = session.get(ids)[-1] if session.get(ids) else None
    new_url = (
        url.replace("form", "update") if instance and ("update" not in url) else url
    )
    request.session["wizard_data"].update({"prev_inst": instance, "prev_url": new_url})


def update_next_step(step_url, request):
    url, ids = step_url
    session = request.session["wizard_data"]
    instance = session.get(ids)[-1] if session.get(ids) else None
    new_url = (
        url.replace("form", "update") if instance and ("update" not in url) else url
    )
    request.session["wizard_data"].update({"next_inst": instance, "next_url": new_url})


def update_other_info(step, request, current, formid, pk):
    url, ids = step[current]
    session = request.session["wizard_data"]
    session["current_step"] = session["steps"][current]
    session["current_url"] = url
    session["final_url"] = step["final_step"][0]
    session["formid"] = formid
    session["del_url"] = url.replace("form", "delete")
    session["current_inst"] = pk


def update_wizard_steps(request, current, prev, next, formid, pk):
    """Updates wizard next, current, prev, final urls"""
    step_urls = {
        "buform": ("onboarding:wiz_bu_form", "buids"),
        "shiftform": ("onboarding:wiz_shift_form", "shiftids"),
        "peopleform": ("/people/wizard/form/", "peopleids"),
        "pgroupform": ("/people/groups/wizard/form/", "pgroupids"),
        "final_step": ("onboarding:wizard_preview", ""),
    }
    # update prev step
    update_prev_step(step_urls.get(prev, ("", "")), request)
    # update next step
    update_next_step(step_urls.get(next, ("", "")), request)
    # update other info
    update_other_info(step_urls, request, current, formid, pk)


def save_msg(request):
    """Displays a success message"""
    return msg.success(request, "Entry has been saved successfully!", "alert-success")


def initailize_form_fields(form):
    for visible in form.visible_fields():
        if visible.widget_type in [
            "text",
            "textarea",
            "datetime",
            "time",
            "number",
            "date",
            "email",
            "decimal",
        ]:
            visible.field.widget.attrs["class"] = "form-control form-control-solid"
        elif visible.widget_type in ["radio", "checkbox"]:
            visible.field.widget.attrs["class"] = "form-check-input"
        elif visible.widget_type in [
            "select2",
            "select",
            "select2multiple",
            "modelselect2",
            "modelselect2multiple",
        ]:
            visible.field.widget.attrs["class"] = "form-select form-select-solid"
            visible.field.widget.attrs["data-control"] = "select2"
            visible.field.widget.attrs["data-placeholder"] = "Select an option"
            visible.field.widget.attrs["data-allow-clear"] = "true"


def apply_error_classes(form):
    # loop on *all* fields if key '__all__' found else only on errors:
    for x in form.fields if "__all__" in form.errors else form.errors:
        attrs = form.fields[x].widget.attrs
        attrs.update({"class": attrs.get("class", "") + " is-invalid"})


def get_instance_for_update(postdata, params, msg, pk, kwargs=None):
    if kwargs is None:
        kwargs = {}
    logger.info("%s", msg)
    obj = params["model"].objects.get(id=pk)
    logger.info(f"object retrieved '{obj}'")
    return params["form_class"](postdata, instance=obj, **kwargs)


def get_model_obj(pk, request, params):
    try:
        obj = params["model"].objects.get(id=pk)
    except params["model"].DoesNotExist:
        return handle_DoesNotExist(request)
    else:
        logger.info(f"object retrieved '{obj}'")
        return obj


def get_index_for_deletion(lookup, request, ids):
    id = lookup["id"]
    data = request.session["wizard_data"]["timeline_data"][ids]
    for idx, item in enumerate(data):
        if item["id"] == int(id):
            return idx


def delete_object(
    request,
    model,
    lookup,
    ids,
    temp,
    form,
    url,
    form_name,
    jsonformname=None,
    jsonform=None,
):
    """called when individual form request for deletion"""
    from django.db.models import RestrictedError

    try:
        logger.info("Request for object delete...")
        res, obj = None, model.objects.get(**lookup)
        form = form(instance=obj)
        obj.delete()
        msg.success(request, "Entry has been deleted successfully", "alert-success")
        request.session["wizard_data"][ids].remove(int(lookup["id"]))
        request.session["wizard_data"]["timeline_data"][ids].pop(
            get_index_for_deletion(lookup, request, ids)
        )
        logger.info("Object deleted")
        res = scts.redirect(url)
    except model.DoesNotExist:
        error_logger.error("Unable to delete, object does not exist")
        msg.error(request, "Client does not exist", "alert alert-danger")
        res = scts.redirect(url)
    except RestrictedError:
        logger.warning("Unable to delete, duw to dependencies")
        msg.error(request, "Unable to delete, duw to dependencies")
        cxt = {form_name: form, jsonformname: jsonform, "edit": True}
        res = scts.render(request, temp, context=cxt)
    except Exception:
        logger.critical("something went wrong!", exc_info=True)
        msg.error(request, "[ERROR] Something went wrong", "alert alert-danger")
        cxt = {form_name: form, jsonformname: jsonform, "edit": True}
        res = scts.render(request, temp, context=cxt)
    return res


def delete_unsaved_objects(model, ids):
    if ids:
        try:
            logger.info("Found unsaved objects in session going to be deleted...")
            model.objects.filter(pk__in=ids).delete()
        except Exception:
            logger.critical("delete_unsaved_objects failed", exc_info=True)
            raise
        else:
            logger.info("Unsaved objects are deleted...DONE")


def cache_it(key, val, time=1 * 60):
    from django.core.cache import cache

    cache.set(key, val, time)
    logger.info(f"saved in cache {pformat(val)}")


def get_from_cache(key):
    from django.core.cache import cache

    if data := cache.get(key):
        logger.info(f"Got from cache {key}")
        return data
    logger.info("Not found in cache")
    return None
