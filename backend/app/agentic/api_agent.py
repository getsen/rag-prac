"""
API-based agent that calls external APIs as tools.
Uses the agentic reasoning loop to decide which API to call and how.
"""

import logging
from typing import Any, Dict
from app.agentic.base import AgenticBase
from app.agentic.external_api_tools import get_api_tools
from app.agentic.tool_definitions import get_tool_definition, get_all_tool_definitions
from app.agentic.parameter_collector import ParameterCollector

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
        self.parameter_collector = ParameterCollector()  # For managing missing parameters
    
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
    
    def extract_parameters_from_query(self, tool_name: str, query: str) -> Dict[str, Any]:
        """
        Extract parameters for a tool from user query using LLM.
        
        Args:
            tool_name: Name of the tool
            query: User query text
            
        Returns:
            Dictionary of extracted parameters
        """
        tool_def = get_tool_definition(tool_name)
        if not tool_def or not tool_def.get_required_parameters():
            return {}
        
        # Build extraction prompt
        params_desc = "\n".join([
            f"- {p.name}: {p.description}"
            for p in tool_def.get_required_parameters()
        ])
        
        extraction_prompt = f"""Extract parameters for the tool '{tool_name}' from the user query.

User Query: {query}

Required Parameters:
{params_desc}

Extract and return the parameters as JSON. If a parameter is not found in the query, omit it.
Only return the JSON object with extracted parameters, nothing else.
Example format: {{"user_id": "user1"}}"""
        
        try:
            response_chunks = []
            from app.llm.ollama.ollama_client_stream import ollama_generate_stream
            
            for chunk in ollama_generate_stream(
                model=self.model,
                prompt=extraction_prompt,
                temperature=0.1,  # Low temperature for accurate extraction
            ):
                response_chunks.append(chunk)
            
            response = "".join(response_chunks).strip()
            
            # Try to parse JSON response
            import json
            # Extract JSON from response (may contain extra text)
            start_idx = response.find("{")
            end_idx = response.rfind("}") + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                extracted = json.loads(json_str)
                logger.info(f"Extracted parameters for '{tool_name}': {extracted}")
                return extracted
            
            logger.warning(f"Could not extract JSON from LLM response: {response}")
            return {}
            
        except Exception as e:
            logger.error(f"Error extracting parameters: {str(e)}")
            return {}
    
    def validate_and_collect_parameters(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        query: str,
    ) -> tuple[bool, Dict[str, Any], str]:
        """
        Validate parameters for a tool and collect missing ones.
        
        Args:
            tool_name: Name of the tool
            tool_input: Parameters provided in Action Input
            query: Original user query
            
        Returns:
            Tuple of (parameters_available, collected_params, user_prompt)
            - If parameters_available is True, tool can execute
            - If False, user_prompt contains message asking for missing info
        """
        tool_def = get_tool_definition(tool_name)
        if not tool_def:
            return False, tool_input, f"Tool '{tool_name}' not found"
        
        # First try to extract parameters from the query
        extracted = self.extract_parameters_from_query(tool_name, query)
        provided = {**tool_input, **extracted}  # Merge with provided params
        
        # Validate parameters
        is_valid, missing = tool_def.validate_parameters(provided)
        
        if is_valid:
            return True, provided, ""
        
        # Parameters missing - start collection
        has_all, prompt = self.parameter_collector.start_collection(
            tool_name=tool_name,
            provided_parameters=provided,
            context={"original_query": query},
        )
        
        logger.info(
            f"Missing parameters for '{tool_name}': {missing}. "
            f"Prompting user for: {prompt}"
        )
        
        return has_all, provided, prompt
    
    def process_parameter_response(
        self,
        user_response: str,
    ) -> tuple[bool, Dict[str, Any], str]:
        """
        Process user's response to a parameter request.
        
        Args:
            user_response: User's response text
            
        Returns:
            Tuple of (parameters_complete, collected_params, next_prompt)
        """
        if not self.parameter_collector.get_pending_tool():
            return False, {}, "No pending parameter collection"
        
        # Extract parameters from user response
        tool_name = self.parameter_collector.get_pending_tool()
        extracted = self.extract_parameters_from_query(tool_name, user_response)
        
        # Add to collector
        has_all, prompt = self.parameter_collector.add_parameters(
            user_response=user_response,
            extracted_params=extracted,
        )
        
        if has_all:
            params = self.parameter_collector.get_collected_parameters()
            self.parameter_collector.reset()
            return True, params, ""
        
        return False, {}, prompt
    
    def validate_tool_parameters(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        query: str,
    ) -> tuple[bool, Dict[str, Any], str]:
        """
        Override to validate and collect parameters for API tools.
        
        Args:
            tool_name: Name of the tool
            tool_input: Parameters provided in Action Input
            query: Original user query
            
        Returns:
            Tuple of (parameters_valid, parameters_dict, error_or_prompt)
        """
        params_available, collected_params, prompt = self.validate_and_collect_parameters(
            tool_name=tool_name,
            tool_input=tool_input,
            query=query,
        )
        
        return params_available, collected_params, prompt
    
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
