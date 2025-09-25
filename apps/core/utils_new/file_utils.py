import os
import logging
from dateutil import parser
from datetime import datetime
from django.db.models import Q, F, Case, When, Value, Func
from django.contrib.gis.db.models.functions import AsGeoJSON
from django.db.models.functions import Cast, Concat, Substr, StrIndex, TruncSecond
import apps.onboarding.models as ob
from django.db import models
from apps.activity.models.location_model import Location
from apps.activity.models.asset_model import Asset

logger = logging.getLogger("django")

from django.conf import settings

# Header Mapping
HEADER_MAPPING = {
    "TYPEASSIST": ["Name*", "Code*", "Type*", "Client*"],
    "PEOPLE": [
        "Code*",
        "Name*",
        "User For*",
        "Employee Type*",
        "Login ID*",
        "Password*",
        "Gender*",
        "Mob No*",
        "Email*",
        "Date of Birth*",
        "Date of Join*",
        "Client*",
        "Site*",
        "Designation",
        "Department",
        "Work Type",
        "Report To",
        "Date of Release",
        "Device Id",
        "Is Emergency Contact",
        "Mobile Capability",
        "Report Capability",
        "Web Capability",
        "Portlet Capability",
        "Current Address",
        "Blacklist",
        "Alert Mails",
    ],
    "BU": [
        "Code*",
        "Name*",
        "Belongs To*",
        "Type*",
        "Site Type",
        "Control Room",
        "Permissible Distance",
        "Site Manager",
        "Sol Id",
        "Enable",
        "GPS Location",
        "Address",
        "State",
        "Country",
        "City",
    ],
    "QUESTION": [
        "Question Name*",
        "Answer Type*",
        "Min",
        "Max",
        "Alert Above",
        "Alert Below",
        "Is WorkFlow",
        "Options",
        "Alert On",
        "Enable",
        "Is AVPT",
        "AVPT Type",
        "Client*",
        "Unit",
        "Category",
    ],
    "ASSET": [
        "Code*",
        "Name*",
        "Running Status*",
        "Identifier*",
        "Is Critical",
        "Client*",
        "Site*",
        "Capacity",
        "BelongsTo",
        "Type",
        "GPS Location",
        "Category",
        "SubCategory",
        "Brand",
        "Unit",
        "Service Provider",
        "Enable",
        "Is Meter",
        "Is Non Engg. Asset",
        "Meter",
        "Model",
        "Supplier",
        "Invoice No",
        "Invoice Date",
        "Service",
        "Service From Date",
        "Service To Date",
        "Year of Manufacture",
        "Manufactured Serial No",
        "Bill Value",
        "Bill Date",
        "Purchase Date",
        "Installation Date",
        "PO Number",
        "FAR Asset ID",
    ],
    "GROUP": ["Group Name*", "Type*", "Client*", "Site*", "Enable"],
    "GROUPBELONGING": ["Group Name*", "Of People", "Of Site", "Client*", "Site*"],
    "VENDOR": [
        "Code*",
        "Name*",
        "Type*",
        "Address*",
        "Email*",
        "Applicable to All Sites",
        "Mob No*",
        "Site*",
        "Client*",
        "GPS Location",
        "Enable",
    ],
    "LOCATION": [
        "Code*",
        "Name*",
        "Type*",
        "Status*",
        "Is Critical",
        "Belongs To",
        "Site*",
        "Client*",
        "GPS Location",
        "Enable",
    ],
    "QUESTIONSET": [
        "Seq No*",
        "Question Set Name*",
        "Belongs To*",
        "QuestionSet Type*",
        "Asset Includes",
        "Site Includes",
        "Site*",
        "Client*",
        "Site Group Includes",
        "Site Type Includes",
        "Show To All Sites",
        "URL",
    ],
    "QUESTIONSETBELONGING": [
        "Question Name*",
        "Question Set*",
        "Client*",
        "Site*",
        "Answer Type*",
        "Seq No*",
        "Is AVPT",
        "Min",
        "Max",
        "Alert Above",
        "Alert Below",
        "Options",
        "Alert On",
        "Is Mandatory",
        "AVPT Type",
    ],
    "SCHEDULEDTASKS": [
        "Name*",
        "Description*",
        "Scheduler*",
        "Asset*",
        "Question Set/Checklist*",
        "People*",
        "Group Name*",
        "Plan Duration*",
        "Gracetime Before*",
        "Gracetime After*",
        "Notify Category*",
        "From Date*",
        "Upto Date*",
        "Scan Type*",
        "Client*",
        "Site*",
        "Priority*",
        "Seq No",
        "Start Time",
        "End Time",
        "Belongs To*",
    ],
    "SCHEDULEDTOURS": [
        "Name*",
        "Description",
        "People",
        "Group Name",
        "Priority*",
        "Notify Category*",
        "Plan Duration*",
        "Grace Time*",
        "Scheduler*",
        "From Date*",
        "Upto Date*",
        "Scan Type*",
        "Client*",
        "Site*",
        "Is Time Restricted",
        "Is Dynamic",
    ],
    "TOURSCHECKPOINTS": [
        "Seq No*",
        "Asset/Checkpoint*",
        "Question Set*",
        "Expiry Time*",
        "Belongs To*",
        "Client*",
        "Site*",
    ],
    "GEOFENCE": [
        "Code*",
        "Name*",
        "Site*",
        "Client*",
        "Alert to People*",
        "Alert to Group*",
        "Alert Text*",
        "Enable",
        "Radius*",
    ],
    "GEOFENCE_PEOPLE": [
        "Code*",
        "People Code*",
        "Site*",
        "Client*",
        "Valid From*",
        "Valid To*",
        "Start Time*",
        "End Time*",
    ],
    "SHIFT": [
        "Name*",
        "Start Time*",
        "End Time*",
        "People Count*",
        "Night Shift*",
        "Site*",
        "Client*",
        "Enable*",
        "Type*",
        "Id*",
        "Count*",
        "Overtime*",
        "Gracetime*",
    ],
}

Example_data = {
    "TYPEASSIST": [
        ("Reception Area", "RECEPTION", "LOCATIONTYPE", "CLIENT_A"),
        ("Bank", "BANK", "SITETYPE", "CLIENT_B"),
        ("Manager", "MANAGER", "DESIGNATIONTYPE", "CLIENT_C"),
    ],
    "BU": [
        (
            "MUM001",
            "Site A",
            "NONE",
            "BRANCH",
            "BANK",
            ["CRAND", "CRGCH"],
            "12",
            "John Doe",
            "123",
            "TRUE",
            "19.05,73.51",
            "123 main street, xyz city",
            "California",
            "USA",
            "Valparaíso",
        ),
        (
            "MUM002",
            "Site B",
            "MUM001",
            "ZONE",
            "OFFICE",
            ["CRAND", "CRGCH"],
            "8",
            "Jane Smith",
            "456",
            "FALSE",
            "19.05,73.51",
            "124 main street, xyz city",
            "New York",
            "Canada",
            "Hobart",
        ),
        (
            "MUM003",
            "Site C",
            "NONE",
            "SITE",
            "SUPERMARKET",
            ["CRAND", "CRGCH"],
            "0",
            "Ming Yang",
            "789",
            "TRUE",
            "19.05,73.51",
            "125 main street, xyz city",
            "california",
            "USA",
            "Manarola",
        ),
    ],
    "LOCATION": [
        (
            "LOC001",
            "Location A",
            "GROUNDFLOOR",
            "WORKING",
            "TRUE",
            "NONE",
            "SITE_A",
            "CLIENT_A",
            "19.05,73.51",
            "TRUE",
        ),
        (
            "LOC002",
            "Location B",
            "MAINENTRANCE",
            "SCRAPPED",
            "FALSE",
            "MUM001",
            "SITE_B",
            "CLIENT_A",
            "19.05,73.52",
            "FALSE",
        ),
        (
            "LOC003",
            "Location C",
            "FIRSTFLOOR",
            "RUNNING",
            "TRUE",
            "NONE",
            "SITE_C",
            "CLIENT_A",
            "19.05,73.53",
            "TRUE",
        ),
    ],
    "ASSET": [
        (
            "ASSET01",
            "Asset A",
            "STANDBY",
            "ASSET",
            "TRUE",
            "CLIENT_A",
            "SITE_A",
            "0.01",
            "NONE",
            "ELECTRICAL",
            "19.05,73.51",
            "NONE",
            "NONE",
            "BRAND_A",
            "NONE",
            "CLINET_A",
            "TRUE",
            "FALSE",
            "TRUE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "2024-04-13",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
        ),
        (
            "ASSET02",
            "Asset B",
            "WORKING",
            "ASSET",
            "FALSE",
            "CLIENT_B",
            "SITE_B",
            "0.02",
            "NONE",
            "MECHANICAL",
            "19.05,73.52",
            "NONE",
            "NONE",
            "BRAND_B",
            "NONE",
            "CLINET_A",
            "TRUE",
            "FALSE",
            "TRUE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "2024-04-13",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
        ),
        (
            "ASSET03",
            "Asset C",
            "MAINTENANCE",
            "CHECKPOINT",
            "TRUE",
            "CLIENT_C",
            "SITE_C",
            "0",
            "NONE",
            "ELECTRICAL",
            "19.05,73.53",
            "NONE",
            "NONE",
            "BRAND_C",
            "NONE",
            "CLINET_A",
            "TRUE",
            "FALSE",
            "TRUE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "2024-04-13",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
        ),
    ],
    "VENDOR": [
        (
            "VENDOR_A",
            "Vendor A",
            "ELECTRICAL",
            "123 main street, xyz city",
            "XYZ@gmail.com",
            "TRUE",
            "911234567891",
            "SITE_A",
            "CLIENT_A",
            "19.05,73.51",
            "TRUE",
        ),
        (
            "VENDOR_B",
            "Vendor B",
            "MECHANICAL",
            "124 main street, xyz city",
            "XYZ@gmail.com",
            "FALSE",
            "911478529630",
            "SITE_B",
            "CLIENT_B",
            "19.05,73.51",
            "FALSE",
        ),
        (
            "VENDOR_C",
            "Vendor C",
            "ELECTRICAL",
            "125 main street, xyz city",
            "XYZ@gmail.com",
            "TRUE",
            "913698521470",
            "SITE_C",
            "CLIENT_C",
            "19.05,73.51",
            "TRUE",
        ),
    ],
    "PEOPLE": [
        (
            "PERSON_A",
            "Person A",
            "Web",
            "STAFF",
            "A123",
            "XYZ",
            "M",
            "911234567891",
            "abc@gmail.com",
            "yyyy-mm-dd",
            "yyyy-mm-dd",
            "CLIENT_A",
            "SITE_A",
            "MANAGER",
            "HR",
            "NONE",
            "NONE",
            "yyyy-mm-dd",
            "513bb5f9c78c9117",
            "TRUE",
            "SELFATTENDANCE, TICKET,INCIDENTREPORT,SOS,SITECRISIS,TOUR",
            "NONE",
            "TR_SS_SITEVISIT,DASHBOARD,TR_SS_SITEVISIT,TR_SS_CONVEYANCE,TR_GEOFENCETRACKING",
            "NONE",
            "123 main street, xyz city",
            "FALSE",
            "TRUE",
        ),
        (
            "PERSON_B",
            "Person B",
            "Mobile",
            "SECURITY",
            "B456",
            "XYZ",
            "F",
            "913698521477",
            "abc@gmail.com",
            "yyyy-mm-dd",
            "yyyy-mm-dd",
            "CLIENT_B",
            "SITE_B",
            "SUPERVISOR",
            "TRAINING",
            "NONE",
            "NONE",
            "yyyy-mm-dd",
            "513bb5f9c78c9118",
            "FALSE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "124 main street, xyz city",
            "FALSE",
            "FALSE",
        ),
        (
            "PERSON_C",
            "Person C",
            "NONE",
            "NONE",
            "C8910",
            "XYZ",
            "O",
            "912587891463",
            "abc@gmail.com",
            "yyyy-mm-dd",
            "yyyy-mm-dd",
            "CLIENT_C",
            "SITE_C",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "yyyy-mm-dd",
            "513bb5f9c78c9119",
            "TRUE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "125 main street, xyz city",
            "FALSE",
            "TRUE",
        ),
    ],
    "QUESTION": [
        (
            "Are s/staff found with correct accessories / pressed uniform?",
            "MULTILINE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "TRUE",
            "",
            "",
            "TRUE",
            "TRUE",
            "NONE",
            "CLIENT_A",
            "NONE",
            "NONE",
        ),
        (
            "Electic Meter box is ok?",
            "DROPDOWN",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "FALSE",
            "No, Yes, N/A",
            "",
            "TRUE",
            "TRUE",
            "NONE",
            "CLIENT_B",
            "NONE",
            "NONE",
        ),
        (
            "All lights working",
            "DROPDOWN",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "TRUE",
            "No, Yes, N/A",
            "",
            "TRUE",
            "TRUE",
            "NONE",
            "CLIENT_C",
            "NONE",
            "NONE",
        ),
    ],
    "QUESTIONSET": [
        (
            "1",
            "Question Set A",
            "NONE",
            "CHECKLIST",
            "ADMINBACK,CMRC",
            "MUM001,MUM003",
            "SITE_A",
            "CLIENT_A",
            "Group A,Group B",
            "BANK,OFFICE",
            "TRUE",
            "NONE",
        ),
        (
            "1",
            "Question Set B",
            "Question Set A",
            "INCIDENTREPORT",
            "NONE",
            "NONE",
            "SITE_B",
            "CLIENT_B",
            "NONE",
            "NONE",
            "FALSE",
            "NONE",
        ),
        (
            "1",
            "Question Set C",
            "Question Set A",
            "WORKPERMIT",
            "NONE",
            "NONE",
            "SITE_C",
            "CLIENT_C",
            "NONE",
            "NONE",
            "TRUE",
            "NONE",
        ),
    ],
    "QUESTIONSETBELONGING": [
        (
            "Are s/staff found with correct accessories / pressed uniform?",
            "Question Set A",
            "CLIENT_A",
            "SITE_A",
            "MULTILINE",
            "1",
            "FALSE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "TRUE",
            "FRONTCAMPIC",
        ),
        (
            "Electic Meter box is ok?",
            "Question Set B",
            "CLIENT_B",
            "SITE_B",
            "DROPDOWN",
            "5",
            "FALSE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "No, Yes, N/A",
            "NONE",
            "FALSE",
            "AUDIO",
        ),
        (
            "All lights working",
            "Question Set C",
            "CLIENT_C",
            "SITE_C",
            "DROPDOWN",
            "3",
            "TRUE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "No, Yes, N/A",
            "NONE",
            "TRUE",
            "NONE",
        ),
    ],
    "GROUP": [
        ("Group A", "PEOPLEGROUP", "CLIENT_A", "SITE_A", "TRUE"),
        ("Group B", "SITEGROUP", "CLIENT_B", "SITE_B", "FALSE"),
        ("Group C", "PEOPLEGROUP", "CLIENT_C", "SITE_C", "TRUE"),
    ],
    "GROUPBELONGING": [
        ("Group A", "Person A", "NONE", "CLIENT_A", "Yout_logged_in_site"),
        ("Group B", "Person B", "NONE", "CLIENT_B", "SITE_A"),
        ("Group C", "Person C", "NONE", "CLIENT_C", "SITE_B"),
    ],
    "SCHEDULEDTASKS": [
        (
            "Task A",
            "Task A Inspection",
            "0 20 * * *",
            "ASSETA",
            "Questionset A",
            "PERSON_A",
            "GROUP_A",
            "15",
            "5",
            "5",
            "RAISETICKETNOTIFY",
            "YYYY-MM-DD HH:MM:SS",
            "YYYY-MM-DD HH:MM:SS",
            "NFC",
            "CLIENT_A",
            "SITE_A",
            "HIGH",
            "1",
            "00:00:00",
            "00:00:00",
            "NONE",
        ),
        (
            "Task B",
            "Task B Daily Reading",
            "1 20 * * *",
            "ASSETB",
            "Checklist B",
            "PERSON_B",
            "GROUP_B",
            "18",
            "5",
            "5",
            "AUTOCLOSENOTIFY",
            "2023-06-07 12:00:00",
            "2023-06-07 16:00:00",
            "QR",
            "CLIENT_B",
            "SITE_B",
            "LOW",
            "6",
            "00:00:00",
            "00:00:00",
            "Task A Inspection",
        ),
        (
            "Task C",
            "Task C Inspection",
            "2 20 * * *",
            "ASSETC",
            "Questionset C",
            "PERSON_C",
            "GROUP_C",
            "20",
            "5",
            "5",
            "NONE",
            "2024-02-04 23:00:00",
            "2024-02-04 23:55:00",
            "SKIP",
            "CLIENT_C",
            "SITE_C",
            "MEDIUM",
            "3",
            "00:00:00",
            "00:00:00",
            "Task A Inspection",
        ),
    ],
    "SCHEDULEDTOURS": [
        (
            "TOUR A",
            "Inspection Tour A",
            "PERSON_A",
            "GROUP_A",
            "HIGH",
            "RAISETICKETNOTIFY",
            "15",
            "5",
            "55 11,16 * * *",
            "YYYY-MM-DD HH:MM:SS",
            "YYYY-MM-DD HH:MM:SS",
            "NFC",
            "CLIENT_A",
            "SITE_A",
            "FALSE",
            "FALSE",
        ),
        (
            "TOUR B",
            "Inspection Tour B",
            "PERSON_B",
            "GROUP_B",
            "LOW",
            "AUTOCLOSENOTIFY",
            "18",
            "5",
            "56 11,16 * * *",
            "2023-06-07 12:00:00",
            "2023-06-07 16:00:00",
            "QR",
            "CLIENT_B",
            "SITE_B",
            "FALSE",
            "FALSE",
        ),
        (
            "TOUR C",
            "Inspection Tour C",
            "PERSON_C",
            "GROUP_C",
            "MEDIUM",
            "RAISETICKETNOTIFY",
            "20",
            "5",
            "57 11,16 * * *",
            "2024-02-04 23:00:00",
            "2024-02-04 23:55:00",
            "SKIP",
            "CLIENT_C",
            "SITE_C",
            "TRUE",
            "TRUE",
        ),
    ],
    "TOURSCHECKPOINTS": [
        (
            "1",
            "CHECKPOINT_001",
            "SECURITY_CHECKLIST",
            "15",
            "TOUR A",
            "CLIENT_A",
            "SITE_A",
        ),
        (
            "2",
            "CHECKPOINT_002",
            "SECURITY_CHECKLIST",
            "10",
            "TOUR A",
            "CLIENT_A",
            "SITE_A",
        ),
        (
            "3",
            "CHECKPOINT_003",
            "SECURITY_CHECKLIST",
            "20",
            "TOUR A",
            "CLIENT_A",
            "SITE_A",
        ),
    ],
    "GEOFENCE": [
        (
            "GEO001",
            "TESTA",
            "SITE_A",
            "CLIENT_A",
            "P012345",
            "NONE",
            "Test",
            "TRUE",
            "100",
        ),
        (
            "GEO002",
            "TESTB",
            "SITE_B",
            "CLIENT_B",
            "P012345",
            "NONE",
            "Test",
            "FALSE",
            "200",
        ),
        (
            "GEO003",
            "TESTC",
            "SITE_C",
            "CLIENT_C",
            "NONE",
            "Group A",
            "Test",
            "TRUE",
            "300",
        ),
    ],
    "GEOFENCE_PEOPLE": [
        (
            "GEO001",
            "P023456",
            "SITE_A",
            "CLIENT_A",
            "17-12-2024",
            "20-12-2024",
            "10:00:00",
            "06:00:00",
        ),
        (
            "GEO002",
            "P023457",
            "SITE_B",
            "CLIENT_B",
            "18-12-2024",
            "21-12-2024",
            "10:00:00",
            "06:00:00",
        ),
        (
            "GEO003",
            "P023458",
            "SITE_C",
            "CLIENT_C",
            "19-12-2024",
            "22-12-2024",
            "10:00:00",
            "06:00:00",
        ),
    ],
    "SHIFT": [
        (
            "General Shift",
            "10:00:00",
            "18:00:00",
            "3",
            "FALSE",
            "SITE_A",
            "CLIENT_A",
            "TRUE",
            "HOD, RPO",
            "1, 2",
            "2, 1",
            "1, 1",
            "60, 30",
        ),
        (
            "Night Shift",
            "20:00:00",
            "08:00:00",
            "3",
            "FALSE",
            "SITE_B",
            "CLIENT_A",
            "TRUE",
            "HOD, RPO",
            "1, 2",
            "2, 1",
            "1, 1",
            "60, 60",
        ),
        (
            "General Shift",
            "20:00:00",
            "08:00:00",
            "3",
            "FALSE",
            "SITE_A",
            "CLIENT_A",
            "TRUE",
            "HOD, RPO",
            "1, 2",
            "2, 1",
            "1, 1",
            "30, 60",
        ),
    ],
}


HEADER_MAPPING_UPDATE = {
    "TYPEASSIST": ["ID*", "Name", "Code", "Type", "Client"],
    "PEOPLE": [
        "ID*",
        "Code",
        "Name",
        "User For",
        "Employee Type",
        "Login ID",
        "Gender",
        "Mob No",
        "Email",
        "Date of Birth",
        "Date of Join",
        "Client",
        "Site",
        "Designation",
        "Department",
        "Work Type",
        "Enable",
        "Report To",
        "Date of Release",
        "Device Id",
        "Is Emergency Contact",
        "Mobile Capability",
        "Report Capability",
        "Web Capability",
        "Portlet Capability",
        "Current Address",
        "Blacklist",
        "Alert Mails",
    ],
    "BU": [
        "ID*",
        "Code",
        "Name",
        "Belongs To",
        "Type",
        "Site Type",
        "Site Manager",
        "Sol Id",
        "Enable",
        "GPS Location",
        "Address",
        "City",
        "State",
        "Country",
    ],
    "QUESTION": [
        "ID*",
        "Question Name",
        "Answer Type",
        "Min",
        "Max",
        "Alert Above",
        "Alert Below",
        "Is WorkFlow",
        "Options",
        "Alert On",
        "Enable",
        "Is AVPT",
        "AVPT Type",
        "Client",
        "Unit",
        "Category",
    ],
    "ASSET": [
        "ID*",
        "Code",
        "Name",
        "Running Status",
        "Identifier",
        "Is Critical",
        "Client",
        "Site",
        "Capacity",
        "BelongsTo",
        "Type",
        "GPS Location",
        "Category",
        "SubCategory",
        "Brand",
        "Unit",
        "Service Provider",
        "Enable",
        "Is Meter",
        "Is Non Engg. Asset",
        "Meter",
        "Model",
        "Supplier",
        "Invoice No",
        "Invoice Date",
        "Service",
        "Service From Date",
        "Service To Date",
        "Year of Manufacture",
        "Manufactured Serial No",
        "Bill Value",
        "Bill Date",
        "Purchase Date",
        "Installation Date",
        "PO Number",
        "FAR Asset ID",
    ],
    "GROUP": ["ID*", "Group Name", "Type", "Client", "Site", "Enable"],
    "GROUPBELONGING": ["ID*", "Group Name", "Of People", "Of Site", "Client", "Site"],
    "VENDOR": [
        "ID*",
        "Code",
        "Name",
        "Type",
        "Address",
        "Email",
        "Applicable to All Sites",
        "Mob No",
        "Site",
        "Client",
        "GPS Location",
        "Enable",
    ],
    "LOCATION": [
        "ID*",
        "Code",
        "Name",
        "Type",
        "Status",
        "Is Critical",
        "Belongs To",
        "Site",
        "Client",
        "GPS Location",
        "Enable",
    ],
    "QUESTIONSET": [
        "ID*",
        "Seq No",
        "Question Set Name",
        "Belongs To",
        "QuestionSet Type",
        "Asset Includes",
        "Site Includes",
        "Site",
        "Client",
        "Site Group Includes",
        "Site Type Includes",
        "Show To All Sites",
        "URL",
    ],
    "QUESTIONSETBELONGING": [
        "ID*",
        "Question Name",
        "Question Set",
        "Client",
        "Site",
        "Answer Type",
        "Seq No",
        "Is AVPT",
        "Min",
        "Max",
        "Alert Above",
        "Alert Below",
        "Options",
        "Alert On",
        "Is Mandatory",
        "AVPT Type",
    ],
    "SCHEDULEDTASKS": [
        "ID*",
        "Name",
        "Description",
        "Scheduler",
        "Asset",
        "Question Set/Checklist",
        "People",
        "Group Name",
        "Plan Duration",
        "Gracetime Before",
        "Gracetime After",
        "Notify Category",
        "From Date",
        "Upto Date",
        "Scan Type",
        "Client",
        "Site",
        "Priority",
        "Seq No",
        "Start Time",
        "End Time",
        "Belongs To",
    ],
    "SCHEDULEDTOURS": [
        "ID*",
        "Name",
        "Description",
        "Scheduler",
        "Asset",
        "Question Set/Checklist",
        "People",
        "Group Name",
        "Plan Duration",
        "Gracetime",
        "Expiry Time",
        "Notify Category",
        "From Date",
        "Upto Date",
        "Scan Type",
        "Client",
        "Site",
        "Priority",
        "Seq No",
        "Start Time",
        "End Time",
        "Belongs To",
    ],
}

Example_data_update = {
    "TYPEASSIST": [
        ("1975", "Reception Area", "RECEPTION", "LOCATIONTYPE", "CLIENT_A"),
        ("1976", "Bank", "BANK", "SITETYPE", "CLIENT_B"),
        ("1977", "Manager", "MANAGER", "DESIGNATIONTYPE", "CLIENT_C"),
    ],
    "BU": [
        (
            "495",
            "MUM001",
            "Site A",
            "NONE",
            "BRANCH",
            "BANK",
            "John Doe",
            "123",
            "TRUE",
            "19.05,73.51",
            "123 main street, xyz city",
            "Valparaíso",
            "California",
            "USA",
        ),
        (
            "496",
            "MUM002",
            "Site B",
            "MUM001",
            "ZONE",
            "OFFICE",
            "Jane Smith",
            "456",
            "FALSE",
            "19.05,73.51",
            "124 main street, xyz city",
            "Hobart",
            "New York",
            "Canada",
        ),
        (
            "497",
            "MUM003",
            "Site C",
            "NONE",
            "SITE",
            "SUPERMARKET",
            "Ming Yang",
            "789",
            "TRUE",
            "19.05,73.51",
            "125 main street, xyz city",
            "Manarola",
            "California",
            "USA",
        ),
    ],
    "LOCATION": [
        (
            "47",
            "LOC001",
            "Location A",
            "GROUNDFLOOR",
            "WORKING",
            "TRUE",
            "NONE",
            "SITE_A",
            "CLIENT_A",
            "19.05,73.51",
            "TRUE",
        ),
        (
            "48",
            "LOC002",
            "Location B",
            "MAINENTRANCE",
            "SCRAPPED",
            "FALSE",
            "MUM001",
            "SITE_B",
            "CLIENT_A",
            "19.05,73.52",
            "FALSE",
        ),
        (
            "49",
            "LOC003",
            "Location C",
            "FIRSTFLOOR",
            "MAINTENANCE",
            "TRUE",
            "NONE",
            "SITE_C",
            "CLIENT_A",
            "19.05,73.53",
            "TRUE",
        ),
    ],
    "ASSET": [
        (
            "1127",
            "ASSET01",
            "Asset A",
            "STANDBY",
            "ASSET",
            "TRUE",
            "CLIENT_A",
            "SITE_A",
            "0.01",
            "NONE",
            "ELECTRICAL",
            "19.05,73.51",
            "NONE",
            "NONE",
            "BRAND_A",
            "NONE",
            "CLINET_A",
            "TRUE",
            "FALSE",
            "TRUE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "2024-04-13",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
        ),
        (
            "1128",
            "ASSET02",
            "Asset B",
            "MAINTENANCE",
            "ASSET",
            "FALSE",
            "CLIENT_B",
            "SITE_B",
            "0.02",
            "NONE",
            "MECHANICAL",
            "19.05,73.52",
            "NONE",
            "NONE",
            "BRAND_B",
            "NONE",
            "CLINET_A",
            "TRUE",
            "FALSE",
            "TRUE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "2024-04-13",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
        ),
        (
            "1129",
            "ASSET03",
            "Asset C",
            "WORKING",
            "CHECKPOINT",
            "TRUE",
            "CLIENT_C",
            "SITE_C",
            "0",
            "NONE",
            "ELECTRICAL",
            "19.05,73.53",
            "NONE",
            "NONE",
            "BRAND_C",
            "NONE",
            "CLINET_A",
            "TRUE",
            "FALSE",
            "TRUE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "2024-04-13",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
        ),
    ],
    "VENDOR": [
        (
            "527",
            "VENDOR_A",
            "Vendor A",
            "ELECTRICAL",
            "123 main street, xyz city",
            "XYZ@gmail.com",
            "TRUE",
            "911234567891",
            "SITE_A",
            "CLIENT_A",
            "19.05,73.51",
            "TRUE",
        ),
        (
            "528",
            "VENDOR_B",
            "Vendor B",
            "MECHANICAL",
            "124 main street, xyz city",
            "XYZ@gmail.com",
            "FALSE",
            "911478529630",
            "SITE_B",
            "CLIENT_B",
            "19.05,73.51",
            "FALSE",
        ),
        (
            "529",
            "VENDOR_C",
            "Vendor C",
            "ELECTRICAL",
            "125 main street, xyz city",
            "XYZ@gmail.com",
            "TRUE",
            "913698521470",
            "SITE_C",
            "CLIENT_C",
            "19.05,73.51",
            "TRUE",
        ),
    ],
    "PEOPLE": [
        (
            "2422",
            "PERSON_A",
            "Person A",
            "Web",
            "STAFF",
            "A123",
            "M",
            "911234567891",
            "abc@gmail.com",
            "yyyy-mm-dd",
            "yyyy-mm-dd",
            "CLIENT_A",
            "SITE_A",
            "MANAGER",
            "HR",
            "CPO",
            "TRUE",
            "NONE",
            "yyyy-mm-dd",
            "513bb5f9c78c9117",
            "TRUE",
            "SELFATTENDANCE, TICKET,INCIDENTREPORT,SOS,SITECRISIS,TOUR",
            "NONE",
            "TR_SS_SITEVISIT,DASHBOARD,TR_SS_SITEVISIT,TR_SS_CONVEYANCE,TR_GEOFENCETRACKING",
            "NONE",
            "123 main street, xyz city",
            "FALSE",
            "TRUE",
        ),
        (
            "2423",
            "PERSON_B",
            "Person B",
            "Mobile",
            "SECURITY",
            "B456",
            "F",
            "913698521477",
            "abc@gmail.com",
            "yyyy-mm-dd",
            "yyyy-mm-dd",
            "CLIENT_B",
            "SITE_B",
            "SUPERVISOR",
            "TRAINING",
            "EXEC",
            "FALSE",
            "NONE",
            "yyyy-mm-dd",
            "513bb5f9c78c9118",
            "FALSE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "124 main street, xyz city",
            "FALSE",
            "FALSE",
        ),
        (
            "2424",
            "PERSON_C",
            "Person C",
            "NONE",
            "ADMIN",
            "C8910",
            "O",
            "912587891463",
            "abc@gmail.com",
            "yyyy-mm-dd",
            "yyyy-mm-dd",
            "CLIENT_C",
            "SITE_C",
            "RPO",
            "ACCOUNTS",
            "ASM",
            "TRUE",
            "NONE",
            "yyyy-mm-dd",
            "513bb5f9c78c9119",
            "TRUE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "125 main street, xyz city",
            "FALSE",
            "TRUE",
        ),
    ],
    "QUESTION": [
        (
            "995",
            "Are s/staff found with correct accessories / pressed uniform?",
            "MULTILINE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "TRUE",
            "",
            "",
            "TRUE",
            "TRUE",
            "NONE",
            "CLIENT_A",
            "NONE",
            "NONE",
        ),
        (
            "996",
            "Electic Meter box is ok?",
            "DROPDOWN",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "FALSE",
            "No, Yes, N/A",
            "",
            "TRUE",
            "TRUE",
            "NONE",
            "CLIENT_B",
            "NONE",
            "NONE",
        ),
        (
            "997",
            "All lights working",
            "DROPDOWN",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "TRUE",
            "No, Yes, N/A",
            "",
            "TRUE",
            "TRUE",
            "NONE",
            "CLIENT_C",
            "NONE",
            "NONE",
        ),
    ],
    "QUESTIONSET": [
        (
            "700",
            "1",
            "Question Set A",
            "NONE",
            "CHECKLIST",
            "ADMINBACK,CMRC",
            "MUM001,MUM003",
            "SITE_A",
            "CLIENT_A",
            "Group A,Group B",
            "BANK,OFFICE",
            "TRUE",
            "NONE",
        ),
        (
            "701",
            "1",
            "Question Set B",
            "Question Set A",
            "INCIDENTREPORT",
            "NONE",
            "NONE",
            "SITE_B",
            "CLIENT_B",
            "NONE",
            "NONE",
            "FALSE",
            "NONE",
        ),
        (
            "702",
            "1",
            "Question Set C",
            "Question Set A",
            "WORKPERMIT",
            "NONE",
            "NONE",
            "SITE_C",
            "CLIENT_C",
            "NONE",
            "NONE",
            "TRUE",
            "NONE",
        ),
    ],
    "QUESTIONSETBELONGING": [
        (
            "1567",
            "Are s/staff found with correct accessories / pressed uniform?",
            "Question Set A",
            "CLIENT_A",
            "SITE_A",
            "MULTILINE",
            "1",
            "FALSE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "TRUE",
            "FRONTCAMPIC",
        ),
        (
            "1568",
            "Electic Meter box is ok?",
            "Question Set B",
            "CLIENT_B",
            "SITE_B",
            "DROPDOWN",
            "5",
            "FALSE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "No, Yes, N/A",
            "NONE",
            "FALSE",
            "AUDIO",
        ),
        (
            "1569",
            "All lights working",
            "Question Set C",
            "CLIENT_C",
            "SITE_C",
            "DROPDOWN",
            "3",
            "TRUE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "No, Yes, N/A",
            "NONE",
            "TRUE",
            "NONE",
        ),
    ],
    "GROUP": [
        ("163", "Group A", "PEOPLEGROUP", "CLIENT_A", "SITE_A", "TRUE"),
        ("164", "Group B", "SITEGROUP", "CLIENT_B", "SITE_B", "FALSE"),
        ("165", "Group C", "PEOPLEGROUP", "CLIENT_C", "SITE_C", "TRUE"),
    ],
    "GROUPBELONGING": [
        ("2764", "Group A", "Person A", "NONE", "CLIENT_A", "Yout_logged_in_site"),
        ("2765", "Group B", "Person B", "NONE", "CLIENT_B", "SITE_A"),
        ("2766", "Group C", "Person C", "NONE", "CLIENT_C", "SITE_B"),
    ],
    "SCHEDULEDTASKS": [
        (
            "2824",
            "Task A",
            "Task A Inspection",
            "0 20 * * *",
            "ASSETA",
            "Questionset A",
            "PERSON_A",
            "GROUP_A",
            "15",
            "5",
            "5",
            "RAISETICKETNOTIFY",
            "YYYY-MM-DD HH:MM:SS",
            "YYYY-MM-DD HH:MM:SS",
            "NFC",
            "CLIENT_A",
            "SITE_A",
            "HIGH",
            "1",
            "00:00:00",
            "00:00:00",
            "NONE",
        ),
        (
            "2825",
            "Task B",
            "Task B Daily Reading",
            "1 20 * * *",
            "ASSETB",
            "Checklist B",
            "PERSON_B",
            "GROUP_B",
            "18",
            "5",
            "5",
            "AUTOCLOSENOTIFY",
            "2023-06-07 12:00:00",
            "2023-06-07 16:00:00",
            "QR",
            "CLIENT_B",
            "SITE_B",
            "LOW",
            "6",
            "00:00:00",
            "00:00:00",
            "Task A Inspection",
        ),
        (
            "2826",
            "Task C",
            "Task C Inspection",
            "2 20 * * *",
            "ASSETC",
            "Questionset C",
            "PERSON_C",
            "GROUP_C",
            "20",
            "5",
            "5",
            "AUTOCLOSED",
            "2024-02-04 23:00:00",
            "2024-02-04 23:55:00",
            "SKIP",
            "CLIENT_C",
            "SITE_C",
            "MEDIUM",
            "3",
            "00:00:00",
            "00:00:00",
            "Task A Inspection",
        ),
    ],
    "SCHEDULEDTOURS": [
        (
            "2824",
            "TOUR A",
            "Inspection Tour A",
            "55 11,16 * * *",
            "ASSET_A",
            "Questionset A",
            "PERSON_A",
            "GROUP_A",
            "15",
            "5",
            "5",
            "RAISETICKETNOTIFY",
            "YYYY-MM-DD HH:MM:SS",
            "YYYY-MM-DD HH:MM:SS",
            "NFC",
            "CLIENT_A",
            "SITE_A",
            "HIGH",
            "1",
            "00:00:00",
            "00:00:00",
            "NONE",
        ),
        (
            "2825",
            "TOUR B",
            "Inspection Tour B",
            "56 11,16 * * *",
            "ASSET_B",
            "Checklist B",
            "PERSON_B",
            "GROUP_B",
            "18",
            "5",
            "5",
            "AUTOCLOSENOTIFY",
            "2023-06-07 12:00:00",
            "2023-06-07 16:00:00",
            "QR",
            "CLIENT_B",
            "SITE_B",
            "LOW",
            "6",
            "00:00:00",
            "00:00:00",
            "Task A Inspection",
        ),
        (
            "2826",
            "TOUR C",
            "Inspection Tour C",
            "57 11,16 * * *",
            "ASSET_C",
            "Questionset C",
            "PERSON_C",
            "GROUP_C",
            "20",
            "5",
            "5",
            "AUTOCLOSED",
            "2024-02-04 23:00:00",
            "2024-02-04 23:55:00",
            "SKIP",
            "CLIENT_C",
            "SITE_C",
            "MEDIUM",
            "3",
            "00:00:00",
            "00:00:00",
            "Task A Inspection",
        ),
    ],
}


def get_home_dir():
    from django.conf import settings

    return settings.MEDIA_ROOT


def upload(request, vendor=False):
    logger.info(f"{request.POST = }")
    activity_name = None
    S = request.session
    if "img" not in request.FILES:
        return
    foldertype = request.POST["foldertype"]
    if foldertype in [
        "task",
        "internaltour",
        "externaltour",
        "ticket",
        "incidentreport",
        "visitorlog",
        "conveyance",
        "workorder",
        "workpermit",
    ]:
        tabletype, activity_name = "transaction", foldertype.upper()
    if foldertype in ["people", "client"]:
        tabletype, activity_name = "master", foldertype.upper()
    if activity_name:
        logger.info(f"Floder type: {foldertype} and activity Name: {activity_name}")

    home_dir = settings.MEDIA_ROOT
    fextension = os.path.splitext(request.FILES["img"].name)[1]
    filename = (
        parser.parse(str(datetime.now())).strftime("%d_%b_%Y_%H%M%S") + fextension
    )
    logger.info(f"{filename = } {fextension = }")

    if tabletype == "transaction":
        fmonth = str(datetime.now().strftime("%b"))
        fyear = str(datetime.now().year)
        peopleid = request.POST["peopleid"]
        fullpath = f'{home_dir}/transaction/{S["clientcode"]}_{S["client_id"]}/{peopleid}/{activity_name}/{fyear}/{fmonth}/'

    else:
        fullpath = f'{home_dir}/master/{S["clientcode"]}_{S["client_id"]}/{foldertype}/'
    logger.info("Full Path of saving image", fullpath)
    logger.info(f"{fullpath = }")

    if not os.path.exists(fullpath):
        os.makedirs(fullpath)
    fileurl = f"{fullpath}{filename}"
    logger.info(f"{fileurl = }")
    try:
        if not os.path.exists(fileurl):
            with open(fileurl, "wb") as temp_file:
                temp_file.write(request.FILES["img"].read())
                temp_file.close()
    except Exception as e:
        logger.critical(e, exc_info=True)
        return False, None, None

    logger.info(f"{filename = } {fullpath = }")
    return True, filename, fullpath


def upload_vendor_file(file, womid):
    home_dir = settings.MEDIA_ROOT
    fmonth = str(datetime.now().strftime("%b"))
    fyear = str(datetime.now().year)
    fullpath = f"{home_dir}/transaction/workorder_management/details/{fyear}/{fmonth}/"
    fextension = os.path.splitext(file.name)[1]
    filename = (
        parser.parse(str(datetime.now())).strftime("%d_%b_%Y_%H%M%S")
        + f"womid_{womid}"
        + fextension
    )
    if not os.path.exists(fullpath):
        os.makedirs(fullpath)
    fileurl = f"{fullpath}{filename}"
    try:
        if not os.path.exists(fileurl):
            with open(fileurl, "wb") as temp_file:
                temp_file.write(file.read())
                temp_file.close()
    except Exception as e:
        logger.critical(e, exc_info=True)
        return False, None, None

    return True, filename, fullpath.replace(home_dir, "")


def download_qrcode(code, name, report_name, session, request):
    from apps.reports import utils as rutils

    report_essentials = rutils.ReportEssentials(report_name=report_name)
    ReportFormat = report_essentials.get_report_export_object()
    report = ReportFormat(
        filename=report_name,
        client_id=session["client_id"],
        formdata={"print_single_qr": code, "qrsize": 200, "name": name},
        request=request,
        returnfile=False,
    )
    return report.execute()


def excel_file_creation(R):
    import pandas as pd
    from io import BytesIO

    columns = HEADER_MAPPING.get(R["template"])
    data_ex = Example_data.get(R["template"])

    df = pd.DataFrame(data_ex, columns=columns)
    main_header = pd.DataFrame([columns], columns=columns)
    empty_row = pd.DataFrame([[""] * len(df.columns)], columns=df.columns)
    buffer = BytesIO()

    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, header=True, startrow=2)
        empty_row.to_excel(writer, index=False, header=False, startrow=len(df) + 3)
        main_header = pd.DataFrame([columns], columns=columns)
        main_header.to_excel(writer, index=False, header=False, startrow=len(df) + 6)
        workbook = writer.book
        worksheet = writer.sheets["Sheet1"]
        bold_format = workbook.add_format({"bold": True, "border": 1})
        for col_num, value in enumerate(columns):
            worksheet.write(len(df) + 6, col_num, value, bold_format)
        merge_format = workbook.add_format({"bg_color": "#E2F4FF", "border": 1})
        Text_for_sample_data = "[ Refernce Data ] Take the Reference of the below data to fill data in correct format :-"
        Text_for_actual_data = (
            "[ Actual Data ] Start filling data below the following headers :-"
        )
        worksheet.merge_range("A2:D2", Text_for_sample_data, merge_format)
        worksheet.merge_range("A9:D9", Text_for_actual_data, merge_format)

    buffer.seek(0)
    return buffer


def excel_file_creation_update(R, S):
    import pandas as pd
    from io import BytesIO

    columns = HEADER_MAPPING_UPDATE.get(R["template"])
    data_ex = Example_data_update.get(R["template"])
    get_data = get_type_data(R["template"], S)
    df = pd.DataFrame(data_ex, columns=columns)
    main_header = pd.DataFrame(get_data, columns=columns)
    empty_row = pd.DataFrame([[""] * len(df.columns)], columns=df.columns)
    buffer = BytesIO()

    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, header=True, startrow=2)
        empty_row.to_excel(writer, index=False, header=False, startrow=len(df) + 3)
        main_header = pd.DataFrame(get_data, columns=columns)
        main_header.to_excel(writer, index=False, header=False, startrow=len(df) + 7)
        workbook = writer.book
        worksheet = writer.sheets["Sheet1"]
        bold_format = workbook.add_format({"bold": True, "border": 1})
        for col_num, value in enumerate(columns):
            worksheet.write(len(df) + 6, col_num, value, bold_format)
        merge_format = workbook.add_format({"bg_color": "#E2F4FF", "border": 1})
        Text_for_sample_data = "[ Refernce Data ] Take the Reference of the below data to fill data in correct format :-"
        Text_for_actual_data = "[ Actual Data ] Please update the data only for the columns in the database table that need to be changed :-"
        worksheet.merge_range("A2:D2", Text_for_sample_data, merge_format)
        worksheet.merge_range("A9:D9", Text_for_actual_data, merge_format)

    buffer.seek(0)
    return buffer


def get_type_data(type_name, S):
    site_ids = S.get("assignedsites", [])
    if not isinstance(site_ids, (list, tuple)):
        site_ids = [site_ids]
    if isinstance(site_ids, (int, str)):
        site_ids = [site_ids]
    if type_name == "TYPEASSIST":
        objs = (
            ob.TypeAssist.objects.select_related("parent", "tatype", "cuser", "muser")
            .filter(
                ~Q(tacode="NONE"),
                ~Q(tatype__tacode="NONE"),
                Q(client_id=S["client_id"]),
                ~Q(client_id=1),
                enable=True,
            )
            .values_list("id", "taname", "tacode", "tatype__tacode", "client__bucode")
        )
        return list(objs)
    if type_name == "BU":
        buids = ob.Bt.objects.get_whole_tree(clientid=S["client_id"])
        objs = (
            ob.Bt.objects.select_related("parent", "identifier", "butype", "people")
            .filter(id__in=buids)
            .exclude(identifier__tacode="CLIENT")
            .annotate(
                address=F("bupreferences__address"),
                state=F("bupreferences__address2__state"),
                country=F("bupreferences__address2__country"),
                city=F("bupreferences__address2__city"),
                latlng=F("bupreferences__address2__latlng"),
                siteincharge_peoplecode=Case(
                    When(siteincharge__enable=True, then=F("siteincharge__peoplecode")),
                    default=Value(None),
                    output_field=models.CharField(),
                ),
            )
            .values_list(
                "id",
                "bucode",
                "buname",
                "parent__bucode",
                "identifier__tacode",
                "butype__tacode",
                "siteincharge_peoplecode",
                "solid",
                "enable",
                "latlng",
                "address",
                "city",
                "state",
                "country",
            )
        )
        return list(objs)
    if type_name == "LOCATION":

        class JsonSubstring(Func):
            function = "SUBSTRING"
            template = "%(function)s(%(expressions)s from '\\[(.+)\\]')"

        objs = (
            Location.objects.select_related("parent", "type", "bu")
            .filter(~Q(loccode="NONE"), bu_id__in=site_ids, client_id=S["client_id"])
            .annotate(
                gps_json=AsGeoJSON("gpslocation"),
                coordinates_str=JsonSubstring("gps_json"),
                lat=Cast(
                    Func(
                        F("coordinates_str"),
                        Value(","),
                        Value(2),
                        function="split_part",
                    ),
                    models.FloatField(),
                ),
                lon=Cast(
                    Func(
                        F("coordinates_str"),
                        Value(","),
                        Value(1),
                        function="split_part",
                    ),
                    models.FloatField(),
                ),
                coordinates=Concat(
                    Cast("lat", models.CharField()),
                    Value(", "),
                    Cast("lon", models.CharField()),
                    output_field=models.CharField(),
                ),
            )
            .values_list(
                "id",
                "loccode",
                "locname",
                "type__tacode",
                "locstatus",
                "iscritical",
                "parent__loccode",
                "bu__bucode",
                "client__bucode",
                "coordinates",
                "enable",
            )
        )
        return list(objs)
    if type_name == "ASSET":

        class JsonSubstring(Func):
            function = "SUBSTRING"
            template = "%(function)s(%(expressions)s from '\\[(.+)\\]')"

        objs = (
            Asset.objects.select_related(
                "parent",
                "type",
                "bu",
                "category",
                "subcategory",
                "brand",
                "unit",
                "servprov",
            )
            .filter(
                ~Q(assetcode="NONE"),
                bu_id__in=site_ids,
                client_id=S["client_id"],
                identifier="ASSET",
            )
            .annotate(
                gps_json=AsGeoJSON("gpslocation"),
                coordinates_str=JsonSubstring("gps_json"),
                lat=Cast(
                    Func(
                        F("coordinates_str"),
                        Value(","),
                        Value(2),
                        function="split_part",
                    ),
                    models.FloatField(),
                ),
                lon=Cast(
                    Func(
                        F("coordinates_str"),
                        Value(","),
                        Value(1),
                        function="split_part",
                    ),
                    models.FloatField(),
                ),
                coordinates=Concat(
                    Cast("lat", models.CharField()),
                    Value(", "),
                    Cast("lon", models.CharField()),
                    output_field=models.CharField(),
                ),
                ismeter=F("asset_json__ismeter"),
                isnonenggasset=F("asset_json__is_nonengg_asset"),
                meter=F("asset_json__meter"),
                model=F("asset_json__model"),
                supplier=F("asset_json__supplier"),
                invoice_no=F("asset_json__invoice_no"),
                invoice_date=F("asset_json__invoice_date"),
                service=F("asset_json__service"),
                sfdate=F("asset_json__sfdate"),
                stdate=F("asset_json__stdate"),
                yom=F("asset_json__yom"),
                msn=F("asset_json__msn"),
                bill_val=F("asset_json__bill_val"),
                bill_date=F("asset_json__bill_date"),
                purchase_date=F("asset_json__purchase_date"),
                inst_date=F("asset_json__inst_date"),
                po_number=F("asset_json__po_number"),
                far_asset_id=F("asset_json__far_asset_id"),
                capacity_val=Cast("capacity", output_field=models.CharField()),
            )
            .values_list(
                "id",
                "assetcode",
                "assetname",
                "runningstatus",
                "identifier",
                "iscritical",
                "client__bucode",
                "bu__bucode",
                "capacity_val",
                "parent__assetcode",
                "type__tacode",
                "coordinates",
                "category__tacode",
                "subcategory__tacode",
                "brand__tacode",
                "unit__tacode",
                "servprov__bucode",
                "enable",
                "ismeter",
                "isnonenggasset",
                "meter",
                "model",
                "supplier",
                "invoice_no",
                "invoice_date",
                "service",
                "sfdate",
                "stdate",
                "yom",
                "msn",
                "bill_val",
                "bill_date",
                "purchase_date",
                "inst_date",
                "po_number",
                "far_asset_id",
            )
        )
        return list(objs)
    if type_name == "VENDOR":

        class JsonSubstring(Func):
            function = "SUBSTRING"
            template = "%(function)s(%(expressions)s from '\\[(.+)\\]')"

        objs = (
            wom.Vendor.objects.select_related("parent", "type", "bu")
            .filter(~Q(code="NONE"), bu_id__in=site_ids, client_id=S["client_id"])
            .annotate(
                gps_json=AsGeoJSON("gpslocation"),
                coordinates_str=JsonSubstring("gps_json"),
                lat=Cast(
                    Func(
                        F("coordinates_str"),
                        Value(","),
                        Value(2),
                        function="split_part",
                    ),
                    models.FloatField(),
                ),
                lon=Cast(
                    Func(
                        F("coordinates_str"),
                        Value(","),
                        Value(1),
                        function="split_part",
                    ),
                    models.FloatField(),
                ),
                coordinates=Concat(
                    Cast("lat", models.CharField()),
                    Value(", "),
                    Cast("lon", models.CharField()),
                    output_field=models.CharField(),
                ),
            )
            .values_list(
                "id",
                "code",
                "name",
                "type__tacode",
                "address",
                "email",
                "show_to_all_sites",
                "mobno",
                "bu__bucode",
                "client__bucode",
                "coordinates",
                "enable",
            )
        )
        return list(objs)
    if type_name == "PEOPLE":
        if S["is_admin"]:

            class FormatListAsString(Func):
                function = "REPLACE"
                template = "(%(function)s(%(function)s(%(function)s(%(function)s(CAST(%(expressions)s AS VARCHAR), '[', ''), ']', ''), '''', ''), '\"', ''))"

            objs = (
                pm.People.objects.filter(
                    ~Q(peoplecode="NONE"), bu_id__in=site_ids, client_id=S["client_id"]
                )
                .select_related(
                    "peopletype",
                    "bu",
                    "client",
                    "designation",
                    "department",
                    "worktype",
                    "reportto",
                )
                .annotate(
                    user_for=F("people_extras__userfor"),
                    isemergencycontact=F("people_extras__isemergencycontact"),
                    mobilecapability=FormatListAsString(
                        F("people_extras__mobilecapability")
                    ),
                    reportcapability=FormatListAsString(
                        F("people_extras__reportcapability")
                    ),
                    webcapability=FormatListAsString(F("people_extras__webcapability")),
                    portletcapability=FormatListAsString(
                        F("people_extras__portletcapability")
                    ),
                    currentaddress=F("people_extras__currentaddress"),
                    blacklist=F("people_extras__blacklist"),
                    alertmails=F("people_extras__alertmails"),
                )
                .values_list(
                    "id",
                    "peoplecode",
                    "peoplename",
                    "user_for",
                    "peopletype__tacode",
                    "loginid",
                    "gender",
                    "mobno",
                    "email",
                    "dateofbirth",
                    "dateofjoin",
                    "client__bucode",
                    "bu__bucode",
                    "designation__tacode",
                    "department__tacode",
                    "worktype__tacode",
                    "enable",
                    "reportto__peoplename",
                    "dateofreport",
                    "deviceid",
                    "isemergencycontact",
                    "mobilecapability",
                    "reportcapability",
                    "webcapability",
                    "portletcapability",
                    "currentaddress",
                    "blacklist",
                    "alertmails",
                )
            )
        else:

            class FormatListAsString(Func):
                function = "REPLACE"
                template = "(%(function)s(%(function)s(%(function)s(%(function)s(CAST(%(expressions)s AS VARCHAR), '[', ''), ']', ''), '''', ''), '\"', ''))"

            objs = (
                pm.People.objects.filter(
                    ~Q(peoplecode="NONE"),
                    client_id=S["client_id"],
                    bu_id__in=S["assignedsites"],
                )
                .select_related(
                    "peopletype",
                    "bu",
                    "client",
                    "designation",
                    "department",
                    "worktype",
                    "reportto",
                )
                .annotate(
                    user_for=F("people_extras__userfor"),
                    isemergencycontact=F("people_extras__isemergencycontact"),
                    mobilecapability=FormatListAsString(
                        F("people_extras__mobilecapability")
                    ),
                    reportcapability=FormatListAsString(
                        F("people_extras__reportcapability")
                    ),
                    webcapability=FormatListAsString(F("people_extras__webcapability")),
                    portletcapability=FormatListAsString(
                        F("people_extras__portletcapability")
                    ),
                    currentaddress=F("people_extras__currentaddress"),
                    blacklist=F("people_extras__blacklist"),
                    alertmails=F("people_extras__alertmails"),
                )
                .values_list(
                    "id",
                    "peoplecode",
                    "peoplename",
                    "user_for",
                    "peopletype__tacode",
                    "loginid",
                    "gender",
                    "mobno",
                    "email",
                    "dateofbirth",
                    "dateofjoin",
                    "client__bucode",
                    "bu__bucode",
                    "designation__tacode",
                    "department__tacode",
                    "worktype__tacode",
                    "enable",
                    "reportto__peoplename",
                    "dateofreport",
                    "deviceid",
                    "isemergencycontact",
                    "mobilecapability",
                    "reportcapability",
                    "webcapability",
                    "portletcapability",
                    "currentaddress",
                    "blacklist",
                    "alertmails",
                )
            )
        return list(objs)
    if type_name == "QUESTION":
        objs = (
            Question.objects.select_related("unit", "category", "client")
            .filter(
                client_id=S["client_id"],
            )
            .annotate(
                alert_above=Case(
                    When(
                        alerton__startswith="<",
                        then=Substr(
                            "alerton", 2, StrIndex(Substr("alerton", 2), Value(",")) - 1
                        ),
                    ),
                    When(
                        alerton__contains=",<",
                        then=Substr("alerton", StrIndex("alerton", Value(",<")) + 2),
                    ),
                    default=Value("NONE"),
                    output_field=models.CharField(),
                ),
                alert_below=Case(
                    When(
                        alerton__contains=">",
                        then=Substr("alerton", StrIndex("alerton", Value(">")) + 1),
                    ),
                    default=Value("NONE"),
                    output_field=models.CharField(),
                ),
                min_str=Cast("min", output_field=models.CharField()),
                max_str=Cast("max", output_field=models.CharField()),
            )
            .values_list(
                "id",
                "quesname",
                "answertype",
                "min_str",
                "max_str",
                "alert_above",
                "alert_below",
                "isworkflow",
                "options",
                "alerton",
                "enable",
                "isavpt",
                "avpttype",
                "client__bucode",
                "unit__tacode",
                "category__tacode",
            )
        )
        return list(objs)
    if type_name == "QUESTIONSET":
        objs = (
            QuestionSet.objects.filter(
                Q(type="RPCHECKLIST") & Q(bu_id__in=S["assignedsites"])
                | (
                    Q(parent_id=1)
                    & ~Q(qsetname="NONE")
                    & Q(bu_id__in=site_ids)
                    & Q(client_id=S["client_id"])
                )
            )
            .select_related("parent")
            .values(
                "id",
                "seqno",
                "qsetname",
                "parent__qsetname",
                "type",
                "assetincludes",
                "buincludes",
                "bu__bucode",
                "client__bucode",
                "site_grp_includes",
                "site_type_includes",
                "show_to_all_sites",
                "url",
            )
        )

        # Convert the queryset to a list
        objs_list = list(objs)

        # Create mappings for asset codes, BU codes, site group names, and site type names
        asset_ids = set()
        bu_ids = set()
        site_group_ids = set()
        site_type_ids = set()

        for obj in objs_list:
            # Validate and collect asset IDs
            if obj["assetincludes"]:
                asset_ids.update(
                    str(asset_id)
                    for asset_id in obj["assetincludes"]
                    if str(asset_id).isdigit()
                )

            # Validate and collect BU IDs
            if obj["buincludes"]:
                bu_ids.update(
                    str(bu_id) for bu_id in obj["buincludes"] if str(bu_id).isdigit()
                )

            # Validate and collect site group IDs
            if obj["site_grp_includes"]:
                site_group_ids.update(
                    str(group_id)
                    for group_id in obj["site_grp_includes"]
                    if str(group_id).isdigit()
                )

            # Validate and collect site type IDs
            if obj["site_type_includes"]:
                site_type_ids.update(
                    str(type_id)
                    for type_id in obj["site_type_includes"]
                    if str(type_id).isdigit()
                )

        # Fetch asset codes
        asset_codes = Asset.objects.filter(id__in=asset_ids).values_list(
            "id", "assetcode"
        )
        asset_code_map = {str(asset_id): code for asset_id, code in asset_codes}

        # Fetch BU codes
        bu_codes = ob.Bt.objects.filter(id__in=bu_ids).values_list("id", "bucode")
        bu_code_map = {str(bu_id): code for bu_id, code in bu_codes}

        # Fetch site group names
        site_group_names = pm.Pgroup.objects.filter(id__in=site_group_ids).values_list(
            "id", "groupname"
        )
        site_group_map = {str(group_id): name for group_id, name in site_group_names}

        # Fetch site type names
        site_type_names = ob.TypeAssist.objects.filter(
            id__in=site_type_ids
        ).values_list("id", "taname")
        site_type_map = {str(type_id): name for type_id, name in site_type_names}

        # Update the lists in the original objects
        for obj in objs_list:
            # Update assetincludes
            if obj["assetincludes"]:
                obj["assetincludes"] = ",".join(
                    asset_code_map.get(str(asset_id), "")
                    for asset_id in obj["assetincludes"]
                    if str(asset_id) in asset_code_map
                )
            else:
                obj["assetincludes"] = ""

            # Update buincludes
            if obj["buincludes"]:
                obj["buincludes"] = ",".join(
                    bu_code_map.get(str(bu_id), "")
                    for bu_id in obj["buincludes"]
                    if str(bu_id) in bu_code_map
                )
            else:
                obj["buincludes"] = ""

            # Update site_grp_includes
            if obj["site_grp_includes"]:
                obj["site_grp_includes"] = ",".join(
                    site_group_map.get(str(group_id), "")
                    for group_id in obj["site_grp_includes"]
                    if str(group_id) in site_group_map
                )
            else:
                obj["site_grp_includes"] = ""

            # Update site_type_includes
            if obj["site_type_includes"]:
                obj["site_type_includes"] = ",".join(
                    site_type_map.get(str(type_id), "")
                    for type_id in obj["site_type_includes"]
                    if str(type_id) in site_type_map
                )
            else:
                obj["site_type_includes"] = ""

        # Resulting objs_list with modified fields
        # output = objs_list

        fields = [
            "id",
            "seqno",
            "qsetname",
            "parent__qsetname",
            "type",
            "assetincludes",
            "buincludes",
            "bu__bucode",
            "client__bucode",
            "site_grp_includes",
            "site_type_includes",
            "show_to_all_sites",
            "url",
        ]

        output = [tuple(obj[field] for field in fields) for obj in objs_list]
        return output
    if type_name == "QUESTIONSETBELONGING":
        objs = (
            QuestionSetBelonging.objects.select_related(
                "qset", "question", "client", "bu"
            )
            .filter(
                bu_id__in=site_ids,
                client_id=S["client_id"],
            )
            .annotate(
                alert_above=Case(
                    When(
                        alerton__startswith="<",
                        then=Substr(
                            "alerton", 2, StrIndex(Substr("alerton", 2), Value(",")) - 1
                        ),
                    ),
                    When(
                        alerton__contains=",<",
                        then=Substr("alerton", StrIndex("alerton", Value(",<")) + 2),
                    ),
                    default=Value(None),
                    output_field=models.CharField(),
                ),
                alert_below=Case(
                    When(
                        alerton__contains=">",
                        then=Substr("alerton", StrIndex("alerton", Value(">")) + 1),
                    ),
                    default=Value(None),
                    output_field=models.CharField(),
                ),
                min_str=Cast("min", output_field=models.CharField()),
                max_str=Cast("max", output_field=models.CharField()),
            )
            .values_list(
                "id",
                "question__quesname",
                "qset__qsetname",
                "client__bucode",
                "bu__bucode",
                "answertype",
                "seqno",
                "isavpt",
                "min_str",
                "max_str",
                "alert_above",
                "alert_below",
                "options",
                "alerton",
                "ismandatory",
                "avpttype",
            )
        )
        return list(objs)
    if type_name == "GROUP":
        objs = (
            pm.Pgroup.objects.select_related("client", "identifier", "bu")
            .filter(
                ~Q(id=-1),
                bu_id__in=site_ids,
                identifier__tacode="PEOPLEGROUP",
                client_id=S["client_id"],
            )
            .values_list(
                "id",
                "groupname",
                "identifier__tacode",
                "client__bucode",
                "bu__bucode",
                "enable",
            )
        )
        return list(objs)
    if type_name == "GROUPBELONGING":
        objs = (
            pm.Pgbelonging.objects.select_related("pgroup", "people")
            .filter(
                bu_id__in=site_ids,
                client_id=S["client_id"],
            )
            .values_list(
                "id",
                "pgroup__groupname",
                "people__peoplecode",
                "assignsites__bucode",
                "client__bucode",
                "bu__bucode",
            )
        )
        return list(objs)
    if type_name == "SCHEDULEDTASKS":
        objs = (
            Job.objects.annotate(
                assignedto=Case(
                    When(
                        Q(pgroup_id=1) | Q(pgroup_id__isnull=True),
                        then=Concat(F("people__peoplename"), Value(" [PEOPLE]")),
                    ),
                    When(
                        Q(people_id=1) | Q(people_id__isnull=True),
                        then=Concat(F("pgroup__groupname"), Value(" [GROUP]")),
                    ),
                ),
                formatted_fromdate=Cast(
                    TruncSecond("fromdate"), output_field=models.CharField()
                ),
                formatted_uptodate=Cast(
                    TruncSecond("uptodate"), output_field=models.CharField()
                ),
                formatted_starttime=Cast(
                    TruncSecond("starttime"), output_field=models.CharField()
                ),
                formatted_endtime=Cast(
                    TruncSecond("endtime"), output_field=models.CharField()
                ),
            )
            .filter(
                ~Q(jobname="NONE") | ~Q(id=1),
                Q(parent__jobname="NONE") | Q(parent_id=1),
                bu_id__in=S["assignedsites"],
                client_id=S["client_id"],
                identifier="TASK",
            )
            .select_related("pgroup", "people", "asset", "bu", "qset", "ticketcategory")
            .values_list(
                "id",
                "jobname",
                "jobdesc",
                "cron",
                "asset__assetcode",
                "qset__qsetname",
                "people__peoplecode",
                "pgroup__groupname",
                "planduration",
                "gracetime",
                "expirytime",
                "ticketcategory__tacode",
                "formatted_fromdate",
                "formatted_uptodate",
                "scantype",
                "client__bucode",
                "bu__bucode",
                "priority",
                "seqno",
                "formatted_starttime",
                "formatted_endtime",
                "parent__jobname",
            )
        )
        return list(objs)
    if type_name == "SCHEDULEDTOURS":
        objs = (
            Job.objects.select_related(
                "pgroup", "people", "asset", "bu", "qset", "ticketcategory"
            )
            .annotate(
                assignedto=Case(
                    When(
                        Q(pgroup_id=1) | Q(pgroup_id__isnull=True),
                        then=Concat(F("people__peoplename"), Value(" [PEOPLE]")),
                    ),
                    When(
                        Q(people_id=1) | Q(people_id__isnull=True),
                        then=Concat(F("pgroup__groupname"), Value(" [GROUP]")),
                    ),
                ),
                formatted_fromdate=Cast(
                    TruncSecond("fromdate"), output_field=models.CharField()
                ),
                formatted_uptodate=Cast(
                    TruncSecond("uptodate"), output_field=models.CharField()
                ),
                formatted_starttime=Cast(
                    TruncSecond("starttime"), output_field=models.CharField()
                ),
                formatted_endtime=Cast(
                    TruncSecond("endtime"), output_field=models.CharField()
                ),
            )
            .filter(
                Q(parent__jobname="NONE") | Q(parent_id=1),
                ~Q(jobname="NONE") | ~Q(id=1),
                bu_id__in=S["assignedsites"],
                client_id=S["client_id"],
                identifier__exact="INTERNALTOUR",
                enable=True,
            )
            .values_list(
                "id",
                "jobname",
                "jobdesc",
                "cron",
                "asset__assetcode",
                "qset__qsetname",
                "people__peoplecode",
                "pgroup__groupname",
                "planduration",
                "gracetime",
                "expirytime",
                "ticketcategory__tacode",
                "formatted_fromdate",
                "formatted_uptodate",
                "scantype",
                "client__bucode",
                "bu__bucode",
                "priority",
                "seqno",
                "formatted_starttime",
                "formatted_endtime",
                "parent__jobname",
            )
        )
        return list(objs)
