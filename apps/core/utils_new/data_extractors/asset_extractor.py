from typing import List, Tuple, Dict, Any
from django.db.models import Q, F, CharField
from django.db.models.functions import Cast
from .base_extractor import BaseDataExtractor
from apps.core.utils_new.gps_utils import add_gps_coordinates_annotation

class AssetExtractor(BaseDataExtractor):
    def extract(self, session_data: Dict[str, Any]) -> List[Tuple]:
        from apps.activity.models.asset_model import Asset

        self._validate_session_data(session_data)
        site_ids = self._get_site_ids(session_data)

        objs = Asset.objects.select_related(
            "parent", "type", "bu", "category",
            "subcategory", "brand", "unit", "servprov"
        ).filter(
            ~Q(assetcode="NONE"),
            bu_id__in=site_ids,
            client_id=session_data["client_id"],
            identifier="ASSET",
        )

        objs = add_gps_coordinates_annotation(objs, 'gpslocation')

        objs = objs.annotate(
            ismeter=F("asset_json__ismeter"),
            isnonenggasset=F("asset_json__is_nonengg_asset"),
            meter=F("asset_json__meter"), model=F("asset_json__model"),
            supplier=F("asset_json__supplier"), invoice_no=F("asset_json__invoice_no"),
            invoice_date=F("asset_json__invoice_date"), service=F("asset_json__service"),
            sfdate=F("asset_json__sfdate"), stdate=F("asset_json__stdate"),
            yom=F("asset_json__yom"), msn=F("asset_json__msn"),
            bill_val=F("asset_json__bill_val"), bill_date=F("asset_json__bill_date"),
            purchase_date=F("asset_json__purchase_date"), inst_date=F("asset_json__inst_date"),
            po_number=F("asset_json__po_number"), far_asset_id=F("asset_json__far_asset_id"),
            capacity_val=Cast("capacity", output_field=CharField()),
        ).values_list(
            "id", "assetcode", "assetname", "runningstatus", "identifier",
            "iscritical", "client__bucode", "bu__bucode", "capacity_val",
            "parent__assetcode", "type__tacode", "coordinates",
            "category__tacode", "subcategory__tacode", "brand__tacode",
            "unit__tacode", "servprov__bucode", "enable", "ismeter",
            "isnonenggasset", "meter", "model", "supplier", "invoice_no",
            "invoice_date", "service", "sfdate", "stdate", "yom", "msn",
            "bill_val", "bill_date", "purchase_date", "inst_date",
            "po_number", "far_asset_id",
        )
        return list(objs)

__all__ = ['AssetExtractor']