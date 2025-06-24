import re
from enum import Enum
from typing import Dict, List, Optional, Any
from typing_extensions import TypedDict
from pydantic import (
    BaseModel,
    Field,
    model_validator,
)

class TagCategoryEnum(str, Enum):
    equipment = 'Equipment'
    point = 'Point'
    location = 'Location'
    property = 'Property'

class Tag(BaseModel):
    uid: str = Field(..., description="Unique identifier for the tag")
    name: str = Field(..., description="Name of the tag")
    label: str = Field(..., description="Display label for the tag")
    category: Optional[TagCategoryEnum] = Field(None, description="Category of the tag")
    parentuid: Optional[str] = Field(None, description="Parent UID for hierarchical tags")
    description: Optional[str] = Field(None, description="Description of the tag")
    synonyms: List[str] = Field(default_factory=list, description="List of synonyms for the tag")
    
    @model_validator(mode='before')
    @classmethod
    def prepare_data(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
            
        data = data.copy()  # Don't modify the original data
        
        # Set parentuid from uid if not provided
        if 'uid' in data and 'parentuid' not in data and '_' in data['uid']:
            data['parentuid'] = data['uid'].rsplit('_', 1)[0]
        
        # Set category from uid if not provided
        if 'uid' in data and 'category' not in data and '_' in data['uid']:
            category = data['uid'].split('_')[0]
            try:
                data['category'] = TagCategoryEnum(category.lower())
            except ValueError:
                pass
                
        # Set name from uid if not provided
        if 'uid' in data and 'name' not in data:
            data['name'] = data['uid'].split('_')[-1]
                
        return data

    @model_validator(mode='after')
    def validate_tag(self) -> 'Tag':
        if self.parentuid and self.category and not self.parentuid.startswith(self.category.value):
            raise ValueError("Tag 'parentuid' must start with the tag category.")
            
        if self.parentuid and self.parentuid.endswith('_'):
            raise ValueError("Tag 'parentuid' must not end with '_'.")
            
        if self.parentuid and self.uid != f"{self.parentuid}_{self.name}":
            raise ValueError("Tag 'uid' must be a concatenation of 'parentuid' and 'name' separated by an underscore.")
            
        return self

class ItemMetadata(BaseModel):
    value: str = Field(" ", description="Value of the metadata")
    config: Dict[str, Any] = Field(default_factory=dict, description="Configuration of the metadata")

class ItemBase(BaseModel):
    name: Optional[str] = Field(None, description="Name of the item")
    type: Optional[str] = Field(None, description="Type of the item")
    label: Optional[str] = Field(None, description="Display label for the item")
    category: Optional[str] = Field(None, description="Category of the item")
    semantic_tags: List[str] = Field(default_factory=list, description="List of semantic tags for the item", alias="semanticTags")
    non_semantic_tags: List[str] = Field(default_factory=list, description="List of non-semantic tag UIDs for the item", alias="nonSemanticTags")
    group_type: Optional[str] = Field(None, description="Type of the group", alias="groupType")
    function: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Function of the item")
    unit_symbol: Optional[str] = Field(None, description="Unit symbol for the item", alias="unitSymbol")
    
    @model_validator(mode='after')
    def validate_item(self) -> 'ItemBase':
        if self.name and self.name[0].isdigit():
            raise ValueError("Item 'name' may not start with a digit.")
            
        return self

class ItemCreate(ItemBase):
    name: str = Field(..., description="Name of the item")
    type: str = Field(..., description="Type of the item")
    metadata: Optional[Dict[str, ItemMetadata]] = Field(default_factory=dict, description="Metadata of the item")
    group_names: List[str] = Field(default_factory=list, description="List of group names for the item", alias="groupNames")

class ItemUpdate(ItemBase):
    name: str = Field(..., description="Name of the item")

class ThingBase(BaseModel):
    UID: Optional[str] = Field(None, description="UID of the thing")
    thingTypeUID: Optional[str] = Field(None, description="Type of the thing")
    label: Optional[str] = Field(None, description="Label of the thing")
    bridgeUID: Optional[str] = Field(None, description="UID of the bridge")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="Configuration of the thing")
    properties: Dict[str, str] = Field(default_factory=dict, description="Properties of the thing")

    @model_validator(mode='after')
    def validate_thing(self) -> 'ThingBase':
        # Skip validation if we don't have both UID and thingTypeUID
        if not self.UID or not self.thingTypeUID:
            return self
            
        if self.bridgeUID:
            pattern = r"{0}:{1}:(.+)".format(
                re.escape(self.thingTypeUID), 
                re.escape(self.bridgeUID)
            )
        else:
            pattern = r"{}:(.+)".format(re.escape(self.thingTypeUID))
            
        if not re.search(pattern, self.UID):
            raise ValueError(
                "Thing UID must be in format 'binding_id:thing_type_id:thing_id' or "
                "'binding_id:thing_type_id:bridge_id:thing_id'"
            )
            
        return self

class ThingCreate(ThingBase):
    UID: str = Field(..., description="UID of the thing")
    thingTypeUID: str = Field(..., description="Type of the thing")

class ThingUpdate(ThingBase):
    UID: str = Field(..., description="UID of the thing")

class RuleBase(BaseModel):
    """Base model for Rule with all fields optional for partial updates"""
    uid: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    triggers: List[Dict[str, Any]] = Field(default_factory=list)
    conditions: List[Dict[str, Any]] = Field(default_factory=list)
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    configuration: Dict[str, Any] = Field(default_factory=dict)
    config_descriptions: List[Dict[str, Any]] = Field(default_factory=list, alias="configDescriptions")
    
class RuleCreate(RuleBase):
    """Model for creating a new rule with required fields"""
    uid: str = Field(..., description="UID of the rule")
    name: str = Field(..., description="Name of the rule")

class RuleUpdate(RuleBase):
    """Model for updating an existing rule with optional fields"""
    uid: str = Field(..., description="UID of the rule")

class RuleStatus(BaseModel):
    status: str = Field(..., description="Status of the rule")
    status_detail: str = Field(default="NONE", alias="statusDetail")

class RuleAction(BaseModel):
    id: str = Field(..., description="ID of the action")
    type: str = Field(..., description="Type of the action")
    configuration: Dict[str, Any] = Field(default_factory=dict)
    inputs: Dict[str, Any] = Field(default_factory=dict)

class RuleTrigger(BaseModel):
    id: str = Field(..., description="ID of the trigger")
    type: str = Field(..., description="Type of the trigger")
    configuration: Dict[str, Any] = Field(default_factory=dict)

class RuleCondition(BaseModel):
    id: str = Field(..., description="ID of the condition")
    type: str = Field(..., description="Type of the condition")
    configuration: Dict[str, Any] = Field(default_factory=dict)

class Link(BaseModel):
    itemName: str = Field(..., description="Name of the item")
    channelUID: str = Field(..., description="UID of the channel")
    configuration: Optional[Dict[str, Any]] = Field(default_factory=dict)
