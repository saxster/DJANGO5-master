from typing import List, Tuple, Dict, Any
from django.db.models import Q
from .base_extractor import BaseDataExtractor


class QuestionSetExtractor(BaseDataExtractor):
    def extract(self, session_data: Dict[str, Any]) -> List[Tuple]:
        from apps.activity.models import QuestionSet
        from apps.activity.models.asset_model import Asset
        import apps.onboarding.models as ob
        import apps.peoples.models as pm

        self._validate_session_data(session_data)
        site_ids = self._get_site_ids(session_data)

        objs = QuestionSet.objects.filter(
            Q(type="RPCHECKLIST") & Q(bu_id__in=session_data["assignedsites"])
            | (
                Q(parent_id=1) & ~Q(qsetname="NONE") &
                Q(bu_id__in=site_ids) & Q(client_id=session_data["client_id"])
            )
        ).select_related("parent").values(
            "id", "seqno", "qsetname", "parent__qsetname", "type",
            "assetincludes", "buincludes", "bu__bucode", "client__bucode",
            "site_grp_includes", "site_type_includes", "show_to_all_sites", "url",
        )

        objs_list = list(objs)
        asset_ids = {str(aid) for obj in objs_list if obj["assetincludes"] for aid in obj["assetincludes"] if str(aid).isdigit()}
        bu_ids = {str(bid) for obj in objs_list if obj["buincludes"] for bid in obj["buincludes"] if str(bid).isdigit()}
        site_group_ids = {str(gid) for obj in objs_list if obj["site_grp_includes"] for gid in obj["site_grp_includes"] if str(gid).isdigit()}
        site_type_ids = {str(tid) for obj in objs_list if obj["site_type_includes"] for tid in obj["site_type_includes"] if str(tid).isdigit()}

        asset_code_map = {str(aid): code for aid, code in Asset.objects.filter(id__in=asset_ids).values_list("id", "assetcode")}
        bu_code_map = {str(bid): code for bid, code in ob.Bt.objects.filter(id__in=bu_ids).values_list("id", "bucode")}
        site_group_map = {str(gid): name for gid, name in pm.Pgroup.objects.filter(id__in=site_group_ids).values_list("id", "groupname")}
        site_type_map = {str(tid): name for tid, name in ob.TypeAssist.objects.filter(id__in=site_type_ids).values_list("id", "taname")}

        for obj in objs_list:
            obj["assetincludes"] = ",".join(asset_code_map.get(str(aid), "") for aid in obj["assetincludes"] or [] if str(aid) in asset_code_map) or ""
            obj["buincludes"] = ",".join(bu_code_map.get(str(bid), "") for bid in obj["buincludes"] or [] if str(bid) in bu_code_map) or ""
            obj["site_grp_includes"] = ",".join(site_group_map.get(str(gid), "") for gid in obj["site_grp_includes"] or [] if str(gid) in site_group_map) or ""
            obj["site_type_includes"] = ",".join(site_type_map.get(str(tid), "") for tid in obj["site_type_includes"] or [] if str(tid) in site_type_map) or ""

        fields = ["id", "seqno", "qsetname", "parent__qsetname", "type", "assetincludes", "buincludes", "bu__bucode", "client__bucode", "site_grp_includes", "site_type_includes", "show_to_all_sites", "url"]
        return [tuple(obj[field] for field in fields) for obj in objs_list]


__all__ = ['QuestionSetExtractor']