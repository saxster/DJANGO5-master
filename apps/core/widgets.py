from import_export import widgets as wg
from django.db.models import Q
from apps.onboarding import models as om
from apps.activity import models as am
from apps.peoples import models as pm
from django.core.exceptions import ValidationError


class TypeAssistEmployeeTypeFKW(wg.ForeignKeyWidget):
    def get_queryset(self, value, row, *args, **kwargs):
        return self.model.objects.select_related().filter(
            Q(client__bucode__exact=row["Client*"]),
            Q(tatype__tacode__exact="PEOPLETYPE") | Q(tatype__tacode__exact="NONE"),
        )


class TypeAssistWorkTypeFKW(wg.ForeignKeyWidget):
    def get_queryset(self, value, row, *args, **kwargs):
        return self.model.objects.select_related().filter(
            Q(client__bucode__exact=row["Client*"]), tatype__tacode__exact="WORKTYPE"
        )


class TypeAssistDepartmentFKW(wg.ForeignKeyWidget):
    def get_queryset(self, value, row, *args, **kwargs):
        return self.model.objects.select_related().filter(
            Q(client__bucode__exact=row["Client*"]), tatype__tacode__exact="DEPARTMENT"
        )


class TypeAssistDesignationFKW(wg.ForeignKeyWidget):
    def get_queryset(self, value, row, *args, **kwargs):
        return self.model.objects.select_related().filter(
            Q(client__bucode__exact=row["Client*"]), tatype__tacode__exact="DESIGNATION"
        )


class BVForeignKeyWidget(wg.ForeignKeyWidget):
    def get_queryset(self, value, row, *args, **kwargs):
        client = om.Bt.objects.filter(bucode=row["Client*"]).first()
        bu_ids = om.Bt.objects.get_whole_tree(client.id)
        qset = self.model.objects.select_related("parent", "identifier").filter(
            id__in=bu_ids, identifier__tacode="SITE", parent__bucode=row["Client*"]
        )
        return qset


class TypeAssistEmployeeTypeFKWUpdate(wg.ForeignKeyWidget):
    def get_queryset(self, value, row, *args, **kwargs):
        if "Client" in row and "Employee Type" in row:
            return self.model.objects.select_related().filter(
                Q(client__bucode__exact=row["Client"])
                & (
                    Q(tatype__tacode__exact="PEOPLETYPE")
                    | Q(tatype__tacode__exact="NONE")
                )
                & (Q(tacode__exact=row["Employee Type"]) | Q(tacode__exact="NONE"))
            )
        return self.model.objects.none()


class TypeAssistWorkTypeFKWUpdate(wg.ForeignKeyWidget):
    def get_queryset(self, value, row, *args, **kwargs):
        if "Client" in row and "Work Type" in row:
            return self.model.objects.select_related().filter(
                Q(client__bucode__exact=row["Client"])
                & (
                    Q(tatype__tacode__exact="WORKTYPE")
                    | Q(tatype__tacode__exact="NONE")
                )
                & (Q(tacode__exact=row["Work Type"]) | Q(tacode__exact="NONE"))
            )
        return self.model.objects.none()


class TypeAssistDepartmentFKWUpdate(wg.ForeignKeyWidget):
    def get_queryset(self, value, row, *args, **kwargs):
        if "Client" in row:
            return self.model.objects.select_related().filter(
                Q(client__bucode__exact=row["Client"]),
                Q(tatype__tacode__exact="DEPARTMENT") | Q(tatype__tacode__exact="NONE"),
            )
        return self.model.objects.none()


class TypeAssistDesignationFKWUpdate(wg.ForeignKeyWidget):
    def get_queryset(self, value, row, *args, **kwargs):
        if "Client" in row:
            return self.model.objects.select_related().filter(
                Q(client__bucode__exact=row["Client"]),
                Q(tatype__tacode__exact="DESIGNATION")
                | Q(tatype__tacode__exact="NONE"),
            )
        return self.model.objects.none()


class BVForeignKeyWidgetUpdate(wg.ForeignKeyWidget):
    def get_queryset(self, value, row, *args, **kwargs):
        if "Client" in row:
            client = om.Bt.objects.filter(bucode=row["Client"]).first()
            bu_ids = om.Bt.objects.get_whole_tree(client.id)
            qset = self.model.objects.select_related("parent", "identifier").filter(
                id__in=bu_ids, identifier__tacode="SITE", parent__bucode=row["Client"]
            )
            return qset
        return self.model.objects.none()


class QsetFKWUpdate(wg.ForeignKeyWidget):
    def get_queryset(self, value, row, *args, **kwargs):
        if "Client" in row:
            return am.QuestionSet.objects.select_related().filter(
                Q(qsetname="NONE") | (Q(client__bucode=row["Client"]) & Q(enable=True))
            )
        return self.model.objects.none()


class TktCategoryFKWUpdate(wg.ForeignKeyWidget):
    def get_queryset(self, value, row, *args, **kwargs):
        return om.TypeAssist.objects.select_related().filter(
            tatype__tacode="NOTIFYCATEGORY"
        )


class AssetFKWUpdate(wg.ForeignKeyWidget):
    def get_queryset(self, value, row, *args, **kwargs):
        if "Client" in row:
            return am.Asset.objects.select_related().filter(
                Q(assetname="NONE") | (Q(client__bucode=row["Client"]) & Q(enable=True))
            )
        return self.model.objects.none()


class PeopleFKWUpdate(wg.ForeignKeyWidget):
    def get_queryset(self, value, row, *args, **kwargs):
        if "Client" in row:
            return pm.People.objects.select_related().filter(
                (Q(client__bucode=row["Client"]) & Q(enable=True))
                | Q(peoplename="NONE")
            )
        return self.model.objects.none()


class PgroupFKWUpdate(wg.ForeignKeyWidget):
    def get_queryset(self, value, row, *args, **kwargs):
        if "Client" in row:
            return pm.Pgroup.objects.select_related().filter(
                (Q(client__bucode=row["Client"]) & Q(enable=True)) | Q(groupname="NONE")
            )
        return self.model.objects.none()


class EnabledTypeAssistWidget(wg.ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return None
        queryset = self.get_queryset(value, row, *args, **kwargs)
        try:
            return queryset.filter(enable=True, **{self.field: value}).get()
        except self.model.DoesNotExist:
            raise ValidationError(f"No enabled TypeAssist found with code {value}")
        except self.model.MultipleObjectsReturned:
            # In case of multiple enabled TypeAssists, return the first one
            return queryset.filter(enable=True, **{self.field: value}).first()


class ClientAwareTypeAssistWidget(wg.ForeignKeyWidget):
    """
    TypeAssist widget that filters by client with the following logic:
    - Accepts TypeAssist where enable=True
    - Accepts TypeAssist where client_id equals:
      - The client_id from the import row
      - 1 (global/default client)
      - NULL (available to all clients)
    """
    def get_queryset(self, value, row, *args, **kwargs):
        from django.db.models import Q
        
        # Get client from the import row
        client_code = row.get("Client*", "NONE")
        
        # Get the actual client object and ID
        client = om.Bt.objects.filter(bucode=client_code).first()
        client_id = client.id if client else 1
        
        # Filter: client_id matches row client OR 1 OR NULL
        # AND must be enabled
        return self.model.objects.filter(
            Q(client_id=client_id) | Q(client_id=1) | Q(client_id__isnull=True),
            enable=True
        )
    
    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return None
        
        queryset = self.get_queryset(value, row, *args, **kwargs)
        try:
            # Filter by the tacode value
            return queryset.filter(**{self.field: value}).get()
        except self.model.DoesNotExist:
            
            # Provide helpful error message
            client_code = row.get("Client*", "NONE") if row else "NONE"
            raise ValidationError(
                f"No enabled TypeAssist found with code '{value}' for client '{client_code}' "
                f"(also checked global client and NULL client)"
            )
        except self.model.MultipleObjectsReturned:
            # If multiple matches, return the most specific one
            # Priority: exact client match > client_id=1 > client_id=NULL
            client_code = row.get("Client*", "NONE") if row else "NONE"
            client = om.Bt.objects.filter(bucode=client_code).first()
            client_id = client.id if client else 1
            
            # Try exact client match first
            exact_match = queryset.filter(client_id=client_id, **{self.field: value}).first()
            if exact_match:
                return exact_match
            
            # Then try global client
            global_match = queryset.filter(client_id=1, **{self.field: value}).first()
            if global_match:
                return global_match
            
            # Finally return NULL client match
            return queryset.filter(client_id__isnull=True, **{self.field: value}).first()
