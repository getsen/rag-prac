"""
API-based agent that calls external APIs as tools.
Uses the agentic reasoning loop to decide which API to call and how.
"""

import logging
from typing import Any, Dict
from app.agentic.base import AgenticBase
from app.agentic.external_api_tools import get_api_tools

logger = logging.getLogger(__name__)


class APIAgent(AgenticBase):
    """
    Agent that uses external APIs as tools.
    
    This agent can:
    - Get user information
    - List and manage tasks
    - Check and restart services
    - Reason about which API to call based on user query
    """
    
    def __init__(
        self,
        model: str = "llama2",
        temperature: float = 0.7,
        max_iterations: int = 10,
    ):
        """Initialize the API agent."""
        super().__init__(
            model=model,
            temperature=temperature,
            max_iterations=max_iterations,
        )
        self.api_tools = get_api_tools()
    
    def get_tools(self) -> Dict[str, Any]:
        """
        Get available API tools.
        
        Returns:
            Dictionary of available API tools
        """
        return {
            "list_users": self.api_tools.list_users,
            "get_user": self.api_tools.get_user,
            "list_tasks": self.api_tools.list_tasks,
            "get_task": self.api_tools.get_task,
            "create_task": self.api_tools.create_task,
            "update_task_status": self.api_tools.update_task_status,
            "get_service_status": self.api_tools.get_service_status,
            "restart_service": self.api_tools.restart_service,
        }
    
    def process_tool_result(self, tool_name: str, tool_result: Any) -> str:
        """
        Process and format API tool results for the LLM.
        
        Args:
            tool_name: Name of the tool that was called
            tool_result: Result from the API tool
            
        Returns:
            Formatted string for LLM consumption
        """
        if not isinstance(tool_result, dict):
            return str(tool_result)
        
        success = tool_result.get("success", False)
        
        if not success:
            error = tool_result.get("error", "Unknown error")
            return f"API Error: {error}"
        
        data = tool_result.get("data")
        message = tool_result.get("message", "")
        
        # Format different types of results
        if tool_name == "list_users":
            if isinstance(data, list):
                formatted = "Users found:\n"
                for user in data:
                    formatted += f"- {user.get('name')} (ID: {user.get('id')}, Role: {user.get('role')})\n"
                return formatted
        
        elif tool_name == "get_user":
            if isinstance(data, dict):
                return f"User Info:\nName: {data.get('name')}\nEmail: {data.get('email')}\nRole: {data.get('role')}"
        
        elif tool_name == "list_tasks":
            if isinstance(data, list):
                formatted = "Tasks found:\n"
                for task in data:
                    formatted += f"- {task.get('title')} (ID: {task.get('id')}, Status: {task.get('status')}, Assigned to: {task.get('assigned_to')})\n"
                return formatted
        
        elif tool_name in ["get_task", "create_task", "update_task_status"]:
            if isinstance(data, dict):
                return f"Task: {data.get('title')}\nStatus: {data.get('status')}\nAssigned to: {data.get('assigned_to')}"
        
        elif tool_name == "get_service_status":
            if isinstance(data, dict):
                # Check if it's a single service or multiple
                if "status" in data and "uptime" in data:
                    # Single service
                    return f"Service: {data.get('name')}\nStatus: {data.get('status')}\nUptime: {data.get('uptime')}\nPort: {data.get('port')}"
                else:
                    # Multiple services
                    formatted = "Service Status:\n"
                    for service_name, service_info in data.items():
                        formatted += f"- {service_info.get('name')}: {service_info.get('status')} (Uptime: {service_info.get('uptime')})\n"
                    return formatted
        
        elif tool_name == "restart_service":
            if message:
                return message
            return f"Service restarted: {data.get('name')}"
        
        # Default formatting
        if isinstance(data, dict):
            return f"Result: {str(data)}"
        elif isinstance(data, list):
            return f"Results:\n" + "\n".join(str(item) for item in data)
        
        return str(tool_result)
    
    def _build_system_prompt(self) -> str:
        """
        Build a custom system prompt for the API agent.
        
        Returns:
            System prompt with API tool descriptions
        """
        return """You are a helpful technical assistant with access to external APIs.

        Available APIs/Tools:
        1. User Management:
        - get_user: Get information about a specific user (requires user_id)
        - list_users: List all users in the system

        2. Task Management:
        - create_task: Create a new task (requires title and assigned_to)
        - get_task: Get information about a specific task (requires task_id)
        - list_tasks: List tasks, optionally filtered by status (pending, in_progress, completed)
        - update_task_status: Update a task's status (requires task_id and status)

        3. Service Management:
        - get_service_status: Get status of services (optionally specify service_name)
        - restart_service: Restart a service (requires service_name)

        Your task is to help users by:
        1. Understanding what they're asking for
        2. Deciding which API(s) to call
        3. Calling the appropriate API with correct parameters
        4. Processing and explaining the results

        Follow this format:
        Thought: What does the user need? Which API should I call?
        Action: The API tool name to use
        Action Input: The parameters as JSON {"key": "value"}

        After getting API results, continue thinking if you need more information.

        When you have the complete answer:
        Action: stop
        Final Response: Your comprehensive answer to the user based on API data

        Be helpful, clear, and accurate in your responses."""
