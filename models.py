import typing
from typing import Dict, List, Optional, Any, NamedTuple, Annotated, Union
from typing_extensions import override, TypedDict, Self
from pydantic import BaseModel, Field, ConfigDict, ModelWrapValidatorHandler, WrapValidator, ValidatorFunctionWrapHandler, model_validator
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
    model_config = ConfigDict(extra='allow')

    @model_validator(mode="wrap")
    @classmethod
    def handle_error_gracefully(cls, data: Any, handler: ModelWrapValidatorHandler[Self]) -> Self:
        try:
            return handler(data)
        except ValidationError as err:
            return ErrorModel(classname=cls.__name__, message=str(err))

    @override
    def model_dump(self, **kwargs):
        kwargs["exclude"] = kwargs.get("exclude", []) + list(self.model_extra.keys())
        return super().model_dump(**kwargs)

    def raise_for_errors(self):

        if isinstance(self, ErrorModel):
            raise ValueError(f"Failed to validate model for class {self.classname}: {self.message}")

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

        for name, field_info in self.__class__.model_fields.items():
            full_name = f"{prefix}.{name}" if prefix else name
            value = getattr(self, name, PydanticUndefined)

            if isinstance(value, ErrorValue):
                error_fields[full_name] = {
                    "message": value.message,
                    "value": value.value,
                }

            elif isinstance(value, CustomBaseModel):
                nested_errors = value.get_error_fields(prefix=full_name)
                error_fields.update(nested_errors)

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

            elif isinstance(value, dict):
                for key, item in value.items():
                    item_name = f"{full_name}[{repr(key)}]"
                    if isinstance(item, ErrorValue):
                        error_fields[item_name] = {
                            "message": item.message,
                            "value": item.value,
                        }
                    elif isinstance(item, CustomBaseModel):
                        error_fields.update(item.get_error_fields(prefix=item_name))

        return error_fields

class ErrorModel(CustomBaseModel):
    classname: str
    message: str

class Item(CustomBaseModel):
    type: Optional[str] = None
    name: str
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
    name: str
    data: List[DataPoint] = []

class ThingStatusInfo(CustomBaseModel):
    status: str
    statusDetail: str = "NONE"
    description: Optional[str] = None

class Thing(CustomBaseModel):
    thingTypeUID: Optional[str] = None
    UID: Optional[str] = None
    label: Optional[str] = None
    bridgeUID: Optional[str] = None
    statusInfo: Optional[ThingStatusInfo] = None
    configuration: Dict[str, Any] = Field(default_factory=dict)
    properties: Dict[str, str] = Field(default_factory=dict)
    has_details: bool = True

    @property
    def get_details(self):
        return f"get_thing_details(name='{self.name}')"

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
    uid: Annotated[str, Field(required=True), WrapValidator(handle_error_gracefully)]
    name: Annotated[str, Field(required=True), WrapValidator(handle_error_gracefully)]
    label: Annotated[str, Field(required=True), WrapValidator(handle_error_gracefully)]
    description: Annotated[Optional[str], Field(default=None), WrapValidator(handle_error_gracefully)]
    synonyms: Annotated[List[str], Field(default=[]), WrapValidator(handle_error_gracefully)]
    editable: Annotated[bool, Field(default=True), WrapValidator(handle_error_gracefully)]
    
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