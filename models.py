from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Item(BaseModel):
    type: str = "String"
    name: str
    state: Optional[str] = None
    label: Optional[str] = None
    tags: List[str] = []
    groupNames: List[str] = []


class ThingStatusInfo(BaseModel):
    status: str
    statusDetail: str = "NONE"
    description: Optional[str] = None


class Channel(BaseModel):
    """OpenHAB Channel model"""

    uid: str
    id: str
    channelTypeUID: Optional[str] = None
    label: Optional[str] = None
    description: Optional[str] = None
    configuration: Dict[str, Any] = Field(default_factory=dict)
    properties: Dict[str, str] = Field(default_factory=dict)
    defaultTags: List[str] = Field(default_factory=list)
    kind: Optional[str] = None  # "STATE" or "TRIGGER"
    acceptedItemType: Optional[str] = None


class Thing(BaseModel):
    thingTypeUID: str
    UID: str
    label: Optional[str] = None
    bridgeUID: Optional[str] = None
    configuration: Dict[str, Any] = Field(default_factory=dict)
    properties: Dict[str, str] = Field(default_factory=dict)
    statusInfo: Optional[ThingStatusInfo] = None
    channels: List[Channel] = Field(default_factory=list)


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


class ItemChannelLinkDTO(BaseModel):
    """Basic item-channel link data for create/update operations"""

    itemName: str
    channelUID: str
    configuration: Dict[str, Any] = Field(default_factory=dict)


class EnrichedItemChannelLinkDTO(BaseModel):
    """Enriched item-channel link data returned by GET operations"""

    itemName: str
    channelUID: str
    configuration: Dict[str, Any] = Field(default_factory=dict)
    editable: bool = True


class ConfigStatusMessage(BaseModel):
    """Configuration status message"""

    parameterName: str
    type: str  # e.g., "PENDING", "ERROR", "WARNING", "INFORMATION"
    message: str
    statusCode: Optional[int] = None


class ThingDTO(BaseModel):
    """Thing data for create/update operations"""

    thingTypeUID: str
    UID: str
    label: Optional[str] = None
    bridgeUID: Optional[str] = None
    configuration: Dict[str, Any] = Field(default_factory=dict)
    properties: Dict[str, str] = Field(default_factory=dict)
    channels: List[Channel] = Field(default_factory=list)
    location: Optional[str] = None
    editable: bool = True


class FirmwareStatusDTO(BaseModel):
    """Firmware status information"""

    status: str
    updatable: bool = False
    version: Optional[str] = None
    targetVersion: Optional[str] = None


class FirmwareDTO(BaseModel):
    """Firmware information"""

    thingTypeUID: str
    vendor: str
    model: str
    description: Optional[str] = None
    version: str
    prerequisiteVersion: Optional[str] = None
    changelog: Optional[str] = None
    onlineChangelog: Optional[str] = None
    properties: Dict[str, str] = Field(default_factory=dict)


class PaginationInfo(BaseModel):
    """Information describing a paginated collection."""

    total_elements: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool


class PaginatedItems(BaseModel):
    """Paginated response wrapper for items."""

    items: List[Item]
    pagination: PaginationInfo


class PaginatedThings(BaseModel):
    """Paginated response wrapper for things."""

    things: List[Thing]
    pagination: PaginationInfo
