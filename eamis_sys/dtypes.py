from typing import TypedDict, Optional
from typing_extensions import NotRequired

'''
没人问我，但你根本想不到写好Type Hint之后IDE提示多方便
'''

class LessonArrangeInfo(TypedDict):
    weekDay: int
    weekState: str
    startUnit: int
    endUnit: int
    weekStateDigest: str
    startTime: int
    endTime: int
    # 这两个键总是存在，只是可能为null
    expLessonGroup: Optional[str]
    expLessonGroupNo: Optional[int]
    roomIds: str
    rooms: str

class LessonData(TypedDict):
    id: int
    no: str
    name: str
    limitCount: int
    planLimitCount: int
    unplanLimitCount: int
    code: str
    credits: int
    courseId: int
    startWeek: int
    endWeek: int
    courseTypeId: int
    courseTypeName: str
    courseTypeCode: str
    scheduled: bool
    hasTextBook: bool
    period: int
    weekHour: int
    withdrawable: bool
    langTypeName: str
    textbooks: str
    teachers: str
    teacherIds: str
    campusCode: str
    campusName: str
    midWithdraw: str
    reservedCount: str
    remark: str
    arrangeInfo: list[LessonArrangeInfo]
    expLessonGroups: list[str]

class ExpLessonGroup(TypedDict):
    indexNo: int
    stdCount: int
    stdCountLimit: int
    proStdCountLimit: int

class StdCount(TypedDict):
    sc: int
    lc: int
    upsc: int
    uplc: int
    plc: int
    puplc: int
    # 这个键可能不存在
    expLessonGroups: NotRequired[dict[str, ExpLessonGroup]]

class ElectResultData(TypedDict):
    id: int
    virtualCost: NotRequired[int]
    preElect: bool 
    defaultElected: bool
    elected: bool
