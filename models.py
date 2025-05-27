from typing import Dict, List, Optional, Any, NamedTuple
from typing_extensions import override
from pydantic import BaseModel, Field, ConfigDict

class CustomBaseModel(BaseModel):

    model_config = ConfigDict(extra='allow')

    @override
    def model_dump(self, **kwargs):
        kwargs["exclude"] = list(kwargs.get("exclude", []) + self.model_extra.keys())
        return super().model_dump(**kwargs)


class Item(CustomBaseModel):
    model_config = ConfigDict(extra='allow')
    type: str
    name: str
    state: Optional[str] = None
    label: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = []
    groupNames: List[str] = []

class ItemDetails(Item):
    members: List[Item] = []

class DataPoint(NamedTuple):
    time: int
    state: str

class ItemPersistence(CustomBaseModel):
    name: str
    data: List[DataPoint] = []

class ThingStatusInfo(CustomBaseModel):
    status: str
    statusDetail: str = "NONE"
    description: Optional[str] = None

class Thing(CustomBaseModel):
    thingTypeUID: str
    UID: str
    label: Optional[str] = None
    bridgeUID: Optional[str] = None
    statusInfo: Optional[ThingStatusInfo] = None
    configuration: Dict[str, Any] = Field(default_factory=dict)
    properties: Dict[str, str] = Field(default_factory=dict)

class ThingDetails(Thing):
    channels: List[Dict[str, Any]] = Field(default_factory=list)

class RuleStatus(CustomBaseModel):
    status: str
    statusDetail: str = "NONE"

class RuleAction(CustomBaseModel):
    id: str
    type: str
    configuration: Dict[str, Any] = Field(default_factory=dict)
    inputs: Dict[str, Any] = Field(default_factory=dict)

class RuleTrigger(CustomBaseModel):
    id: str
    type: str
    configuration: Dict[str, Any] = Field(default_factory=dict)

class RuleCondition(CustomBaseModel):
    id: str
    type: str
    configuration: Dict[str, Any] = Field(default_factory=dict)

class Rule(CustomBaseModel):
    uid: str
    name: str
    status: Optional[RuleStatus] = None
    tags: List[str] = []
    visibility: Optional[str] = None
    editable: bool = True

class RuleDetails(Rule):
    description: Optional[str] = None
    triggers: List[RuleTrigger] = []
    conditions: List[RuleCondition] = []
    actions: List[RuleAction] = []
    configuration: Dict[str, Any] = Field(default_factory=dict)
    configDescriptions: List[Dict[str, Any]] = Field(default_factory=list)

class Tag(CustomBaseModel):
    uid: str
    name: str
    label: Optional[str] = None
    description: Optional[str] = None
    synonyms: List[str] = []
    editable: bool = True

class Link(CustomBaseModel):
    itemName: str
    channelUID: str
    configuration: Dict[str, Any] = Field(default_factory=dict)
    editable: bool = True

class PaginationInfo(CustomBaseModel):
    total_elements: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool

class PaginatedThings(CustomBaseModel):
    things: List[Thing]
    pagination: PaginationInfo

class PaginatedItems(CustomBaseModel):
    items: List[Item]
    pagination: PaginationInfo

class PaginatedRules(CustomBaseModel):
    rules: List[Rule]
    pagination: PaginationInfo

class PaginatedLinks(CustomBaseModel):
    links: List[Link]
    pagination: PaginationInfo