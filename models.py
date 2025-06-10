import re
from enum import Enum
from typing import Dict, List, Optional, Any, NamedTuple, Annotated
from typing_extensions import override, TypedDict, Self
from pydantic import (
    BaseModel, 
    Field, 
    ConfigDict, 
    ModelWrapValidatorHandler, 
    WrapValidator, 
    ValidatorFunctionWrapHandler, 
    model_validator
)
from pydantic_core import ValidationError, PydanticUndefined

def handle_error_gracefully(value: Any, handler: ValidatorFunctionWrapHandler) -> Optional[Any]:
    try:
        return handler(value)
    except ValidationError as err:
        return ErrorValue(value=value, message=str(err))

class ErrorValue(BaseModel):
    value: Any
    message: str

class CustomBaseModel(BaseModel):
    model_config = ConfigDict(extra="allow")
    
    def after_model_validations(self) -> Self:
        return self

    @model_validator(mode="wrap")
    @classmethod
    def handle_error_gracefully(cls, data: Any, handler: ModelWrapValidatorHandler[Self]) -> Self:
        try:
            if hasattr(cls, 'prepare_data'):
                data = cls.prepare_data(data)
            model = handler(data)
            model.after_model_validations()
            return model
        except (Exception) as err:
            error = ErrorModel(classname=cls.__name__, message=f"Input validation failed: {str(err)}", errors=[])
            if isinstance(err, ValidationError):
                for validation_error in err.errors():
                    error.errors.append(ErrorValue(value=validation_error['input'], message=validation_error['msg']))
            return error

    @override
    def model_dump(self, **kwargs):
        if hasattr(self, 'model_extra') and self.model_extra:
            kwargs["exclude"] = kwargs.get("exclude", []) + list(self.model_extra.keys())
        return super().model_dump(**kwargs)

    def raise_for_errors(self):

        if isinstance(self, ErrorModel):
            messages = []
            if self.errors:
                for error in self.errors:
                    messages.append(f"{self.message} in class {self.classname}: {error.value}: {error.message}")
            else:
                messages.append(f"Failed to validate model for class {self.classname}: {self.message}")
            raise ValueError("\n".join(messages))

        errors = self.get_error_fields()
        extra = list(self.model_extra.keys())

        if errors or extra:
            messages = []

            for field, info in errors.items():
                messages.append(f"Field error for {field}: {info['message']} (value: {repr(info['value'])})")

            for key in extra:
                messages.append(f"Unexpected extra field: {key}")

            raise ValueError("\n".join(messages))

    def get_error_fields(self, prefix="") -> dict[str, dict[str, Any]]:
        error_fields = {}

        # Check if this is an ErrorModel
        if hasattr(self, 'classname') and hasattr(self, 'message'):
            error_fields[prefix or 'error'] = {
                "message": self.message,
                "value": None
            }
            return error_fields

        for name, field_info in self.__class__.model_fields.items():
            full_name = f"{prefix}.{name}" if prefix else name
            value = getattr(self, name, PydanticUndefined)

            # Skip None values and undefined fields
            if value is None or value is PydanticUndefined:
                continue

            # Handle ErrorValue
            if isinstance(value, ErrorValue):
                error_fields[full_name] = {
                    "message": value.message,
                    "value": value.value,
                }
            # Handle nested CustomBaseModel instances (including ErrorModel)
            elif isinstance(value, CustomBaseModel):
                nested_errors = value.get_error_fields(prefix=full_name)
                error_fields.update(nested_errors)

            # Handle lists/tuples
            elif isinstance(value, (list, tuple)) and not isinstance(value, str):
                for idx, item in enumerate(value):
                    item_name = f"{full_name}[{idx}]"
                    if isinstance(item, ErrorValue):
                        error_fields[item_name] = {
                            "message": item.message,
                            "value": item.value,
                        }
                    elif isinstance(item, CustomBaseModel):
                        error_fields.update(item.get_error_fields(prefix=item_name))

            # Handle dictionaries
            elif isinstance(value, dict):
                for key, item in value.items():
                    item_name = f"{full_name}[{key}]"
                    if isinstance(item, ErrorValue):
                        error_fields[item_name] = {
                            "message": item.message,
                            "value": item.value,
                        }
                    elif isinstance(item, CustomBaseModel):
                        error_fields.update(item.get_error_fields(prefix=item_name))

        return error_fields

class ErrorModel(CustomBaseModel):
    classname: Annotated[str, Field(required=True)]
    message: Annotated[str, Field(required=True)]
    errors: Annotated[Optional[List[ErrorValue]], Field(required=False, default_factory=list)]

class TagCategoryEnum(str, Enum):
    equipment = 'Equipment'
    point = 'Point'
    location = 'Location'
    property = 'Property'

class Tag(CustomBaseModel):
    uid: Annotated[str, Field(required=True), WrapValidator(handle_error_gracefully)]
    category: Annotated[TagCategoryEnum, Field(required=False, default=None), WrapValidator(handle_error_gracefully)]
    parentuid: Annotated[Optional[str], Field(required=False, default=None), WrapValidator(handle_error_gracefully)]
    name: Annotated[str, Field(required=False, default=None), WrapValidator(handle_error_gracefully)]
    label: Annotated[str, Field(required=True, default=""), WrapValidator(handle_error_gracefully)]
    description: Annotated[Optional[str], Field(required=False, default=None), WrapValidator(handle_error_gracefully)]
    synonyms: Annotated[List[str], Field(required=False, default_factory=list), WrapValidator(handle_error_gracefully)]
    
    @classmethod
    def prepare_data(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if data.get('uid'):
                if not data.get('parentuid'):
                    match = re.match(r".*(?=_)", data['uid'])
                    if match:
                        parentuid = match.group()
                        data.update({'parentuid': parentuid})
                
                if not data.get('category'):
                    match = re.match(r"^.*?(?=_)", data['uid'])
                    if match:
                        category = match.group()
                    else:
                        category = data['uid']
                    data.update({'category': category})
                
                if "_" in data['uid'] and not data.get('name'):
                    data.update({'name': data['uid'].split('_')[-1]})
                elif "_" not in data['uid'] and not data.get('name'):
                    data.update({'name': data['uid']})
        return data

    @override
    def after_model_validations(self) -> Self:
        if self.category and not isinstance(self.category, TagCategoryEnum):
            raise ValueError("Tag 'category' must be a valid TagCategoryEnum (one of Equipment, Point, Location, Property).")
        if self.parentuid and self.category and not self.parentuid.startswith((self.category.value)):
            raise ValueError("Tag 'parentuid' must start with the tag category.")
        if self.parentuid and self.parentuid.endswith('_'):
            raise ValueError("Tag 'parentuid' must not end with '_'.")
        if self.parentuid and self.parentuid + "_" + self.name != self.uid:
            raise ValueError("Tag 'uid' must be a concatenation of 'parentuid' and 'name' separated by an underscore.")
        return self

class ItemMetadata(CustomBaseModel):
    value: str = " "
    config: Optional[Dict[str, Any]] = None

class CommandOptions(TypedDict):
    command: str
    label: str

class CommandDescription(CustomBaseModel):
    commandOptions: List[CommandOptions] = Field(default_factory=list)

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

class Item(CustomBaseModel):
    type: Annotated[str, Field(required=True), WrapValidator(handle_error_gracefully)]
    name: Annotated[str, Field(required=True), WrapValidator(handle_error_gracefully)]
    label: Annotated[Optional[str], Field(required=False, default=None), WrapValidator(handle_error_gracefully)]
    category: Annotated[Optional[str], Field(required=False, default=None), WrapValidator(handle_error_gracefully)]
    semantic_tags: Annotated[List[Tag], Field(required=False, default_factory=list), WrapValidator(handle_error_gracefully)]
    non_semantic_tags: Annotated[List[str], Field(required=False, default_factory=list), WrapValidator(handle_error_gracefully)]
    groupNames: Annotated[List[str], Field(required=False, default_factory=list), WrapValidator(handle_error_gracefully)]
    members: Annotated[List['Item'], Field(required=False, default_factory=list), WrapValidator(handle_error_gracefully)]
    groupType: Annotated[Optional[str], Field(required=False, default=None), WrapValidator(handle_error_gracefully)]
    function: Annotated[Optional[Dict[str, Any]], Field(required=False, default_factory=dict), WrapValidator(handle_error_gracefully)]
    commandDescription: Annotated[Optional[CommandDescription], Field(required=False, default=None), WrapValidator(handle_error_gracefully)]
    stateDescription: Annotated[Optional[StateDescription], Field(required=False, default=None), WrapValidator(handle_error_gracefully)]
    unitSymbol: Annotated[Optional[str], Field(required=False, default=None), WrapValidator(handle_error_gracefully)]
    
    @override
    def after_model_validations(self) -> Self:
        if isinstance(self, Item):
            if self.name and self.name[0].isdigit():
                raise ValueError("Item 'name' may not start with a digit.")
        return self

class DataPoint(NamedTuple):
    time: int
    state: str

class ItemPersistence(CustomBaseModel):
    name: str
    data: List[DataPoint] = []

class Thing(CustomBaseModel):
    thingTypeUID: Optional[str] = None
    UID: Optional[str] = None
    label: Optional[str] = None
    bridgeUID: Optional[str] = None
    configuration: Dict[str, Any] = Field(default_factory=dict)
    properties: Dict[str, str] = Field(default_factory=dict)

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