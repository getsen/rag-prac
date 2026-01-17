"""
HTTP API Client for Express Server
Provides methods to call the Express API endpoints for agentic tools.
"""

import logging
import requests
from typing import Any, Dict, Optional
from app.config import settings

logger = logging.getLogger(__name__)


class HTTPAPIClient:
    """Client for calling external HTTP APIs (Express server)."""
    
    def __init__(self, base_url: str = "http://localhost:3001"):
        """
        Initialize HTTP API client.
        
        Args:
            base_url: Base URL of the Express API server
        """
        self.base_url = base_url
        self.api_base = f"{self.base_url}/api"
        self.timeout = 10
        logger.info(f"HTTPAPIClient initialized with base_url={self.api_base}")
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Make HTTP request to API.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path (e.g., '/users')
            **kwargs: Additional arguments to pass to requests
            
        Returns:
            Response JSON or error dict
        """
        url = f"{self.api_base}{endpoint}"
        try:
            logger.debug(f"Making {method} request to {url}")
            
            response = requests.request(
                method=method,
                url=url,
                timeout=self.timeout,
                **kwargs
            )
            response.raise_for_status()
            
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
            }
    
    async def list_users(self) -> Dict[str, Any]:
        """
        List all users from Express API.
        
        Returns:
            Users list or error dict
        """
        try:
            users = self._make_request("GET", "/users")
            return {
                "success": True,
                "data": users if isinstance(users, list) else users.get("data", []),
                "message": f"Found {len(users) if isinstance(users, list) else 0} users",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    async def get_user(self, user_id: str) -> Dict[str, Any]:
        """
        Get user by ID from Express API.
        
        Args:
            user_id: User ID
            
        Returns:
            User data or error dict
        """
        try:
            user = self._make_request("GET", f"/users/{user_id}")
            return {
                "success": True,
                "data": user,
                "message": f"User {user_id} retrieved",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    async def list_tasks(self) -> Dict[str, Any]:
        """
        List all tasks from Express API.
        
        Returns:
            Tasks list or error dict
        """
        try:
            tasks = self._make_request("GET", "/tasks")
            return {
                "success": True,
                "data": tasks if isinstance(tasks, list) else tasks.get("data", []),
                "message": f"Found {len(tasks) if isinstance(tasks, list) else 0} tasks",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """
        Get task by ID from Express API.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task data or error dict
        """
        try:
            task = self._make_request("GET", f"/tasks/{task_id}")
            return {
                "success": True,
                "data": task,
                "message": f"Task {task_id} retrieved",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    async def create_task(self, title: str, assigned_to: str = "") -> Dict[str, Any]:
        """
        Create a new task via Express API.
        
        Args:
            title: Task title
            assigned_to: User ID to assign to (optional)
            
        Returns:
            Created task data or error dict
        """
        try:
            payload = {
                "title": title,
                "assigned_to": assigned_to or "",
            }
            task = self._make_request("POST", "/tasks", json=payload)
            return {
                "success": True,
                "data": task,
                "message": f"Task '{title}' created",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    async def update_task_status(self, task_id: str, status: str) -> Dict[str, Any]:
        """
        Update task status via Express API.
        
        Args:
            task_id: Task ID
            status: New status (pending/in_progress/completed)
            
        Returns:
            Updated task data or error dict
        """
        try:
            payload = {"status": status}
            task = self._make_request("PUT", f"/tasks/{task_id}", json=payload)
            return {
                "success": True,
                "data": task,
                "message": f"Task {task_id} status updated to {status}",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    async def get_service_status(self, service_name: str) -> Dict[str, Any]:
        """
        Get service status from Express API.
        
        Args:
            service_name: Service name (api_server/database/cache)
            
        Returns:
            Service status data or error dict
        """
        try:
            service = self._make_request("GET", f"/services")
            # Filter for specific service
            services_list = service if isinstance(service, list) else service.get("data", [])
            matching = [s for s in services_list if s.get("name") == service_name]
            
            if matching:
                return {
                    "success": True,
                    "data": matching[0],
                    "message": f"Service {service_name} status retrieved",
                }
            else:
                return {
                    "success": False,
                    "error": f"Service {service_name} not found",
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    async def restart_service(self, service_name: str) -> Dict[str, Any]:
        """
        Restart a service via Express API.
        
        Args:
            service_name: Service name to restart
            
        Returns:
            Service status or error dict
        """
        try:
            result = self._make_request("POST", f"/services/{service_name}/restart")
            return {
                "success": True,
                "data": result,
                "message": f"Service {service_name} restart initiated",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }


# Global HTTP client instance
_http_client = HTTPAPIClient(base_url=getattr(settings, 'express_api_url', 'http://localhost:3001'))


def get_http_api_client() -> HTTPAPIClient:
    """Get the global HTTP API client instance."""
    return _http_client
