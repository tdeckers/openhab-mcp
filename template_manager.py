# template_manager.py
import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Union, Tuple
from datetime import datetime
from pydantic import BaseModel, Field, constr, ConfigDict
from typing_extensions import Literal
from functools import lru_cache
from packaging import version

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Version of the OpenHAB MCP server
OPENHAB_MCP_VERSION = "0.1.0"

class TemplateMetadata(BaseModel):
    """Represents metadata for a process template."""
    id: str = Field(..., description="Unique identifier for the template")
    version: constr(pattern=r'^\d+\.\d+\.\d+$')  # type: ignore
    name: str
    description: str = ""
    author: str = ""
    created: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    tags: List[str] = []
    search_terms: List[str] = Field(default_factory=list, exclude=True)


class TemplateInput(BaseModel):
    """Input parameter definition."""
    name: str
    type: Literal["string", "number", "boolean", "object", "array"]
    description: str = ""
    required: bool = True
    default: Optional[Union[str, int, bool, list, dict]] = None
    examples: Optional[List[Any]] = None


class StepFailureHandling(BaseModel):
    """Inline error handling for a step."""
    condition: str
    action: Literal["ask_user", "rollback", "abort", "continue"]
    message: str


class StepConfirmation(BaseModel):
    """Inline user confirmation within a step."""
    message: str
    required: bool = True


class TemplateStep(BaseModel):
    """A step in the template process."""
    step_id: str
    action: str
    target: Optional[str] = None
    description: str = ""
    parameters: Dict[str, Any] = Field(default_factory=dict)
    when: Optional[str] = None  # Optional condition for step execution
    on_fail: Optional[StepFailureHandling] = None
    confirmation: Optional[StepConfirmation] = None


class TemplateExample(BaseModel):
    """Example usage of the template."""
    name: str
    description: str = ""
    input: Dict[str, Any]
    expected_output: Dict[str, Any]


class ProcessTemplate(BaseModel):
    """Complete process template model."""
    model_config = ConfigDict(extra='forbid')

    metadata: TemplateMetadata
    requires: List[Union[str, Dict[str, str]]] = []
    input: List[TemplateInput] = []
    steps: List[TemplateStep]
    examples: List[TemplateExample] = []

    @classmethod
    def from_json(cls, json_content: str) -> 'ProcessTemplate':
        data = json.loads(json_content)
        return cls(**data)

    def to_json(self, **kwargs) -> str:
        return self.model_dump_json(exclude_none=True, **kwargs)

class TemplateManager:
    """Manages process templates including loading, searching, and validation.
    
    Templates are loaded from two locations:
    1. Standard templates from the templates directory
    2. Override templates from the override directory (overrides standard templates with same ID)
    """
    
    def __init__(self, templates_dir: str = None, override_dir: str = None):
        """
        Initialize the TemplateManager.
        
        Args:
            templates_dir: Directory containing standard template files. 
                         Defaults to 'process_templates' in the current directory.
            override_dir: Directory containing override template files.
                        Defaults to 'process_templates/overrides' in the current directory.
        """
        self.templates_dir = templates_dir or os.path.join(os.path.dirname(__file__), 'process_templates')
        self.override_dir = override_dir or os.path.join(os.path.dirname(__file__), 'process_templates', 'overrides')
        self.templates_cache: Dict[str, ProcessTemplate] = {}
        self.search_index: Dict[str, Dict[str, Any]] = {}
        self._load_templates()
    
    @staticmethod
    def _parse_version(version_str: str) -> Tuple[int, int, int]:
        """Parse a version string into a tuple of integers for comparison."""
        try:
            return tuple(map(int, version_str.split('.')))
        except (ValueError, AttributeError):
            return (0, 0, 0)
    
    def check_version_requirement(self, required_version: Optional[str]) -> Tuple[bool, str]:
        """
        Check if the current version meets the required version.
        
        Args:
            required_version: Version requirement string (e.g., '>=0.5.0' or '1.0.0')
            
        Returns:
            Tuple of (is_compatible, message)
        """
        if not required_version:
            return True, ""
            
        try:
            # Remove any comparison operators for parsing
            version_str = required_version.lstrip('<=>~!=')
            
            # Check if version string is valid
            version.parse(version_str)
            
            # If we get here, version string is valid
            # For now, just log the requirement without enforcing it
            logger.info(f"Version requirement: {required_version}")
            return True, f"Version requirement: {required_version}"
            
        except version.InvalidVersion as e:
            logger.warning(f"Invalid version string in template: {e}")
            # For invalid versions, log a warning but don't block loading
            return True, f"Version requirement not enforced: {required_version}"
    
    def _load_template_file(self, file_path: Path) -> Optional[ProcessTemplate]:
        """Load and validate a single template file."""
        try:
            logger.debug(f"Loading template from {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    template_data = json.load(f)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in template {file_path}: {e}")
                    return None
            
            # Check version requirement before parsing
            if req_version := template_data.get('requires', []):
                for req in req_version:
                    if isinstance(req, dict) and 'mcp_version' in req:
                        is_compatible, message = self.check_version_requirement(req['mcp_version'])
                        if not is_compatible:
                            logger.warning(f"Skipping template {file_path.name}: {message}")
                            return None
            
            # Parse and validate template using Pydantic model
            template = ProcessTemplate(**template_data)
            logger.debug(f"Successfully loaded template: {file_path.name}")
            return template
            
        except Exception as e:
            logger.error(f"Error loading template {file_path}: {e}", exc_info=True)
            return None
    
    def _load_templates_from_dir(self, directory: Path) -> Dict[str, ProcessTemplate]:
        """Load all templates from a directory."""
        templates = {}
        
        if not directory.exists():
            logger.warning(f"Template directory does not exist: {directory}")
            return templates
        
        for file_path in directory.glob('*.json'):
            if template := self._load_template_file(file_path):
                template_id = template.metadata.id
                if template_id in templates:
                    logger.warning(f"Duplicate template ID '{template_id}' in {file_path}")
                    continue
                templates[template_id] = template
                self._add_to_search_index(template_id, template)
        
        return templates
    
    def _load_templates(self) -> None:
        """Load all templates from both standard and override directories."""
        try:
            # Clear existing data
            self.templates_cache.clear()
            self.search_index.clear()
            
            # Ensure override directory exists
            override_path = Path(self.override_dir)
            override_path.mkdir(parents=True, exist_ok=True)
            
            # Load standard templates first
            standard_templates = self._load_templates_from_dir(Path(self.templates_dir))
            
            # Load override templates (will override standard ones with same ID)
            override_templates = self._load_templates_from_dir(override_path)
            
            # Merge templates (overrides take precedence)
            self.templates_cache = {**standard_templates, **override_templates}
            
            # Rebuild search index
            for template_id, template in self.templates_cache.items():
                self._add_to_search_index(template_id, template)
            
            logger.info(f"Loaded {len(self.templates_cache)} templates "
                       f"({len(standard_templates)} standard, "
                       f"{len(override_templates)} overrides, "
                       f"{len(override_templates) - len(set(standard_templates) & set(override_templates))} custom)")
            
        except Exception as e:
            logger.error(f"Error loading templates: {e}")
    
    def _add_to_search_index(self, template_id: str, template: ProcessTemplate) -> None:
        """Add a template to the search index."""
        search_terms = set()
        
        # Add metadata fields to search index
        metadata = template.metadata.model_dump(exclude={'search_terms'}, exclude_none=True)
        for field in ['name', 'description', 'tags']:
            if field in metadata and metadata[field]:
                if isinstance(metadata[field], str):
                    search_terms.update(self._tokenize_text(str(metadata[field])))
                elif isinstance(metadata[field], list):
                    for item in metadata[field]:
                        search_terms.update(self._tokenize_text(item))
        
        # Add any explicit search terms
        if template.metadata.search_terms:
            for term in template.metadata.search_terms:
                search_terms.update(self._tokenize_text(term))
        
        self.search_index[template_id] = {
            'terms': search_terms,
            'metadata': metadata
        }
    
    @lru_cache(maxsize=1000)
    def _tokenize_text(self, text: str) -> Set[str]:
        """Tokenize text for search indexing."""
        if not text:
            return set()
        
        # Convert to lowercase and split into words
        words = re.findall(r'\b\w+\b', text.lower())
        # Remove common stop words (simplified)
        stop_words = {'the', 'and', 'or', 'in', 'on', 'at', 'for', 'to', 'of', 'a', 'an'}
        return {word for word in words if word not in stop_words and len(word) > 2}
    
    def search_templates(
        self,
        query: str = "",
        tags: List[str] = None,
        limit: int = 10,
        min_relevance: float = 0.1
    ) -> List[Dict[str, Any]]:
        """
        Search for templates matching the query and optional tags.
        
        Args:
            query: Search query string
            tags: Optional list of tags to filter by
            limit: Maximum number of results to return
            min_relevance: Minimum relevance score (0.0 to 1.0)
            
        Returns:
            List of template search results sorted by relevance
        """
        if not query and not tags:
            return []
            
        query_terms = self._tokenize_text(query) if query else set()
        results = []
        
        for template_id, index_data in self.search_index.items():
            if template_id not in self.templates_cache:
                continue
                
            # Check tag filter
            if tags:
                template_tags = set(index_data['metadata'].get('tags', []))
                if not any(tag.lower() in {t.lower() for t in template_tags} for tag in tags):
                    continue
            
            # Calculate relevance score
            score = 0.0
            matched_terms = []
            
            # Match query terms
            if query_terms:
                matched_terms = [term for term in query_terms if term in index_data['terms']]
                if matched_terms:
                    # Simple TF-IDF like scoring
                    score = len(matched_terms) / len(query_terms)
                    
                    # Boost score if query matches template name exactly
                    if 'name' in index_data['metadata']:
                        name_terms = set(self._tokenize_text(index_data['metadata']['name']))
                        if query_terms.issubset(name_terms):
                            score = min(1.0, score + 0.3)
            
            # Include templates that match tags even with no query terms
            if tags and not query_terms:
                score = 0.5  # Base score for tag-only matches
                
            if score >= min_relevance:
                results.append({
                    'template_id': template_id,
                    'name': index_data['metadata'].get('name', 'Unnamed Template'),
                    'description': index_data['metadata'].get('description', ''),
                    'relevance_score': min(1.0, score),  # Cap at 1.0
                    'match_type': 'metadata' if query_terms else 'tag',
                    'matched_terms': matched_terms,
                    'metadata': index_data['metadata']
                })
        
        # Sort by relevance score (descending)
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        return results[:limit]
    
    def get_template(self, template_id: str) -> Optional[ProcessTemplate]:
        """
        Get a template by ID.
        
        Args:
            template_id: ID of the template to retrieve
            
        Returns:
            The template if found, None otherwise
        """
        return self.templates_cache.get(template_id)
    
    def reload_templates(self) -> None:
        """Reload all templates from disk."""
        self.templates_cache.clear()
        self.search_index.clear()
        self._load_templates()
        self._tokenize_text.cache_clear()

    def save_override_template(self, template: ProcessTemplate) -> bool:
        """
        Save a template to the override directory.
        
        Args:
            template: The template to save
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Ensure override directory exists
            os.makedirs(self.override_dir, exist_ok=True)
            
            # Create filename from template ID
            filename = f"{template.metadata.id}.json"
            filepath = os.path.join(self.override_dir, filename)
            
            # Write template as JSON
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(template.to_json(indent=2))
                
            # Reload templates to update cache
            self.reload_templates()
            return True
            
        except Exception as e:
            logger.error(f"Error saving template: {e}")
            return False
    
    def delete_override_template(self, template_id: str) -> bool:
        """
        Delete a template from the override directory.
        
        Args:
            template_id: ID of the template to delete
            
        Returns:
            bool: True if deleted or didn't exist, False on error
        """
        try:
            override_path = Path(self.override_dir)
            filepath = os.path.join(self.override_dir, f"{template_id}.json")
            
            if os.path.exists(filepath):
                os.remove(filepath)
                logger.info(f"Deleted override template: {filepath}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error deleting override template {template_id}: {e}")
            return False

# Example usage
if __name__ == "__main__":
    # Set up basic logging
    logging.basicConfig(level=logging.INFO)
    
    # Initialize template manager
    manager = TemplateManager()
    
    # List all templates
    print("\nAll templates:")
    for template_id in manager.templates_cache:
        print(f"- {template_id}")
    
    # Search for templates
    print("\nSearch results for 'thing':")
    results = manager.search_templates("duplicate inbox thing")
    for result in results:
        print(f"Found template: {result['name']} (score: {result['relevance_score']:.2f})")
    
    # Get a specific template
    if results:
        template = manager.get_template(results[0]['template_id'])
        if template:
            print(f"\nTemplate details:")
            print(f"Name: {template.metadata.name}")
            print(f"Description: {template.metadata.description}")
            print(f"Version: {template.metadata.version}")
            print(f"Steps: {len(template.steps)} steps defined")