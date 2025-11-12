"""
Business Unit helper functions.

Contains utility functions and default values for the Bt model.
"""


def bu_defaults():
    """Default preferences for business units with comprehensive settings."""
    return {
        "mobilecapability": [],
        "validimei": "",
        "webcapability": [],
        "portletcapability": [],
        "validip": "",
        "reliveronpeoplecount": 0,
        "reportcapability": [],
        "usereliver": False,
        "pvideolength": 10,
        "guardstrenth": 0,
        "malestrength": 0,
        "femalestrength": 0,
        "siteclosetime": "",
        "tag": "",
        "siteopentime": "",
        "nearbyemergencycontacts": [],
        "maxadmins": 5,
        "address": "",
        "address2": None,
        "permissibledistance": 0,
        "controlroom": [],
        "ispermitneeded": False,
        "no_of_devices_allowed": 0,
        "no_of_users_allowed_mob": 0,
        "no_of_users_allowed_web": 0,
        "no_of_users_allowed_both": 0,
        "devices_currently_added": 0,
        "startdate": "",
        "enddate": "",
        "onstop": "",
        "onstopmessage": "",
        "clienttimezone": "",
        "billingtype": "",
        "total_people_count": 0,
        "contract_designcount": {},
        "posted_people": [],
    }
