"""Base class for handling agentic AI requests."""

import logging
import json
from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod
import asyncio
from app.llm.ollama.ollama_client_stream import ollama_generate_stream
from app.chat.conversation_context import ConversationContextManager

logger = logging.getLogger(__name__)


class AgenticBase(ABC):
    """
    Base class for handling agentic AI requests.
    
    This class provides the foundation for implementing agent-based workflows
    that can reason, plan, and take actions to answer user queries.
    
    Subclasses should implement specific agent strategies and tool integrations.
    """
    
    def __init__(
        self,
        model: str = "llama2",
        temperature: float = 0.7,
        max_iterations: int = 10,
        timeout: float = 60.0,
    ):
        """
        Initialize the agentic base handler.
        
        Args:
            model: The LLM model to use for reasoning
            temperature: Temperature for model generation (higher = more creative)
            max_iterations: Maximum number of agent iterations/steps
            timeout: Timeout for agent execution in seconds
        """
        self.model = model
        self.temperature = temperature
        self.max_iterations = max_iterations
        self.timeout = timeout
        self.tools: Dict[str, Any] = {}
        logger.info(
            f"AgenticBase initialized with model={model}, "
            f"temperature={temperature}, max_iterations={max_iterations}"
        )
    
    @abstractmethod
    def get_tools(self) -> Dict[str, Any]:
        """
        Get available tools for the agent.
        
        Returns:
            Dictionary mapping tool names to tool definitions/callables
        """
        pass
    
    @abstractmethod
    def process_tool_result(self, tool_name: str, tool_result: Any) -> str:
        """
        Process the result from a tool execution.
        
        Args:
            tool_name: Name of the tool that was executed
            tool_result: The result returned by the tool
            
        Returns:
            Formatted string representation of the tool result
        """
        pass
    
    async def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """
        Execute a tool with the given input.
        
        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters for the tool
            
        Returns:
            Result from tool execution
        """
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not found. Available tools: {list(self.tools.keys())}")
        
        tool = self.tools[tool_name]
        
        # Handle callable tools
        if callable(tool):
            result = tool(**tool_input)
            # Handle async callables
            if asyncio.iscoroutine(result):
                result = await result
            return result
        
        raise ValueError(f"Tool '{tool_name}' is not callable")
    
    async def run(
        self,
        query: str,
        context_manager: Optional[ConversationContextManager] = None,
    ) -> Dict[str, Any]:
        """
        Execute the agent reasoning loop.
        
        Args:
            query: The user query to process
            context_manager: Optional conversation context manager
            
        Returns:
            Dictionary with:
                - response: Final response to the user
                - reasoning: Agent's reasoning steps
                - tools_used: List of tools that were executed
                - iterations: Number of iterations taken
        """
        logger.info(f"Starting agentic run for query: {query[:100]}")
        
        reasoning_steps: List[str] = []
        tools_used: List[Dict[str, Any]] = []
        iteration = 0
        current_context = query
        
        try:
            # Get available tools
            self.tools = self.get_tools()
            
            while iteration < self.max_iterations:
                iteration += 1
                logger.info(f"Agent iteration {iteration}/{self.max_iterations}")
                
                # Generate next action using LLM
                action = await self._get_next_action(
                    query=query,
                    current_context=current_context,
                    reasoning_steps=reasoning_steps,
                    context_manager=context_manager,
                )
                
                # Add fallback: Check if user query matches a tool even if LLM didn't suggest it
                if not action.get("action") or action.get("action") == "stop":
                    action = self._detect_tool_from_query(query, action)
                
                reasoning_steps.append(f"Step {iteration}: {action.get('thought', 'Processing...')}")
                
                # Check if agent decided to stop
                if action.get("action") == "stop" or action.get("final_response"):
                    response = action.get("final_response", "No response generated")
                    logger.info(f"Agent finished with response after {iteration} iterations")
                    return {
                        "response": response,
                        "reasoning": reasoning_steps,
                        "tools_used": tools_used,
                        "iterations": iteration,
                    }
                
                # Execute tool if specified
                if action.get("action") and action.get("action") != "stop":
                    tool_name = action.get("action")
                    tool_input = action.get("action_input", {})
                    
                    logger.info(f"Executing tool: {tool_name}")
                    
                    try:
                        tool_result = await self.execute_tool(tool_name, tool_input)
                        processed_result = self.process_tool_result(tool_name, tool_result)
                        
                        tools_used.append({
                            "tool": tool_name,
                            "input": tool_input,
                            "output": processed_result[:500],  # Truncate for logging
                        })
                        
                        # Update context with tool result
                        current_context = f"Previous context: {current_context}\n\nTool '{tool_name}' result: {processed_result}"
                        
                        # After successful tool execution, try to generate final answer
                        # This prevents infinite loops where the agent keeps executing the same tool
                        if iteration < self.max_iterations - 1:
                            # Give the agent one more chance to say "I have the answer"
                            final_response = await self._generate_final_response(
                                query=query,
                                tool_result=processed_result,
                                tool_name=tool_name,
                            )
                            
                            if final_response:
                                logger.info(f"Generated final response after tool execution")
                                return {
                                    "response": final_response,
                                    "reasoning": reasoning_steps,
                                    "tools_used": tools_used,
                                    "iterations": iteration,
                                }
                        
                    except Exception as e:
                        error_msg = f"Error executing tool '{tool_name}': {str(e)}"
                        logger.error(error_msg)
                        reasoning_steps.append(error_msg)
                        current_context = f"{current_context}\n\nError: {error_msg}"
            
            # Max iterations reached
            response = "Unable to generate response within maximum iterations."
            logger.warning(f"Agent reached maximum iterations ({self.max_iterations})")
            
            return {
                "response": response,
                "reasoning": reasoning_steps,
                "tools_used": tools_used,
                "iterations": iteration,
            }
            
        except Exception as e:
            logger.error(f"Error in agentic run: {str(e)}")
            return {
                "response": f"Error: {str(e)}",
                "reasoning": reasoning_steps,
                "tools_used": tools_used,
                "iterations": iteration,
            }
    
    async def _get_next_action(
        self,
        query: str,
        current_context: str,
        reasoning_steps: List[str],
        context_manager: Optional[ConversationContextManager] = None,
    ) -> Dict[str, Any]:
        """
        Get the next action from the LLM based on current context.
        
        Args:
            query: Original user query
            current_context: Current context/results from previous steps
            reasoning_steps: Previous reasoning steps
            context_manager: Optional conversation context
            
        Returns:
            Dictionary with action, thought, and other metadata
        """
        # Build system prompt for agent
        system_prompt = self._build_system_prompt()
        
        # Build user message with context
        user_message = self._build_user_message(
            query=query,
            current_context=current_context,
            reasoning_steps=reasoning_steps,
            context_manager=context_manager,
        )
        
        logger.debug(f"System prompt: {system_prompt[:200]}...")
        logger.debug(f"User message: {user_message[:200]}...")
        
        # Call LLM to get next action
        # Note: ollama_generate_stream returns a generator, not an awaitable
        response_chunks = ollama_generate_stream(
            model=self.model,
            prompt=user_message,
            system=system_prompt,
            temperature=self.temperature,
        )
        
        # Consume the generator to build complete response
        response = "".join(response_chunks)
        
        # Parse response to extract action
        action = self._parse_action(response)
        return action
    
    def _detect_tool_from_query(self, query: str, current_action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect tool to use based on user query as fallback.
        
        Args:
            query: User query
            current_action: Current action from LLM (may be stop)
            
        Returns:
            Updated action dict if tool detected, else current_action
        """
        query_lower = query.lower()
        
        # Keyword mappings for tool detection
        tool_keywords = {
            "list_users": ["list.*users?", "all users?", "show users?", "get all users?"],
            "get_user": ["get user", "find user", "user info", "who is"],
            "list_tasks": ["list.*tasks?", "all tasks?", "show tasks?", "get all tasks?"],
            "get_task": ["get task", "find task", "task info"],
            "create_task": ["create.*task", "new task", "add task"],
            "update_task_status": ["update.*status", "change.*status", "mark.*task"],
            "get_service_status": ["service.*status", "check.*service"],
            "restart_service": ["restart.*service", "restart service"],
        }
        
        import re
        for tool, keywords in tool_keywords.items():
            for keyword in keywords:
                if re.search(keyword, query_lower):
                    logger.info(f"Detected tool from query using keyword '{keyword}': {tool}")
                    return {
                        "thought": f"Matched query pattern to {tool}",
                        "action": tool,
                        "action_input": {},
                        "final_response": None,
                    }
        
        return current_action
    
    async def _generate_final_response(self, query: str, tool_result: str, tool_name: str) -> Optional[str]:
        """
        Generate a final response after tool execution.
        
        Args:
            query: Original user query
            tool_result: Result from the executed tool
            tool_name: Name of the tool that was executed
            
        Returns:
            Final response string or None if unable to generate
        """
        try:
            user_message = f"""User query: {query}

I executed the '{tool_name}' tool and got this result:
{tool_result}

Based on this result, provide a clear and concise answer to the user's original query.
If the result directly answers the query, summarize it for the user.
If more information is needed, you can ask for clarification or suggest next steps."""
            
            response_chunks = ollama_generate_stream(
                model=self.model,
                prompt=user_message,
                system="You are a helpful assistant. Provide clear and concise responses based on the provided tool results.",
                temperature=self.temperature,
            )
            
            response = "".join(response_chunks)
            return response if response.strip() else None
            
        except Exception as e:
            logger.error(f"Error generating final response: {str(e)}")
            return None
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt for the agent."""
        tools_list = "\n".join(
            f"- {name}: {self._get_tool_description(name)}"
            for name in self.tools.keys()
        )
        
        return f"""You are a helpful AI assistant with access to the following tools:

            {tools_list}

            Your task is to help answer user questions by using the available tools when necessary.

            IMPORTANT INSTRUCTIONS:
            1. You MUST use tools to get real data. Do NOT guess or make up information.
            2. For queries about users, tasks, or services, you MUST call the appropriate tool.
            3. For "list" or "get all" queries, call the corresponding list_* or get_* tool.
            4. Always execute tools first, then provide the results to the user.

            Follow this format for your response:
            Thought: What do you need to do?
            Action: The tool name to use (or 'stop' if no tool needed)
            Action Input: The input parameters for the tool as JSON, or {{}} if not needed
            Observation: [This will be filled in based on tool output]

            If you can answer the question directly or after tool execution, respond with:
            Thought: I have enough information to answer
            Action: stop
            Final Response: Your complete answer to the user

            EXAMPLES:
            - User: "List all users" -> Action: list_users
            - User: "Get user john" -> Action: get_user with {{"user_id": "john"}}
            - User: "What tasks are pending?" -> Action: list_tasks then filter by status

            Be concise and helpful in your responses."""
    
    def _build_user_message(
        self,
        query: str,
        current_context: str,
        reasoning_steps: List[str],
        context_manager: Optional[ConversationContextManager] = None,
    ) -> str:
        """Build the user message with context for the LLM."""
        message = f"User Query: {query}\n\n"
        
        if reasoning_steps:
            message += f"Previous Steps:\n" + "\n".join(reasoning_steps) + "\n\n"
        
        if current_context and current_context != query:
            message += f"Current Context:\n{current_context}\n\n"
        
        if context_manager:
            conv_context = context_manager.get_context_for_rag()
            if conv_context.get("full_context"):
                message += f"Conversation History:\n{conv_context['full_context']}\n\n"
        
        message += "What is your next action?"
        return message
    
    def _get_tool_description(self, tool_name: str) -> str:
        """Get description for a tool."""
        tool = self.tools.get(tool_name)
        if hasattr(tool, "__doc__") and tool.__doc__:
            return tool.__doc__.strip()
        return f"Tool: {tool_name}"
    
    def _parse_action(self, response: str) -> Dict[str, Any]:
        """
        Parse the LLM response to extract action.
        
        Args:
            response: Raw response from LLM
            
        Returns:
            Dictionary with parsed action details
        """
        try:
            # Try to parse structured response
            lines = response.strip().split("\n")
            action_dict = {
                "thought": "",
                "action": None,
                "action_input": {},
                "final_response": None,
            }
            
            for line in lines:
                line = line.strip()
                if line.startswith("Thought:"):
                    action_dict["thought"] = line.replace("Thought:", "").strip()
                elif line.startswith("Action:"):
                    action_dict["action"] = line.replace("Action:", "").strip()
                elif line.startswith("Action Input:"):
                    input_str = line.replace("Action Input:", "").strip()
                    try:
                        if input_str and input_str != "{}":
                            action_dict["action_input"] = json.loads(input_str)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse action input JSON: {input_str}")
                elif line.startswith("Final Response:"):
                    action_dict["final_response"] = line.replace("Final Response:", "").strip()
            
            # If action is found, return it
            if action_dict.get("action"):
                logger.info(f"Parsed action: {action_dict['action']}")
                return action_dict
            
            # Fallback: Try to detect tool calls from response content
            response_lower = response.lower()
            available_tools = list(self.tools.keys())
            
            logger.debug(f"Available tools: {available_tools}")
            logger.debug(f"Response text: {response_lower[:200]}")
            
            # Check if any tool name is mentioned in the response (exact match or with underscore variants)
            for tool in available_tools:
                tool_lower = tool.lower()
                # Check for exact match
                if tool_lower in response_lower:
                    logger.info(f"Detected tool mention: {tool}")
                    action_dict["action"] = tool
                    action_dict["thought"] = "Detected from response"
                    action_dict["action_input"] = {}
                    return action_dict
                
                # Check for space-separated variant (e.g., "list users" for "list_users")
                tool_spaced = tool_lower.replace("_", " ")
                if tool_spaced in response_lower:
                    logger.info(f"Detected tool mention (spaced): {tool}")
                    action_dict["action"] = tool
                    action_dict["thought"] = "Detected from response"
                    action_dict["action_input"] = {}
                    return action_dict
            
            # Default to stop action if no tool detected
            action_dict["action"] = "stop"
            action_dict["final_response"] = response
            logger.info(f"No tool detected, defaulting to stop action. Available tools: {available_tools}")
            
            return action_dict
            
        except Exception as e:
            logger.error(f"Error parsing action: {str(e)}")
            return {
                "thought": "Error parsing response",
                "action": "stop",
                "action_input": {},
                "final_response": response,
            }
    
    def sync_run(
        self,
        query: str,
        context_manager: Optional[ConversationContextManager] = None,
    ) -> Dict[str, Any]:
        """
        Synchronous wrapper for the async run method.
        
        Args:
            query: The user query to process
            context_manager: Optional conversation context manager
            
        Returns:
            Dictionary with response and metadata
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            self.run(query=query, context_manager=context_manager)
        )
