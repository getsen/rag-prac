#!/usr/bin/env python3
"""
Unit test to verify the _generate_final_response method exists and has correct signature.
This tests that the infinite loop fix infrastructure is in place.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.agentic.api_agent import APIAgent
from app.config import Settings
import inspect

def test_agent_has_final_response_method():
    """Test that agent has the _generate_final_response method."""
    
    settings = Settings()
    agent = APIAgent(
        model=settings.ollama_model,
        temperature=settings.temperature,
    )
    
    print(f"\n{'='*80}")
    print(f"Testing Agent Infrastructure for Infinite Loop Fix")
    print(f"{'='*80}\n")
    
    # Check if method exists
    has_method = hasattr(agent, '_generate_final_response')
    print(f"✅ Agent has _generate_final_response method: {has_method}")
    
    if not has_method:
        print("❌ FAILED: Method not found")
        return False
    
    # Check if it's async
    method = getattr(agent, '_generate_final_response')
    is_async = inspect.iscoroutinefunction(method)
    print(f"✅ Method is async: {is_async}")
    
    if not is_async:
        print("❌ FAILED: Method should be async")
        return False
    
    # Check signature
    sig = inspect.signature(method)
    params = list(sig.parameters.keys())
    print(f"✅ Method parameters: {params}")
    
    expected_params = ['query', 'tool_result', 'tool_name']
    has_all_params = all(p in params for p in expected_params)
    print(f"✅ Has all expected parameters: {has_all_params}")
    
    if not has_all_params:
        print(f"❌ FAILED: Expected parameters {expected_params}, got {params}")
        return False
    
    # Check that run method handles tool execution
    run_method = getattr(agent, 'run')
    run_source = inspect.getsource(run_method)
    
    has_tool_execution = '_generate_final_response' in run_source
    print(f"✅ run() method calls _generate_final_response: {has_tool_execution}")
    
    if not has_tool_execution:
        print("❌ FAILED: run() method should call _generate_final_response")
        return False
    
    # Check tool detection methods
    has_detect_tool = hasattr(agent, '_detect_tool_from_query')
    print(f"✅ Agent has _detect_tool_from_query method: {has_detect_tool}")
    
    has_parse_action = hasattr(agent, '_parse_action')
    print(f"✅ Agent has _parse_action method: {has_parse_action}")
    
    print(f"\n{'='*80}")
    print(f"✅ ALL CHECKS PASSED - Infrastructure for infinite loop fix is in place!")
    print(f"{'='*80}\n")
    
    return True

if __name__ == "__main__":
    success = test_agent_has_final_response_method()
    sys.exit(0 if success else 1)
