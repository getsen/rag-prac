"""
Parameter collection system for agent tools.
Handles detecting missing parameters and collecting them from user via conversation.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from app.agentic.tool_definitions import get_tool_definition, ToolParameter

logger = logging.getLogger(__name__)


class ParameterCollector:
    """
    Manages collecting missing tool parameters from user via conversation.
    Stores parameter state across multiple interactions.
    """
    
    def __init__(self):
        """Initialize the parameter collector."""
        self.pending_tool: Optional[str] = None  # Tool waiting for parameters
        self.collected_parameters: Dict[str, Any] = {}  # Parameters collected so far
        self.missing_parameters: List[str] = []  # Parameters still needed
        self.context: Dict[str, Any] = {}  # Additional context about the request
    
    def start_collection(
        self,
        tool_name: str,
        provided_parameters: Dict[str, Any],
        context: Dict[str, Any] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Start collecting parameters for a tool.
        
        Args:
            tool_name: Name of the tool that needs parameters
            provided_parameters: Parameters already extracted from user query
            context: Additional context about the request
            
        Returns:
            Tuple of (all_parameters_available, prompt_for_user)
            - If all_parameters_available is True, tool can execute
            - If False, prompt_for_user contains the message to send to user
        """
        tool_def = get_tool_definition(tool_name)
        if not tool_def:
            return False, f"Tool '{tool_name}' not found"
        
        # Check which parameters are missing
        is_valid, missing = tool_def.validate_parameters(provided_parameters)
        
        if is_valid:
            # All required parameters are available
            return True, None
        
        # Some parameters are missing, start collection
        self.pending_tool = tool_name
        self.collected_parameters = provided_parameters.copy()
        self.missing_parameters = missing
        self.context = context or {}
        
        # Generate prompt for user
        prompt = self._generate_collection_prompt(tool_def, missing)
        
        logger.info(
            f"Starting parameter collection for tool '{tool_name}'. "
            f"Missing: {missing}"
        )
        
        return False, prompt
    
    def add_parameters(
        self,
        user_response: str,
        extracted_params: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        """
        Process user's response and add collected parameters.
        
        Args:
            user_response: Raw user response text
            extracted_params: Parameters extracted from user response
            
        Returns:
            Tuple of (all_parameters_available, next_prompt)
        """
        if not self.pending_tool:
            return False, "No pending tool parameter collection"
        
        tool_def = get_tool_definition(self.pending_tool)
        if not tool_def:
            return False, "Tool definition not found"
        
        # Add newly extracted parameters
        self.collected_parameters.update(extracted_params)
        
        # Check if all parameters are now available
        is_valid, still_missing = tool_def.validate_parameters(self.collected_parameters)
        
        if is_valid:
            # All parameters collected!
            logger.info(
                f"All parameters collected for tool '{self.pending_tool}': "
                f"{self.collected_parameters}"
            )
            return True, None
        
        # Still missing some parameters
        self.missing_parameters = still_missing
        prompt = self._generate_collection_prompt(tool_def, still_missing)
        
        logger.info(
            f"Still collecting parameters for '{self.pending_tool}'. "
            f"Still missing: {still_missing}"
        )
        
        return False, prompt
    
    def get_collected_parameters(self) -> Dict[str, Any]:
        """Get all collected parameters for the pending tool."""
        return self.collected_parameters.copy()
    
    def get_pending_tool(self) -> Optional[str]:
        """Get the tool currently collecting parameters."""
        return self.pending_tool
    
    def reset(self):
        """Reset the collection state."""
        self.pending_tool = None
        self.collected_parameters = {}
        self.missing_parameters = []
        self.context = {}
        logger.info("Parameter collection reset")
    
    def _generate_collection_prompt(
        self,
        tool_def,
        missing_params: List[str],
    ) -> str:
        """
        Generate a user-friendly prompt asking for missing parameters.
        
        Args:
            tool_def: Tool definition
            missing_params: List of parameter names that are missing
            
        Returns:
            Formatted prompt for user
        """
        if not missing_params:
            return ""
        
        prompt_lines = [
            f"To {tool_def.description.lower()}, I need the following information:",
            "",
        ]
        
        for param_name in missing_params:
            param = tool_def.get_parameter_by_name(param_name)
            if param:
                examples_str = ""
                if param.examples:
                    examples_str = f" (e.g., {', '.join(param.examples)})"
                
                prompt_lines.append(f"• {param.description}{examples_str}")
        
        prompt_lines.append("")
        prompt_lines.append("Please provide this information so I can proceed.")
        
        return "\n".join(prompt_lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize state for storage."""
        return {
            "pending_tool": self.pending_tool,
            "collected_parameters": self.collected_parameters,
            "missing_parameters": self.missing_parameters,
            "context": self.context,
        }
    
    def from_dict(self, state: Dict[str, Any]) -> None:
        """Restore state from serialized data."""
        self.pending_tool = state.get("pending_tool")
        self.collected_parameters = state.get("collected_parameters", {})
        self.missing_parameters = state.get("missing_parameters", [])
        self.context = state.get("context", {})
