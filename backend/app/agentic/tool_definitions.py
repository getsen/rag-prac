"""
Tool definitions with prerequisites and metadata.
Defines what parameters each tool requires and how to collect them.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = None  # Lazy load to avoid circular imports


@dataclass
class ToolParameter:
    """Definition of a tool parameter."""
    name: str
    type: str  # "string", "integer", "boolean", etc.
    required: bool = True
    description: str = ""
    examples: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "type": self.type,
            "required": self.required,
            "description": self.description,
            "examples": self.examples or [],
        }


@dataclass
class ToolDefinition:
    """Complete definition of a tool with prerequisites."""
    name: str
    description: str
    parameters: List[ToolParameter]
    category: str  # "user", "task", "service"
    
    def get_required_parameters(self) -> List[ToolParameter]:
        """Get list of required parameters."""
        return [p for p in self.parameters if p.required]
    
    def get_parameter_by_name(self, name: str) -> Optional[ToolParameter]:
        """Get parameter definition by name."""
        for param in self.parameters:
            if param.name == name:
                return param
        return None
    
    def validate_parameters(self, provided: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate provided parameters against definition.
        
        Returns:
            Tuple of (is_valid, list_of_missing_required_params)
        """
        missing = []
        for param in self.get_required_parameters():
            if param.name not in provided or provided[param.name] is None:
                missing.append(param.name)
        
        return len(missing) == 0, missing
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "parameters": [p.to_dict() for p in self.parameters],
            "required_parameters": [p.name for p in self.get_required_parameters()],
        }


# Tool Definitions
TOOL_DEFINITIONS: Dict[str, ToolDefinition] = {
    "list_users": ToolDefinition(
        name="list_users",
        description="List all users in the system",
        parameters=[],
        category="user",
    ),
    
    "get_user": ToolDefinition(
        name="get_user",
        description="Get detailed information about a specific user",
        parameters=[
            ToolParameter(
                name="user_id",
                type="string",
                required=True,
                description="The unique identifier of the user",
                examples=["user1", "alice", "bob123"],
            ),
        ],
        category="user",
    ),
    
    "list_tasks": ToolDefinition(
        name="list_tasks",
        description="List all tasks in the system, optionally filtered by status",
        parameters=[
            ToolParameter(
                name="status",
                type="string",
                required=False,
                description="Filter by task status (optional)",
                examples=["pending", "in_progress", "completed"],
            ),
        ],
        category="task",
    ),
    
    "get_task": ToolDefinition(
        name="get_task",
        description="Get detailed information about a specific task",
        parameters=[
            ToolParameter(
                name="task_id",
                type="string",
                required=True,
                description="The unique identifier of the task",
                examples=["task1", "task-123", "abc456"],
            ),
        ],
        category="task",
    ),
    
    "create_task": ToolDefinition(
        name="create_task",
        description="Create a new task in the system",
        parameters=[
            ToolParameter(
                name="title",
                type="string",
                required=True,
                description="Title or name of the task",
                examples=["Fix login bug", "Update documentation", "Review pull request"],
            ),
            ToolParameter(
                name="assigned_to",
                type="string",
                required=True,
                description="User ID of who the task is assigned to",
                examples=["user1", "alice", "bob123"],
            ),
        ],
        category="task",
    ),
    
    "update_task_status": ToolDefinition(
        name="update_task_status",
        description="Update the status of an existing task",
        parameters=[
            ToolParameter(
                name="task_id",
                type="string",
                required=True,
                description="The unique identifier of the task",
                examples=["task1", "task-123"],
            ),
            ToolParameter(
                name="status",
                type="string",
                required=True,
                description="New status for the task",
                examples=["pending", "in_progress", "completed"],
            ),
        ],
        category="task",
    ),
    
    "get_service_status": ToolDefinition(
        name="get_service_status",
        description="Get the status of services",
        parameters=[
            ToolParameter(
                name="service_name",
                type="string",
                required=False,
                description="Name of the specific service to check (optional, if not provided all services are listed)",
                examples=["api", "database", "cache"],
            ),
        ],
        category="service",
    ),
    
    "restart_service": ToolDefinition(
        name="restart_service",
        description="Restart a specific service",
        parameters=[
            ToolParameter(
                name="service_name",
                type="string",
                required=True,
                description="Name of the service to restart",
                examples=["api", "database", "cache"],
            ),
        ],
        category="service",
    ),
}


def get_tool_definition(tool_name: str) -> Optional[ToolDefinition]:
    """Get tool definition by name."""
    return TOOL_DEFINITIONS.get(tool_name)


def get_all_tool_definitions() -> Dict[str, ToolDefinition]:
    """Get all tool definitions."""
    return TOOL_DEFINITIONS.copy()
