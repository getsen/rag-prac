"""
External API Tools Service
Wraps HTTP calls to Express API server for agentic tools.
"""

import logging
import json
from typing import Any, Dict, Optional
from datetime import datetime
from app.agentic.http_api_client import get_http_api_client

logger = logging.getLogger(__name__)


class ExternalAPITools:
    """Collection of external API tools that call the Express API."""
    
    def __init__(self):
        """Initialize with HTTP API client."""
        self.http_client = get_http_api_client()
        logger.info("ExternalAPITools initialized with HTTP API client")
    
    async def get_user(self, user_id: str) -> Dict[str, Any]:
        """
        Get user information by ID from Express API.
        
        Args:
            user_id: The user ID to retrieve
            
        Returns:
            User information or error message
        """
        logger.info(f"API Tool: Getting user {user_id}")
        return await self.http_client.get_user(user_id)
    
    async def list_users(self) -> Dict[str, Any]:
        """
        List all users from Express API.
        
        Returns:
            List of all users
        """
        logger.info("API Tool: Listing all users")
        return await self.http_client.list_users()
    
    async def create_task(self, title: str, assigned_to: str) -> Dict[str, Any]:
        """
        Create a new task via Express API.
        
        Args:
            title: Task title
            assigned_to: User ID to assign task to
            
        Returns:
            Created task or error message
        """
        logger.info(f"API Tool: Creating task '{title}' for {assigned_to}")
        return await self.http_client.create_task(title, assigned_to)
    
    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """
        Get task information by ID from Express API.
        
        Args:
            task_id: The task ID to retrieve
            
        Returns:
            Task information or error message
        """
        logger.info(f"API Tool: Getting task {task_id}")
        return await self.http_client.get_task(task_id)
    
    async def list_tasks(self, status: Optional[str] = None) -> Dict[str, Any]:
        """
        List tasks from Express API, optionally filtered by status.
        
        Args:
            status: Optional status to filter by (pending, in_progress, completed)
            
        Returns:
            List of tasks
        """
        logger.info(f"API Tool: Listing tasks with status={status}")
        result = await self.http_client.list_tasks()
        
        if result.get("success") and status:
            data = result.get("data", [])
            result["data"] = [t for t in data if t.get("status") == status]
        
        return result
    
    async def update_task_status(self, task_id: str, status: str) -> Dict[str, Any]:
        """
        Update task status via Express API.
        
        Args:
            task_id: Task ID to update
            status: New status (pending, in_progress, completed)
            
        Returns:
            Updated task or error message
        """
        logger.info(f"API Tool: Updating task {task_id} status to {status}")
        return await self.http_client.update_task_status(task_id, status)
    
    async def get_service_status(self, service_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get service status information from Express API.
        
        Args:
            service_name: Optional specific service to check
            
        Returns:
            Service status information
        """
        logger.info(f"API Tool: Getting service status for {service_name or 'all services'}")
        
        if service_name:
            return await self.http_client.get_service_status(service_name)
        
        # Get all services
        result = await self.http_client.get_service_status("")
        return result
    
    async def restart_service(self, service_name: str) -> Dict[str, Any]:
        """
        Restart a service via Express API.
        
        Args:
            service_name: Name of service to restart
            
        Returns:
            Service restart result
        """
        logger.info(f"API Tool: Restarting service {service_name}")
        return await self.http_client.restart_service(service_name)


# Global instance
_tools_instance: Optional[ExternalAPITools] = None


def get_api_tools() -> ExternalAPITools:
    """Get or create the API tools instance."""
    global _tools_instance
    if _tools_instance is None:
        _tools_instance = ExternalAPITools()
    return _tools_instance
