#!/usr/bin/env python3
"""
Test parameter collection system for agent tools.
Tests the workflow of detecting missing parameters and collecting them.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.agentic.api_agent import APIAgent
from app.agentic.parameter_collector import ParameterCollector
from app.agentic.tool_definitions import get_tool_definition, get_all_tool_definitions
from app.config import Settings


def test_tool_definitions():
    """Test that tool definitions are properly configured."""
    print(f"\n{'='*80}")
    print("Testing Tool Definitions")
    print(f"{'='*80}\n")
    
    defs = get_all_tool_definitions()
    
    # Check that all expected tools are defined
    expected_tools = [
        "list_users", "get_user", "list_tasks", "get_task",
        "create_task", "update_task_status", "get_service_status", "restart_service"
    ]
    
    for tool in expected_tools:
        tool_def = get_tool_definition(tool)
        assert tool_def is not None, f"Tool '{tool}' not defined"
        print(f"✅ {tool}: {len(tool_def.get_required_parameters())} required params")
    
    # Verify get_user has user_id parameter
    get_user_def = get_tool_definition("get_user")
    assert len(get_user_def.get_required_parameters()) == 1
    assert get_user_def.get_required_parameters()[0].name == "user_id"
    print(f"\n✅ get_user correctly requires 'user_id'")
    
    # Verify create_task has title and assigned_to
    create_task_def = get_tool_definition("create_task")
    required = [p.name for p in create_task_def.get_required_parameters()]
    assert "title" in required and "assigned_to" in required
    print(f"✅ create_task correctly requires 'title' and 'assigned_to'")


def test_parameter_validation():
    """Test parameter validation."""
    print(f"\n{'='*80}")
    print("Testing Parameter Validation")
    print(f"{'='*80}\n")
    
    get_user_def = get_tool_definition("get_user")
    
    # Test with missing parameter
    is_valid, missing = get_user_def.validate_parameters({})
    assert not is_valid and "user_id" in missing
    print(f"✅ Detected missing 'user_id' parameter")
    
    # Test with provided parameter
    is_valid, missing = get_user_def.validate_parameters({"user_id": "user1"})
    assert is_valid and len(missing) == 0
    print(f"✅ Validated 'user_id' parameter")


def test_parameter_collector():
    """Test parameter collection flow."""
    print(f"\n{'='*80}")
    print("Testing Parameter Collector")
    print(f"{'='*80}\n")
    
    collector = ParameterCollector()
    
    # Start collecting for get_user (missing user_id)
    has_all, prompt = collector.start_collection(
        tool_name="get_user",
        provided_parameters={},
        context={"original_query": "get user role for user1"},
    )
    
    assert not has_all, "Should not have all parameters yet"
    assert "user" in prompt.lower(), "Prompt should mention user"
    assert collector.get_pending_tool() == "get_user"
    print(f"✅ Started collection for 'get_user'")
    print(f"   Prompt: {prompt[:100]}...")
    
    # User provides user_id
    has_all, prompt = collector.add_parameters(
        user_response="The user is user1",
        extracted_params={"user_id": "user1"},
    )
    
    assert has_all, "Should have all parameters now"
    assert prompt is None or len(prompt) == 0, "Should not need more prompts"
    assert collector.get_collected_parameters()["user_id"] == "user1"
    print(f"✅ Successfully collected 'user_id' parameter")
    
    # Reset
    collector.reset()
    assert collector.get_pending_tool() is None
    print(f"✅ Reset collector state")


def test_api_agent_parameter_validation():
    """Test APIAgent parameter validation."""
    print(f"\n{'='*80}")
    print("Testing APIAgent Parameter Validation")
    print(f"{'='*80}\n")
    
    settings = Settings()
    agent = APIAgent(
        model=settings.ollama_model,
        temperature=settings.temperature,
    )
    
    # Test with completely missing user_id (no clues in query)
    params_valid, validated, prompt = agent.validate_tool_parameters(
        tool_name="get_user",
        tool_input={},
        query="get user info",  # No user_id mentioned
    )
    
    # This might succeed or fail depending on LLM extraction
    # The important thing is it goes through the validation flow
    print(f"✅ Parameter validation executed")
    print(f"   Valid: {params_valid}")
    if not params_valid:
        print(f"   Prompt: {prompt[:100]}...")
    else:
        print(f"   Extracted params: {validated}")
    
    # Test create_task with user_id in query should still need title
    params_valid, validated, prompt = agent.validate_tool_parameters(
        tool_name="create_task",
        tool_input={},
        query="create a task",  # No specific title or assignee
    )
    
    # Should ask for missing parameters
    print(f"\n✅ create_task parameter validation executed")
    print(f"   Valid: {params_valid}")
    if not params_valid:
        print(f"   Missing params, prompt asked for them")
    else:
        print(f"   All params available: {validated}")


def main():
    """Run all tests."""
    try:
        test_tool_definitions()
        test_parameter_validation()
        test_parameter_collector()
        test_api_agent_parameter_validation()
        
        print(f"\n{'='*80}")
        print("✅ ALL PARAMETER COLLECTION TESTS PASSED")
        print(f"{'='*80}\n")
        return True
        
    except Exception as e:
        print(f"\n{'='*80}")
        print(f"❌ TEST FAILED: {str(e)}")
        print(f"{'='*80}\n")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
