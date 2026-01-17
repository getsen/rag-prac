#!/usr/bin/env python3
"""
Test script to verify that the agent no longer infinitely loops after tool execution.
This tests the _generate_final_response fix.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.agentic.api_agent import APIAgent
from app.config import Settings

def test_agent_no_infinite_loop():
    """Test that agent stops after tool execution without reaching max iterations."""
    
    settings = Settings()
    agent = APIAgent(
        model=settings.ollama_model,
        temperature=settings.temperature,
    )
    
    # Test query that should trigger list_users tool
    query = "List all users available"
    
    print(f"\n{'='*80}")
    print(f"Testing agent with query: {query}")
    print(f"{'='*80}\n")
    
    result = agent.sync_run(
        query=query,
    )
    
    print(f"\n{'='*80}")
    print(f"Agent Result:")
    print(f"{'='*80}")
    print(f"Response: {result.get('response')}")
    print(f"\nIterations: {result.get('iterations')}")
    print(f"Tools used: {result.get('tools_used')}")
    print(f"Reasoning steps: {len(result.get('reasoning', []))} steps")
    
    print(f"\n{'='*80}")
    print(f"Verification:")
    print(f"{'='*80}")
    
    iterations = result.get('iterations', 0)
    max_iterations = agent.max_iterations
    tools_used = result.get('tools_used', [])
    response = result.get('response', '')
    
    # Verify expectations
    checks = {
        "Did not reach max iterations": iterations < max_iterations,
        "Tool was executed": len(tools_used) > 0,
        "Got a response": len(response) > 0,
        "Response mentions tool": any(word in response.lower() for word in ['user', 'list', 'users']),
    }
    
    for check, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"{status} {check}")
    
    all_passed = all(checks.values())
    
    print(f"\n{'='*80}")
    if all_passed:
        print(f"✅ ALL CHECKS PASSED - Agent loop fix is working!")
    else:
        print(f"❌ SOME CHECKS FAILED - Agent loop may not be fixed")
    print(f"{'='*80}\n")
    
    return all_passed

if __name__ == "__main__":
    success = test_agent_no_infinite_loop()
    sys.exit(0 if success else 1)
