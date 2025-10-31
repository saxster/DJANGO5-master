"""Serializers for mobile REST sync endpoints."""

from __future__ import annotations

from typing import Any, Dict, List

from rest_framework import serializers

from apps.service.services.mobile_sync import SyncResult


class TicketSyncFilterSerializer(serializers.Serializer):
    """Validate ticket sync query parameters."""

    people_id = serializers.IntegerField()
    bu_id = serializers.IntegerField()
    client_id = serializers.IntegerField()
    mdtz = serializers.DateTimeField()
    ctz_offset = serializers.IntegerField()

    def to_service_kwargs(self) -> Dict[str, Any]:
        data = self.validated_data
        return {
            "people_id": data["people_id"],
            "mdtz": data["mdtz"].isoformat(),
            "ctz_offset": data["ctz_offset"],
            "bu_id": data["bu_id"],
            "client_id": data["client_id"],
        }


class QuestionSyncFilterSerializer(serializers.Serializer):
    """Validate question modified-after filters."""

    mdtz = serializers.DateTimeField()
    ctz_offset = serializers.IntegerField()
    client_id = serializers.IntegerField()

    def to_service_kwargs(self) -> Dict[str, Any]:
        data = self.validated_data
        return {
            "mdtz": data["mdtz"].isoformat(),
            "ctz_offset": data["ctz_offset"],
            "client_id": data["client_id"],
        }


class QuestionSetSyncFilterSerializer(QuestionSyncFilterSerializer):
    """Validate question set modified-after filters."""

    bu_id = serializers.IntegerField()
    people_id = serializers.IntegerField()

    def to_service_kwargs(self) -> Dict[str, Any]:
        data = self.validated_data
        base = super().to_service_kwargs()
        base.update(
            {
                "bu_id": data["bu_id"],
                "people_id": data["people_id"],
            }
        )
        return base


class QuestionSetBelongingFilterSerializer(QuestionSetSyncFilterSerializer):
    """Validate question set belonging filters."""

    include_dependency_logic = serializers.BooleanField(required=False, default=False)

    def to_service_kwargs(self) -> Dict[str, Any]:
        data = self.validated_data
        base = super().to_service_kwargs()
        base["include_dependency_logic"] = data.get("include_dependency_logic", False)
        return base


class QuestionSetLogicParamsSerializer(serializers.Serializer):
    """Validate parameters for retrieving full question set logic."""

    qset_id = serializers.IntegerField()
    client_id = serializers.IntegerField()
    bu_id = serializers.IntegerField()

    def to_service_kwargs(self) -> Dict[str, Any]:
        return dict(self.validated_data)


class JobNeedSyncFilterSerializer(serializers.Serializer):
    """Validate job need modified-after filters."""

    people_id = serializers.IntegerField()
    bu_id = serializers.IntegerField()
    client_id = serializers.IntegerField()

    def to_service_kwargs(self) -> Dict[str, Any]:
        data = self.validated_data
        return {
            "people_id": data["people_id"],
            "bu_id": data["bu_id"],
            "client_id": data["client_id"],
        }


class JobNeedDetailsFilterSerializer(serializers.Serializer):
    """Validate job need details filters."""

    jobneed_ids = serializers.CharField()
    ctz_offset = serializers.IntegerField()

    def to_service_kwargs(self) -> Dict[str, Any]:
        data = self.validated_data
        return {
            "jobneed_ids": data["jobneed_ids"],
            "ctz_offset": data["ctz_offset"],
        }


class ExternalTourSyncFilterSerializer(JobNeedSyncFilterSerializer):
    """Validate external tour job need filters."""


class PeopleModifiedFilterSerializer(serializers.Serializer):
    """Validate people modified-after filters."""

    mdtz = serializers.DateTimeField()
    ctz_offset = serializers.IntegerField()
    bu_id = serializers.IntegerField()

    def to_service_kwargs(self) -> Dict[str, Any]:
        data = self.validated_data
        return {
            "mdtz": data["mdtz"].isoformat(),
            "ctz_offset": data["ctz_offset"],
            "bu_id": data["bu_id"],
        }


class PeopleEventLogPunchInsFilterSerializer(serializers.Serializer):
    """Validate people event log punch-ins filters."""

    date_for = serializers.DateField()
    bu_id = serializers.IntegerField()
    people_id = serializers.IntegerField()

    def to_service_kwargs(self) -> Dict[str, Any]:
        data = self.validated_data
        return {
            "date_for": data["date_for"].isoformat(),
            "bu_id": data["bu_id"],
            "people_id": data["people_id"],
        }


class PgbelongingFilterSerializer(serializers.Serializer):
    """Validate pgbelonging modified-after filters."""

    mdtz = serializers.DateTimeField()
    ctz_offset = serializers.IntegerField()
    bu_id = serializers.IntegerField()
    people_id = serializers.IntegerField()

    def to_service_kwargs(self) -> Dict[str, Any]:
        data = self.validated_data
        return {
            "mdtz": data["mdtz"].isoformat(),
            "ctz_offset": data["ctz_offset"],
            "bu_id": data["bu_id"],
            "people_id": data["people_id"],
        }


class PeopleEventLogHistoryFilterSerializer(serializers.Serializer):
    """Validate people event log history filters."""

    mdtz = serializers.DateTimeField()
    ctz_offset = serializers.IntegerField()
    people_id = serializers.IntegerField()
    bu_id = serializers.IntegerField()
    client_id = serializers.IntegerField()
    pevent_type_ids = serializers.CharField()

    def to_service_kwargs(self) -> Dict[str, Any]:
        data = self.validated_data
        raw_ids = data["pevent_type_ids"]
        if isinstance(raw_ids, str):
            split_ids = [segment.strip() for segment in raw_ids.split(",") if segment.strip()]
            pevent_ids: List[int] = [int(value) for value in split_ids]
        else:
            pevent_ids = list(raw_ids)

        return {
            "mdtz": data["mdtz"].isoformat(),
            "ctz_offset": data["ctz_offset"],
            "people_id": data["people_id"],
            "bu_id": data["bu_id"],
            "client_id": data["client_id"],
            "pevent_type_ids": pevent_ids,
        }


class AttachmentFilterSerializer(serializers.Serializer):
    """Validate attachment lookup filters."""

    owner = serializers.CharField(required=False, allow_blank=True)

    def to_service_kwargs(self) -> Dict[str, Any]:
        return dict(self.validated_data)


class SelectOutputSerializer(serializers.Serializer):
    """Serializer mirroring legacy SelectOutputType fields."""

    nrows = serializers.IntegerField()
    ncols = serializers.IntegerField(required=False, allow_null=True)
    msg = serializers.CharField()
    rc = serializers.IntegerField(default=0)
    records = serializers.JSONField(required=False, allow_null=True)
    records_typed = serializers.JSONField(required=False, allow_null=True)
    record_type = serializers.CharField(required=False, allow_null=True)

    @classmethod
    def from_sync_result(cls, result: SyncResult, rc: int = 0) -> Dict[str, Any]:
        """Convert a SyncResult into serializer payload."""

        return {
            "nrows": result.count,
            "ncols": None,
            "msg": result.message,
            "rc": rc,
            "records": result.records_json,
            "records_typed": list(result.typed_records or result.records),
            "record_type": result.record_type,
        }
