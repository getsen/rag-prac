"""
MCP-based API agent that uses the Model Context Protocol to call external tools.
This agent calls tools through a direct integration (no separate MCP server).
"""

import asyncio
import logging
from typing import Any, Dict
from app.agentic.base import AgenticBase
from app.agentic.parameter_collector import ParameterCollector
from app.agentic.external_api_tools import get_api_tools

logger = logging.getLogger(__name__)


class MCPAPIAgent(AgenticBase):
    """
    Agent that uses MCP tools (direct integration).
    
    This agent:
    - Uses predefined tools with MCP-compatible schemas
    - Automatically discovers available tools
    - Calls tools with proper parameter validation
    - Handles parameter collection for missing tool arguments
    """
    
    def __init__(
        self,
        model: str = "llama2",
        temperature: float = 0.7,
        max_iterations: int = 10,
    ):
        """
        Initialize the MCP API agent.
        
        Args:
            model: LLM model to use
            temperature: Temperature for LLM responses
            max_iterations: Max reasoning loop iterations
        """
        super().__init__(
            model=model,
            temperature=temperature,
            max_iterations=max_iterations,
        )
        self.api_tools = get_api_tools()
        self.parameter_collector = ParameterCollector()
        self._tools_cache: Dict[str, Any] = {}
    
    def get_tools(self) -> Dict[str, Any]:
        """
        Get available tools (cached).
        
        Returns:
            Dictionary of available tools with their metadata
        """
        if self._tools_cache:
            return self._tools_cache
        
        # Build tool definitions from API tools
        tools = {
            "list_users": {
                "name": "list_users",
                "description": "List all users in the system",
                "callable": self.api_tools.list_users,
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            "get_user": {
                "name": "get_user",
                "description": "Get information about a specific user",
                "callable": self.api_tools.get_user,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "user_id": {
                            "type": "string",
                            "description": "The user ID (e.g., 'user1')",
                        }
                    },
                    "required": ["user_id"],
                },
            },
            "create_user": {
                "name": "create_user",
                "description": "Create a new user",
                "callable": lambda **kwargs: {"success": False, "error": "Not implemented"},
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "User's name"},
                        "email": {"type": "string", "description": "User's email"},
                        "role": {"type": "string", "description": "User's role"},
                    },
                    "required": ["name", "email", "role"],
                },
            },
            "list_tasks": {
                "name": "list_tasks",
                "description": "List all tasks in the system",
                "callable": self.api_tools.list_tasks,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "description": "Filter by status",
                        },
                    },
                    "required": [],
                },
            },
            "get_task": {
                "name": "get_task",
                "description": "Get information about a specific task",
                "callable": self.api_tools.get_task,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string", "description": "The task ID"}
                    },
                    "required": ["task_id"],
                },
            },
            "create_task": {
                "name": "create_task",
                "description": "Create a new task and assign it to a user",
                "callable": self.api_tools.create_task,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Task title"},
                        "assigned_to": {
                            "type": "string",
                            "description": "User ID to assign to",
                        },
                        "description": {
                            "type": "string",
                            "description": "Task description",
                        },
                        "status": {"type": "string", "description": "Initial status"},
                    },
                    "required": ["title", "assigned_to"],
                },
            },
            "update_task_status": {
                "name": "update_task_status",
                "description": "Update the status of a task",
                "callable": self.api_tools.update_task_status,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string", "description": "The task ID"},
                        "status": {"type": "string", "description": "New status"},
                    },
                    "required": ["task_id", "status"],
                },
            },
            "get_service_status": {
                "name": "get_service_status",
                "description": "Get the status of a service",
                "callable": self.api_tools.get_service_status,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "service_name": {"type": "string", "description": "The service name (optional)"}
                    },
                    "required": [],
                },
            },
            "restart_service": {
                "name": "restart_service",
                "description": "Restart a service",
                "callable": self.api_tools.restart_service,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "service_name": {
                            "type": "string",
                            "description": "The service name",
                        }
                    },
                    "required": ["service_name"],
                },
            },
        }
        
        self._tools_cache = tools
        logger.info(f"✅ Loaded {len(tools)} MCP tools")
        return tools
    
    def extract_parameters_from_query(self, tool_name: str, query: str) -> Dict[str, Any]:
        """
        Extract parameters for a tool from user query using LLM.
        
        Args:
            tool_name: Name of the tool
            query: User query text
            
        Returns:
            Dictionary of extracted parameters
        """
        tools = self.get_tools()
        if tool_name not in tools:
            return {}
        
        tool_info = tools[tool_name]
        schema = tool_info.get("inputSchema", {})
        properties = schema.get("properties", {})
        
        if not properties:
            return {}
        
        # Build extraction prompt
        params_desc = "\n".join([
            f"- {name}: {prop.get('description', 'No description')}"
            for name, prop in properties.items()
        ])
        
        extraction_prompt = f"""Extract parameters for the tool '{tool_name}' from the user query.

User Query: {query}

Tool Parameters:
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
        Validate parameters and collect missing ones.
        
        Args:
            tool_name: Name of the tool
            tool_input: Parameters provided in Action Input
            query: Original user query
            
        Returns:
            Tuple of (parameters_available, collected_params, user_prompt)
        """
        tools = self.get_tools()
        if tool_name not in tools:
            return False, tool_input, f"Tool '{tool_name}' not found"
        
        # Extract parameters from the query
        extracted = self.extract_parameters_from_query(tool_name, query)
        provided = {**tool_input, **extracted}
        
        # Check required parameters from schema
        tool_info = tools[tool_name]
        schema = tool_info.get("inputSchema", {})
        required = schema.get("required", [])
        
        # Validate all required parameters are present
        missing = [p for p in required if p not in provided or provided[p] is None]
        
        if not missing:
            return True, provided, ""
        
        # Start parameter collection
        has_all, prompt = self.parameter_collector.start_collection(
            tool_name=tool_name,
            provided_parameters=provided,
            context={"original_query": query},
        )
        
        logger.info(f"Missing parameters for '{tool_name}': {missing}")
        return has_all, provided, prompt
    
    def process_parameter_response(
        self,
        user_response: str,
    ) -> tuple[bool, Dict[str, Any], str]:
        """
        Process user's response to parameter request.
        
        Args:
            user_response: User's response text
            
        Returns:
            Tuple of (parameters_complete, collected_params, next_prompt)
        """
        if not self.parameter_collector.get_pending_tool():
            return False, {}, "No pending parameter collection"
        
        tool_name = self.parameter_collector.get_pending_tool()
        extracted = self.extract_parameters_from_query(tool_name, user_response)
        
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
        Override to validate and collect parameters for MCP tools.
        
        Args:
            tool_name: Name of the tool
            tool_input: Parameters provided in Action Input
            query: Original user query
            
        Returns:
            Tuple of (parameters_valid, parameters_dict, error_or_prompt)
        """
        return self.validate_and_collect_parameters(
            tool_name=tool_name,
            tool_input=tool_input,
            query=query,
        )
    
    async def execute_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
    ) -> Any:
        """
        Execute a tool (MCP-based direct call).
        
        Args:
            tool_name: Name of the tool
            tool_input: Parameters for the tool
            
        Returns:
            Result from the tool execution
        """
        tools = self.get_tools()
        
        if tool_name not in tools:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' not found",
            }
        
        try:
            tool_info = tools[tool_name]
            tool_callable = tool_info["callable"]
            
            # Call the tool directly
            result = tool_callable(**tool_input)
            
            # Handle async callables
            if asyncio.iscoroutine(result):
                result = await result
            
            logger.info(f"Tool '{tool_name}' executed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    def process_tool_result(self, tool_name: str, tool_result: Any) -> str:
        """
        Process and format tool results for the LLM.
        
        Args:
            tool_name: Name of the tool that was called
            tool_result: Result from the tool
            
        Returns:
            Formatted string for LLM consumption
        """
        if not isinstance(tool_result, dict):
            return str(tool_result)
        
        success = tool_result.get("success", False)
        
        if not success:
            error = tool_result.get("error", "Unknown error")
            return f"Error: {error}"
        
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
        
        elif tool_name in ["get_service_status", "restart_service"]:
            if isinstance(data, dict):
                return f"Service: {data.get('name')}\nStatus: {data.get('status')}"
            if message:
                return message
        
        # Default formatting
        if isinstance(data, dict):
            return f"Result: {str(data)}"
        elif isinstance(data, list):
            return f"Results:\n" + "\n".join(str(item) for item in data)
        
        return str(tool_result)
    
    def _build_system_prompt(self) -> str:
        """
        Build system prompt for the MCP agent.
        
        Returns:
            System prompt with available tools
        """
        return """You are a helpful technical assistant with access to external tools via MCP.

Available Tools:
1. User Management:
   - get_user: Get information about a specific user
   - list_users: List all users in the system
   - create_user: Create a new user

2. Task Management:
   - create_task: Create a new task and assign it to a user
   - get_task: Get information about a specific task
   - list_tasks: List tasks (can filter by status or assigned user)
   - update_task_status: Update a task's status

3. Service Management:
   - get_service_status: Get the status of a service
   - restart_service: Restart a service

Your task is to:
1. Understand what the user is asking for
2. Decide which tool(s) to call
3. Call the tool with correct parameters
4. Process and explain the results

Follow this format:
Thought: What does the user need? Which tool should I call?
Action: The tool name
Action Input: The parameters as JSON {"key": "value"}

When you have the complete answer:
Action: stop
Final Response: Your comprehensive answer based on tool results

Be helpful, clear, and accurate in your responses."""
