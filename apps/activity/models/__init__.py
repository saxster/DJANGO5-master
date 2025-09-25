# Import all models to make them available when importing from this package

from .asset_model import Asset, AssetLog
from .attachment_model import Attachment
from .deviceevent_log_model import DeviceEventlog
from .job_model import Job, Jobneed, JobneedDetails
from .location_model import Location
from .question_model import Question, QuestionSet, QuestionSetBelonging

# Make all models available at package level
__all__ = [
    'Asset',
    'AssetLog', 
    'Attachment',
    'DeviceEventlog',
    'Job',
    'Jobneed',
    'JobneedDetails',
    'Location',
    'Question',
    'QuestionSet',
    'QuestionSetBelonging',
]