from pydantic import BaseModel
from datetime import datetime, date
from typing import List


class PeopleModifiedAfterSchema(BaseModel):
    mdtz: datetime
    ctzoffset: int
    buid: int


class PeopleEventLogPunchInsSchema(BaseModel):
    datefor: date
    buid: int
    peopleid: int


class PgbelongingModifiedAfterSchema(BaseModel):
    mdtz: datetime
    ctzoffset: int
    buid: int
    peopleid: int


class PeopleEventLogHistorySchema(BaseModel):
    mdtz: datetime
    ctzoffset: int
    buid: int
    peopleid: int
    clientid: int
    peventtypeid: List[int]


class AttachmentSchema(BaseModel):
    owner: str
