import json
import random
from rest_framework.utils.encoders import JSONEncoder
from django.contrib.gis.measure import Distance


class CustomJsonEncoderWithDistance(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Distance):
            return obj.m
        return super(CustomJsonEncoderWithDistance, self).default(obj)


def encrypt(data: bytes) -> bytes:
    import zlib
    from base64 import urlsafe_b64encode as b64e

    data = bytes(data, "utf-8")
    return b64e(zlib.compress(data, 9))


def decrypt(obscured: bytes) -> bytes:
    from zlib import decompress
    from base64 import urlsafe_b64decode as b64d

    byte_val = decompress(b64d(obscured))
    return byte_val.decode("utf-8")


def clean_record(record):
    from django.contrib.gis.geos import GEOSGeometry

    for k, v in record.items():
        if k in ["gpslocation", "startlocation", "endlocation"]:
            v = v.split(",")
            p = f"POINT({v[1]} {v[0]})"
            record[k] = GEOSGeometry(p, srid=4326)
    return record


def getformatedjson(geofence=None, jsondata=None, rettype=dict):
    data = jsondata or geofence.geojson
    geodict = json.loads(data)
    result = [{"lat": lat, "lng": lng} for lng, lat in geodict["coordinates"][0]]
    return result if rettype == dict else json.dumps(result)


def sumDig(n):
    a = 0
    while n > 0:
        a = a + n % 10
        n = int(n / 10)

    return a


def orderedRandom(arr, k):
    if not len(arr) > 25:
        return arr
    indices = random.sample(range(len(arr)), k)
    return [arr[i] for i in sorted(indices)]


def format_data(objects):
    columns, rows, data = objects[0].keys(), {}, {}
    for i, d in enumerate(objects):
        for c in columns:
            rows[i][c] = "" if rows[i][c] is None else str(rows[i][c])
    data["rows"] = rows
    return data
