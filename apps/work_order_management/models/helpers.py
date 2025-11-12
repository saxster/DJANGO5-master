"""
Work Order Management - Helper Functions

This module contains default value functions for JSONField defaults.
"""


def geojson():
    """Default value for geojson field"""
    return {"gpslocation": ""}


def other_data():
    """Default value for other_data field with vendor token and scoring fields"""
    return {
        "token": None,
        "created_at": None,
        "token_expiration": 5,  # min
        "reply_from_vendor": "",
        "wp_seqno": 0,
        "wp_approvers": [],
        "wp_verifiers": [],
        "section_weightage": 0,
        "overall_score": 0,
        "remarks": "",
        "uptime_score": 0,
    }


def wo_history_json():
    """Default value for work order history tracking"""
    return {"wo_history": [], "wp_history": []}
