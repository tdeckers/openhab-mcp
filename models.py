from typing import Dict, List, Optional, Any, NamedTuple
from typing_extensions import override, TypedDict
from pydantic import BaseModel, Field, ConfigDict
import random
import string


class CustomBaseModel(BaseModel):

    model_config = ConfigDict(extra='allow')

    # Never dump extra fields. We need them though to teach the LLM not to invent fields that don't exist
    @override
    def model_dump(self, **kwargs):
        kwargs["exclude"] = kwargs.get("exclude", []) + list(self.model_extra.keys())
        return super().model_dump(**kwargs)


class Item(CustomBaseModel):
    type: str
    name: str = Field(frozen=True)
    state: Optional[str] = None
    transformedState: Optional[str] = None
    label: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = []
    groupNames: List[str] = []
    has_details: bool = True

    @property
    def get_details(self):
        return f"get_item_details(name='{self.name}')"

class CommandOptions(TypedDict):
    command: str
    label: str

class CommandDescription(CustomBaseModel):
    commandOptions: List[CommandOptions]

class StateOptions(TypedDict):
    value: str
    label: str

class StateDescription(CustomBaseModel):
    minimum: Optional[int] = None
    maximum: Optional[int] = None
    step: Optional[int] = None
    pattern: Optional[str] = None
    readOnly: Optional[bool] = None
    options: Optional[List[StateOptions]] = None

class ItemMetadata(CustomBaseModel):
    value: str = " "
    config: Optional[Dict[str, Any]] = None

class ItemDetails(Item):
    members: List['ItemDetails'] = []
    metadata: Optional[Dict[str, ItemMetadata]] = None
    commandDescription: Optional[CommandDescription] = None
    stateDescription: Optional[StateDescription] = None
    unitSymbol: Optional[str] = None

class DataPoint(NamedTuple):
    time: int
    state: str

class ItemPersistence(CustomBaseModel):
    name: str = Field(frozen=True)
    data: List[DataPoint] = []

class ThingStatusInfo(CustomBaseModel):
    status: str
    statusDetail: str = "NONE"
    description: Optional[str] = None

class Thing(CustomBaseModel):
    thingTypeUID: str = Field(frozen=True)
    UID: Optional[str] = Field(frozen=True)
    label: Optional[str] = None
    bridgeUID: Optional[str] = None
    statusInfo: Optional[ThingStatusInfo] = None
    configuration: Dict[str, Any] = Field(default_factory=dict)
    properties: Dict[str, str] = Field(default_factory=dict)
    has_details: bool = True
    
    @property
    def get_details(self):
        return f"get_thing_details(name='{self.UID}')"

class ThingDetails(Thing):
    channels: List[Dict[str, Any]] = Field(default_factory=list)

class RuleStatus(CustomBaseModel):
    status: str
    statusDetail: str = "NONE"

class RuleAction(CustomBaseModel):
    id: str = Field(frozen=True)
    type: str
    configuration: Dict[str, Any] = Field(default_factory=dict)
    inputs: Dict[str, Any] = Field(default_factory=dict)

class RuleTrigger(CustomBaseModel):
    id: str = Field(frozen=True)
    type: str
    configuration: Dict[str, Any] = Field(default_factory=dict)

class RuleCondition(CustomBaseModel):
    id: str = Field(frozen=True)
    type: str
    configuration: Dict[str, Any] = Field(default_factory=dict)

class Rule(CustomBaseModel):
    uid: str = Field(frozen=True)
    name: str
    status: Optional[RuleStatus] = None
    tags: List[str] = []
    visibility: Optional[str] = None
    editable: bool = True
    has_details: bool = True
    
    @property
    def get_details(self):
        return f"get_rule_details(uid='{self.uid}')"

class RuleDetails(Rule):
    description: Optional[str] = None
    triggers: List[RuleTrigger] = []
    conditions: List[RuleCondition] = []
    actions: List[RuleAction] = []
    configuration: Dict[str, Any] = Field(default_factory=dict)
    configDescriptions: List[Dict[str, Any]] = Field(default_factory=list)

class Tag(CustomBaseModel):
    uid: str = Field(frozen=True)
    name: str
    label: Optional[str] = None
    description: Optional[str] = None
    synonyms: List[str] = []
    editable: bool = True
    
class Link(CustomBaseModel):
    itemName: str = Field(frozen=True)
    channelUID: str = Field(frozen=True)
    configuration: Dict[str, Any] = Field(default_factory=dict)
    editable: bool = True

class PaginationInfo(CustomBaseModel):
    total_elements: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool

    @property
    def next_page(self):
        return self.page + 1 if self.has_next else None

    @property
    def previous_page(self):
        return self.page - 1 if self.has_previous else None

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