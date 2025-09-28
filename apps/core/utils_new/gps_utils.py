from django.db.models import Func, F, Value, CharField, FloatField
from django.db.models.functions import Cast, Concat


class JsonSubstring(Func):
    function = "SUBSTRING"
    template = "%(function)s(%(expressions)s from '\\[(.+)\\]')"


def add_gps_coordinates_annotation(queryset, gps_field_name='gpslocation'):
    from django.contrib.gis.db.models.functions import AsGeoJSON

    return queryset.annotate(
        gps_json=AsGeoJSON(gps_field_name),
        coordinates_str=JsonSubstring("gps_json"),
        lat=Cast(
            Func(
                F("coordinates_str"),
                Value(","),
                Value(2),
                function="split_part",
            ),
            FloatField(),
        ),
        lon=Cast(
            Func(
                F("coordinates_str"),
                Value(","),
                Value(1),
                function="split_part",
            ),
            FloatField(),
        ),
        coordinates=Concat(
            Cast("lat", CharField()),
            Value(", "),
            Cast("lon", CharField()),
            output_field=CharField(),
        ),
    )


__all__ = ['JsonSubstring', 'add_gps_coordinates_annotation']