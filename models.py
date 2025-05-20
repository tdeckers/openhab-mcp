from typing import Dict, List, Optional, Any, NamedTuple
from pydantic import BaseModel, Field

class Item(BaseModel):
    type: str = "String"
    name: str
    state: Optional[str] = None
    label: Optional[str] = None
    tags: List[str] = []
    groupNames: List[str] = []

class DataPoint(NamedTuple):
    time: int
    state: str

class ItemPersistence(BaseModel):
    name: str
    data: List[DataPoint] = []

class ThingStatusInfo(BaseModel):
    status: str
    statusDetail: str = "NONE"
    description: Optional[str] = None

class ThingSummary(BaseModel):
    thingTypeUID: str
    UID: str
    label: Optional[str] = None
    bridgeUID: Optional[str] = None
    statusInfo: Optional[ThingStatusInfo] = None

class PaginationInfo(BaseModel):
    total_items: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool

class PaginatedThings(BaseModel):
    items: List[ThingSummary]
    pagination: PaginationInfo

class PaginatedItems(BaseModel):
    items: List[Item]
    pagination: PaginationInfo

class Thing(BaseModel):
    thingTypeUID: str
    UID: str
    label: Optional[str] = None
    bridgeUID: Optional[str] = None
    configuration: Dict[str, Any] = Field(default_factory=dict)
    properties: Dict[str, str] = Field(default_factory=dict)
    statusInfo: Optional[ThingStatusInfo] = None
    channels: List[Dict[str, Any]] = Field(default_factory=list)

class RuleStatus(BaseModel):
    status: str
    statusDetail: str = "NONE"

class RuleAction(BaseModel):
    id: str
    type: str
    configuration: Dict[str, Any] = Field(default_factory=dict)
    inputs: Dict[str, Any] = Field(default_factory=dict)

class RuleTrigger(BaseModel):
    id: str
    type: str
    configuration: Dict[str, Any] = Field(default_factory=dict)

class RuleCondition(BaseModel):
    id: str
    type: str
    configuration: Dict[str, Any] = Field(default_factory=dict)

class Rule(BaseModel):
    uid: str
    name: str
    description: Optional[str] = None
    status: Optional[RuleStatus] = None
    tags: List[str] = []
    visibility: Optional[str] = None
    editable: bool = True
    configuration: Dict[str, Any] = Field(default_factory=dict)
    configDescriptions: List[Dict[str, Any]] = Field(default_factory=list)
    triggers: List[RuleTrigger] = []
    conditions: List[RuleCondition] = []
    actions: List[RuleAction] = []
