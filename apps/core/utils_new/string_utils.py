import json
import random
from rest_framework.utils.encoders import JSONEncoder
from django.contrib.gis.measure import Distance


__all__ = [
    'CustomJsonEncoderWithDistance',
    'clean_record',
    'getformatedjson',
    'sumDig',
    'orderedRandom',
]


class CustomJsonEncoderWithDistance(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Distance):
            return obj.m
        return super(CustomJsonEncoderWithDistance, self).default(obj)


def encrypt(data: bytes) -> bytes:
    """
    HARD DEPRECATED - DO NOT USE THIS FUNCTION.

    CRITICAL SECURITY VULNERABILITY (CVSS 7.5):
    This function uses zlib compression, NOT real encryption!
    - NOT cryptographically secure
    - Trivially reversible (anyone can decompress)
    - NO authentication or integrity protection
    - NO key management
    - Violates .claude/rules.md Rule #2

    MIGRATION REQUIRED:
    Use apps.core.services.secure_encryption_service.encrypt() instead.

    Raises:
        RuntimeError: ALWAYS - This function is blocked in ALL environments
    """
    import logging

    logger = logging.getLogger("security")
    logger.critical(
        "SECURITY VIOLATION: Attempted to use HARD DEPRECATED insecure encrypt()",
        extra={
            'function': 'string_utils.encrypt',
            'security_level': 'CRITICAL',
            'cvss_score': 7.5,
            'rule_violation': '.claude/rules.md Rule #2',
            'migration_path': 'apps.core.services.secure_encryption_service.encrypt()'
        }
    )
    raise RuntimeError(
        "CRITICAL SECURITY ERROR: This encrypt() function is HARD DEPRECATED and blocked in ALL environments.\n"
        "It uses insecure zlib compression instead of real encryption (CVSS 7.5).\n\n"
        "REQUIRED MIGRATION:\n"
        "  from apps.core.services.secure_encryption_service import SecureEncryptionService\n"
        "  encrypted = SecureEncryptionService.encrypt(data)\n\n"
        "See .claude/rules.md Rule #2 for details."
    )


def decrypt(obscured: bytes) -> bytes:
    """
    HARD DEPRECATED - DO NOT USE THIS FUNCTION.

    CRITICAL SECURITY VULNERABILITY (CVSS 7.5):
    This function uses zlib decompression, NOT real decryption!
    - NOT cryptographically secure
    - Trivially reversible (anyone can decompress)
    - NO authentication or integrity protection
    - NO key management
    - Violates .claude/rules.md Rule #2

    MIGRATION REQUIRED:
    Use apps.core.services.secure_encryption_service.decrypt() instead.

    Raises:
        RuntimeError: ALWAYS - This function is blocked in ALL environments
    """
    import logging

    logger = logging.getLogger("security")
    logger.critical(
        "SECURITY VIOLATION: Attempted to use HARD DEPRECATED insecure decrypt()",
        extra={
            'function': 'string_utils.decrypt',
            'security_level': 'CRITICAL',
            'cvss_score': 7.5,
            'rule_violation': '.claude/rules.md Rule #2',
            'migration_path': 'apps.core.services.secure_encryption_service.decrypt()'
        }
    )
    raise RuntimeError(
        "CRITICAL SECURITY ERROR: This decrypt() function is HARD DEPRECATED and blocked in ALL environments.\n"
        "It uses insecure zlib decompression instead of real decryption (CVSS 7.5).\n\n"
        "REQUIRED MIGRATION:\n"
        "  from apps.core.services.secure_encryption_service import SecureEncryptionService\n"
        "  decrypted = SecureEncryptionService.decrypt(encrypted_data)\n\n"
        "See .claude/rules.md Rule #2 for details."
    )


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
