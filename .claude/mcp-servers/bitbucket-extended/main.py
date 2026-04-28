#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bitbucket MCP Server - Extended Version

A Model Context Protocol server that provides comprehensive access to Bitbucket Cloud REST API.
This expanded version includes all major API endpoints from the Bitbucket Cloud documentation.

Enterprise-grade implementation with enhanced security, error handling, and logging.
"""

import sys
import subprocess
import os

# Check and install dependencies if needed
def check_dependencies():
    """Check if required dependencies are installed"""
    missing = []
    
    try:
        import aiohttp
    except ImportError:
        missing.append('aiohttp')
    
    try:
        import mcp
    except ImportError:
        missing.append('mcp')
    
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        if 'mcp' not in missing:
            missing.append('fastmcp')
    
    try:
        import certifi
    except ImportError:
        missing.append('certifi')
    
    if missing:
        print(f"Missing dependencies: {', '.join(missing)}", file=sys.stderr)
        print("Installing dependencies...", file=sys.stderr)
        
        # Try to install missing dependencies
        for package in missing:
            if package == 'fastmcp':
                package = 'mcp[cli]'
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", package], 
                                    stdout=subprocess.DEVNULL, 
                                    stderr=subprocess.DEVNULL)
                print(f"✓ Installed {package}", file=sys.stderr)
            except subprocess.CalledProcessError:
                print(f"✗ Failed to install {package}", file=sys.stderr)
                print(f"Please run: python3 -m pip install --user {package}", file=sys.stderr)
                sys.exit(1)
        
        print("Dependencies installed. Please restart Claude Desktop.", file=sys.stderr)
        sys.exit(0)

# Check dependencies before importing
check_dependencies()

# Now import the actual dependencies
import asyncio
import base64
import json
import logging
import ssl
import certifi
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import aiohttp
from mcp.server.fastmcp import FastMCP

# Configure logging for enterprise monitoring
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

class BitbucketAPI:
    """Bitbucket API client supporting both app passwords (Basic auth) and API tokens (Bearer auth)"""

    def __init__(self, workspace: str, app_password: str = None, username: str = None, api_token: str = None):
        if not workspace:
            raise ValueError("Workspace is required")
        if not api_token and not (username and app_password):
            raise ValueError("Either api_token or both username and app_password are required")

        self.workspace = workspace.strip()
        self.base_url = "https://api.bitbucket.org/2.0"

        if api_token:
            self.auth_type = "basic"
            email = os.getenv('BITBUCKET_EMAIL', username)
            self.username = email.strip() if email else username
            try:
                auth_string = f"{self.username}:{api_token.strip()}"
                auth_bytes = auth_string.encode('ascii')
                self.auth_header = base64.b64encode(auth_bytes).decode('ascii')
            except Exception as e:
                logger.error(f"Failed to encode API token credentials: {str(e)}")
                raise ValueError("Invalid API token credentials")
            logger.info(f"Initialized BitbucketAPI with API token for workspace: {self.workspace}")
        else:
            self.auth_type = "basic"
            self.username = username.strip()
            try:
                auth_string = f"{self.username}:{app_password.strip()}"
                auth_bytes = auth_string.encode('ascii')
                self.auth_header = base64.b64encode(auth_bytes).decode('ascii')
            except Exception as e:
                logger.error(f"Failed to encode authentication credentials: {str(e)}")
                raise ValueError("Invalid authentication credentials")
            logger.info(f"Initialized BitbucketAPI with app password for user: {self.username}, workspace: {self.workspace}")
    
    async def _make_request(self, session: aiohttp.ClientSession, method: str, endpoint: str, 
                          data: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make an authenticated request to the Bitbucket API"""
        url = f"{self.base_url}/{endpoint}"
        headers = {
            'Authorization': f'Basic {self.auth_header}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'BitbucketMCPServer/2.0'
        }
        
        logger.debug(f"Making {method} request to {endpoint}")
        
        # Create SSL context with certifi certificates
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        
        try:
            async with session.request(method, url, headers=headers, json=data, params=params, 
                                      timeout=aiohttp.ClientTimeout(total=30), ssl=ssl_context) as response:
                if response.status == 401:
                    raise Exception("Authentication failed. Check your username and app password.")
                elif response.status == 403:
                    raise Exception("Access denied. Check your app password permissions.")
                elif response.status == 404:
                    raise Exception("Resource not found.")
                elif response.status == 429:
                    raise Exception("Rate limit exceeded. Please retry after some time.")
                elif response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"API error {response.status}: {error_text}")
                
                return await response.json()
        except asyncio.TimeoutError:
            raise Exception("Request timeout. The Bitbucket API may be experiencing issues.")
        except aiohttp.ClientError as e:
            raise Exception(f"Network error: {str(e)}")

    # Repository Management
    async def list_repositories(self) -> List[Dict[str, Any]]:
        async with aiohttp.ClientSession() as session:
            data = await self._make_request(session, "GET", f"repositories/{self.workspace}")
            return data.get('values', [])
    
    async def get_repository(self, repo_slug: str) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "GET", f"repositories/{self.workspace}/{repo_slug}")
    
    async def create_repository(self, repo_slug: str, is_private: bool = True, description: str = "", 
                               language: str = "", has_issues: bool = True, has_wiki: bool = True) -> Dict[str, Any]:
        data = {
            "slug": repo_slug,
            "is_private": is_private,
            "description": description,
            "language": language,
            "has_issues": has_issues,
            "has_wiki": has_wiki
        }
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "POST", f"repositories/{self.workspace}/{repo_slug}", data=data)
    
    async def update_repository(self, repo_slug: str, description: str = None, 
                               is_private: bool = None, language: str = None) -> Dict[str, Any]:
        data = {}
        if description is not None:
            data["description"] = description
        if is_private is not None:
            data["is_private"] = is_private
        if language is not None:
            data["language"] = language
        
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "PUT", f"repositories/{self.workspace}/{repo_slug}", data=data)
    
    async def delete_repository(self, repo_slug: str) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "DELETE", f"repositories/{self.workspace}/{repo_slug}")
    
    async def fork_repository(self, repo_slug: str, name: str = None, workspace: str = None) -> Dict[str, Any]:
        data = {}
        if name:
            data["name"] = name
        if workspace:
            data["workspace"] = {"slug": workspace}
        
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "POST", f"repositories/{self.workspace}/{repo_slug}/forks", data=data)
    
    # Branches and Tags
    async def list_branches(self, repo_slug: str) -> List[Dict[str, Any]]:
        async with aiohttp.ClientSession() as session:
            data = await self._make_request(session, "GET", f"repositories/{self.workspace}/{repo_slug}/refs/branches")
            return data.get('values', [])
    
    async def get_branch(self, repo_slug: str, branch_name: str) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "GET", f"repositories/{self.workspace}/{repo_slug}/refs/branches/{branch_name}")
    
    async def create_branch(self, repo_slug: str, branch_name: str, target_hash: str) -> Dict[str, Any]:
        data = {
            "name": branch_name,
            "target": {"hash": target_hash}
        }
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "POST", f"repositories/{self.workspace}/{repo_slug}/refs/branches", data=data)
    
    async def delete_branch(self, repo_slug: str, branch_name: str) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "DELETE", f"repositories/{self.workspace}/{repo_slug}/refs/branches/{branch_name}")
    
    async def list_tags(self, repo_slug: str) -> List[Dict[str, Any]]:
        async with aiohttp.ClientSession() as session:
            data = await self._make_request(session, "GET", f"repositories/{self.workspace}/{repo_slug}/refs/tags")
            return data.get('values', [])
    
    async def create_tag(self, repo_slug: str, tag_name: str, target_hash: str) -> Dict[str, Any]:
        data = {
            "name": tag_name,
            "target": {"hash": target_hash}
        }
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "POST", f"repositories/{self.workspace}/{repo_slug}/refs/tags", data=data)
    
    # Commits
    async def list_commits(self, repo_slug: str, branch: str = None, path: str = None) -> List[Dict[str, Any]]:
        params = {}
        if branch:
            params["branch"] = branch
        if path:
            params["path"] = path
        
        async with aiohttp.ClientSession() as session:
            data = await self._make_request(session, "GET", f"repositories/{self.workspace}/{repo_slug}/commits", params=params)
            return data.get('values', [])
    
    async def get_commit(self, repo_slug: str, commit_hash: str) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "GET", f"repositories/{self.workspace}/{repo_slug}/commit/{commit_hash}")
    
    async def get_commit_diff(self, repo_slug: str, commit_hash: str) -> str:
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/repositories/{self.workspace}/{repo_slug}/diff/{commit_hash}"
            headers = {
                'Authorization': f'Basic {self.auth_header}',
                'User-Agent': 'BitbucketMCPServer/2.0'
            }
            
            # Create SSL context with certifi certificates
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30), ssl=ssl_context) as response:
                if response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"API error {response.status}: {error_text}")
                return await response.text()
    
    async def add_commit_comment(self, repo_slug: str, commit_hash: str, comment: str) -> Dict[str, Any]:
        data = {"content": {"raw": comment}}
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "POST", f"repositories/{self.workspace}/{repo_slug}/commit/{commit_hash}/comments", data=data)
    
    # Source Code
    async def get_file_content(self, repo_slug: str, file_path: str, branch: str = "main") -> str:
        encoded_path = quote(file_path, safe='')
        async with aiohttp.ClientSession() as session:
            endpoint = f"repositories/{self.workspace}/{repo_slug}/src/{branch}/{encoded_path}"
            url = f"{self.base_url}/{endpoint}"
            headers = {
                'Authorization': f'Basic {self.auth_header}',
                'User-Agent': 'BitbucketMCPServer/2.0'
            }
            
            # Create SSL context with certifi certificates
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30), ssl=ssl_context) as response:
                if response.status == 404:
                    raise Exception(f"File not found: {file_path}")
                elif response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"API error {response.status}: {error_text}")
                
                return await response.text()
    
    async def list_directory(self, repo_slug: str, path: str = "", branch: str = "main") -> List[Dict[str, Any]]:
        encoded_path = quote(path, safe='') if path else ""
        endpoint = f"repositories/{self.workspace}/{repo_slug}/src/{branch}/{encoded_path}"
        
        async with aiohttp.ClientSession() as session:
            data = await self._make_request(session, "GET", endpoint)
            return data.get('values', [])
    
    async def get_file_metadata(self, repo_slug: str, file_path: str, branch: str = "main") -> Dict[str, Any]:
        encoded_path = quote(file_path, safe='')
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "GET", 
                                           f"repositories/{self.workspace}/{repo_slug}/src/{branch}/{encoded_path}?format=meta")
    
    # Pull Requests
    async def list_pull_requests(self, repo_slug: str, state: str = "OPEN") -> List[Dict[str, Any]]:
        params = {"state": state}
        async with aiohttp.ClientSession() as session:
            data = await self._make_request(session, "GET", f"repositories/{self.workspace}/{repo_slug}/pullrequests", params=params)
            return data.get('values', [])
    
    async def get_pull_request(self, repo_slug: str, pr_id: int) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "GET", f"repositories/{self.workspace}/{repo_slug}/pullrequests/{pr_id}")
    
    async def create_pull_request(self, repo_slug: str, title: str, description: str, 
                                 source_branch: str, destination_branch: str = "main") -> Dict[str, Any]:
        data = {
            "title": title,
            "description": description,
            "source": {"branch": {"name": source_branch}},
            "destination": {"branch": {"name": destination_branch}},
        }
        
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "POST", f"repositories/{self.workspace}/{repo_slug}/pullrequests", data=data)
    
    async def update_pull_request(self, repo_slug: str, pr_id: int, title: str = None, 
                                 description: str = None, destination_branch: str = None) -> Dict[str, Any]:
        data = {}
        if title:
            data["title"] = title
        if description:
            data["description"] = description
        if destination_branch:
            data["destination"] = {"branch": {"name": destination_branch}}
        
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "PUT", f"repositories/{self.workspace}/{repo_slug}/pullrequests/{pr_id}", data=data)
    
    async def get_pr_diff(self, repo_slug: str, pr_id: int) -> str:
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/repositories/{self.workspace}/{repo_slug}/pullrequests/{pr_id}/diff"
            headers = {
                'Authorization': f'Basic {self.auth_header}',
                'User-Agent': 'BitbucketMCPServer/2.0'
            }
            
            # Create SSL context with certifi certificates
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30), ssl=ssl_context) as response:
                if response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"API error {response.status}: {error_text}")
                return await response.text()
    
    async def get_pr_commits(self, repo_slug: str, pr_id: int) -> List[Dict[str, Any]]:
        async with aiohttp.ClientSession() as session:
            data = await self._make_request(session, "GET", f"repositories/{self.workspace}/{repo_slug}/pullrequests/{pr_id}/commits")
            return data.get('values', [])
    
    async def add_pr_comment(self, repo_slug: str, pr_id: int, comment: str) -> Dict[str, Any]:
        data = {"content": {"raw": comment}}
        
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "POST", f"repositories/{self.workspace}/{repo_slug}/pullrequests/{pr_id}/comments", data=data)
    
    async def approve_pull_request(self, repo_slug: str, pr_id: int) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "POST", f"repositories/{self.workspace}/{repo_slug}/pullrequests/{pr_id}/approve")
    
    async def unapprove_pull_request(self, repo_slug: str, pr_id: int) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "DELETE", f"repositories/{self.workspace}/{repo_slug}/pullrequests/{pr_id}/approve")
    
    async def merge_pull_request(self, repo_slug: str, pr_id: int, merge_strategy: str = "merge_commit", message: str = "") -> Dict[str, Any]:
        data = {
            "type": merge_strategy,
            "message": message
        }
        
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "POST", f"repositories/{self.workspace}/{repo_slug}/pullrequests/{pr_id}/merge", data=data)
    
    async def decline_pull_request(self, repo_slug: str, pr_id: int) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "POST", f"repositories/{self.workspace}/{repo_slug}/pullrequests/{pr_id}/decline")
    
    async def get_pr_comments(self, repo_slug: str, pr_id: int) -> List[Dict[str, Any]]:
        """Get all comments on a pull request"""
        async with aiohttp.ClientSession() as session:
            data = await self._make_request(session, "GET", f"repositories/{self.workspace}/{repo_slug}/pullrequests/{pr_id}/comments")
            return data.get('values', [])
    
    async def get_pr_activity(self, repo_slug: str, pr_id: int) -> List[Dict[str, Any]]:
        """Get activity log for a pull request"""
        async with aiohttp.ClientSession() as session:
            data = await self._make_request(session, "GET", f"repositories/{self.workspace}/{repo_slug}/pullrequests/{pr_id}/activity")
            return data.get('values', [])
    
    # Issues
    async def list_issues(self, repo_slug: str, status: str = None) -> List[Dict[str, Any]]:
        params = {}
        if status:
            params["status"] = status
        
        async with aiohttp.ClientSession() as session:
            data = await self._make_request(session, "GET", f"repositories/{self.workspace}/{repo_slug}/issues", params=params)
            return data.get('values', [])
    
    async def get_issue(self, repo_slug: str, issue_id: int) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "GET", f"repositories/{self.workspace}/{repo_slug}/issues/{issue_id}")
    
    async def create_issue(self, repo_slug: str, title: str, content: str, kind: str = "bug", priority: str = "major") -> Dict[str, Any]:
        data = {
            "title": title,
            "content": {"raw": content},
            "kind": kind,
            "priority": priority
        }
        
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "POST", f"repositories/{self.workspace}/{repo_slug}/issues", data=data)
    
    async def update_issue(self, repo_slug: str, issue_id: int, title: str = None, 
                          content: str = None, status: str = None, priority: str = None) -> Dict[str, Any]:
        data = {}
        if title:
            data["title"] = title
        if content:
            data["content"] = {"raw": content}
        if status:
            data["status"] = status
        if priority:
            data["priority"] = priority
        
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "PUT", f"repositories/{self.workspace}/{repo_slug}/issues/{issue_id}", data=data)
    
    async def add_issue_comment(self, repo_slug: str, issue_id: int, comment: str) -> Dict[str, Any]:
        data = {"content": {"raw": comment}}
        
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "POST", f"repositories/{self.workspace}/{repo_slug}/issues/{issue_id}/comments", data=data)
    
    # Pipelines
    async def list_pipelines(self, repo_slug: str) -> List[Dict[str, Any]]:
        async with aiohttp.ClientSession() as session:
            data = await self._make_request(session, "GET", f"repositories/{self.workspace}/{repo_slug}/pipelines")
            return data.get('values', [])
    
    async def get_pipeline(self, repo_slug: str, pipeline_uuid: str) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "GET", f"repositories/{self.workspace}/{repo_slug}/pipelines/{pipeline_uuid}")
    
    async def trigger_pipeline(self, repo_slug: str, branch: str = "main") -> Dict[str, Any]:
        data = {
            "target": {
                "type": "pipeline_ref_target",
                "ref_type": "branch",
                "ref_name": branch
            }
        }
        
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "POST", f"repositories/{self.workspace}/{repo_slug}/pipelines", data=data)
    
    async def stop_pipeline(self, repo_slug: str, pipeline_uuid: str) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "POST", f"repositories/{self.workspace}/{repo_slug}/pipelines/{pipeline_uuid}/stopPipeline")
    
    # Webhooks
    async def list_webhooks(self, repo_slug: str) -> List[Dict[str, Any]]:
        async with aiohttp.ClientSession() as session:
            data = await self._make_request(session, "GET", f"repositories/{self.workspace}/{repo_slug}/hooks")
            return data.get('values', [])
    
    async def create_webhook(self, repo_slug: str, url: str, events: List[str], active: bool = True) -> Dict[str, Any]:
        data = {
            "url": url,
            "events": events,
            "active": active
        }
        
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "POST", f"repositories/{self.workspace}/{repo_slug}/hooks", data=data)
    
    async def delete_webhook(self, repo_slug: str, webhook_uid: str) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "DELETE", f"repositories/{self.workspace}/{repo_slug}/hooks/{webhook_uid}")
    
    # Workspace
    async def get_workspace(self) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "GET", f"workspaces/{self.workspace}")
    
    async def list_workspace_members(self) -> List[Dict[str, Any]]:
        async with aiohttp.ClientSession() as session:
            data = await self._make_request(session, "GET", f"workspaces/{self.workspace}/members")
            return data.get('values', [])
    
    async def list_workspace_projects(self) -> List[Dict[str, Any]]:
        async with aiohttp.ClientSession() as session:
            data = await self._make_request(session, "GET", f"workspaces/{self.workspace}/projects")
            return data.get('values', [])
    
    async def create_project(self, name: str, key: str, description: str = "", is_private: bool = True) -> Dict[str, Any]:
        data = {
            "name": name,
            "key": key,
            "description": description,
            "is_private": is_private
        }
        
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "POST", f"workspaces/{self.workspace}/projects", data=data)
    
    # User
    async def get_current_user(self) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "GET", "user")
    
    async def get_user(self, username: str) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "GET", f"users/{username}")
    
    # Snippets
    async def list_snippets(self) -> List[Dict[str, Any]]:
        async with aiohttp.ClientSession() as session:
            data = await self._make_request(session, "GET", f"snippets/{self.workspace}")
            return data.get('values', [])
    
    async def create_snippet(self, title: str, filename: str, content: str, is_private: bool = True) -> Dict[str, Any]:
        data = {
            "title": title,
            "is_private": is_private,
            "files": {
                filename: {"content": content}
            }
        }
        
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "POST", f"snippets/{self.workspace}", data=data)


# Global API instance
api: Optional[BitbucketAPI] = None

# Create the FastMCP server
mcp = FastMCP("bitbucket-server-extended")

# === REPOSITORY TOOLS ===

@mcp.tool()
async def list_repositories() -> str:
    """List all repositories in the workspace"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        repos = await api.list_repositories()
        repos_info = []
        for repo in repos:
            repos_info.append({
                "name": repo.get("name"),
                "full_name": repo.get("full_name"),
                "description": repo.get("description", ""),
                "language": repo.get("language", ""),
                "is_private": repo.get("is_private", False)
            })
        
        return json.dumps(repos_info, indent=2)
    except Exception as e:
        raise Exception(f"Error listing repositories: {str(e)}")

@mcp.tool()
async def get_repository(repo_slug: str) -> str:
    """Get details about a specific repository"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        repo = await api.get_repository(repo_slug)
        return json.dumps(repo, indent=2)
    except Exception as e:
        raise Exception(f"Error getting repository: {str(e)}")

@mcp.tool()
async def create_repository(repo_slug: str, is_private: bool = True, description: str = "", 
                           language: str = "", has_issues: bool = True, has_wiki: bool = True) -> str:
    """Create a new repository"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        repo = await api.create_repository(repo_slug, is_private, description, language, has_issues, has_wiki)
        return f"Created repository: {repo.get('full_name')}"
    except Exception as e:
        raise Exception(f"Error creating repository: {str(e)}")

@mcp.tool()
async def update_repository(repo_slug: str, description: str = None, is_private: bool = None, language: str = None) -> str:
    """Update repository settings"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        repo = await api.update_repository(repo_slug, description, is_private, language)
        return f"Updated repository: {repo.get('full_name')}"
    except Exception as e:
        raise Exception(f"Error updating repository: {str(e)}")

@mcp.tool()
async def delete_repository(repo_slug: str) -> str:
    """Delete a repository"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        await api.delete_repository(repo_slug)
        return f"Deleted repository: {repo_slug}"
    except Exception as e:
        raise Exception(f"Error deleting repository: {str(e)}")

@mcp.tool()
async def fork_repository(repo_slug: str, name: str = None, workspace: str = None) -> str:
    """Fork a repository"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        fork = await api.fork_repository(repo_slug, name, workspace)
        return f"Forked repository to: {fork.get('full_name')}"
    except Exception as e:
        raise Exception(f"Error forking repository: {str(e)}")

# === BRANCH & TAG TOOLS ===

@mcp.tool()
async def list_branches(repo_slug: str) -> str:
    """List branches in a repository"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        branches = await api.list_branches(repo_slug)
        return json.dumps(branches, indent=2)
    except Exception as e:
        raise Exception(f"Error listing branches: {str(e)}")

@mcp.tool()
async def get_branch(repo_slug: str, branch_name: str) -> str:
    """Get specific branch details"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        branch = await api.get_branch(repo_slug, branch_name)
        return json.dumps(branch, indent=2)
    except Exception as e:
        raise Exception(f"Error getting branch: {str(e)}")

@mcp.tool()
async def create_branch(repo_slug: str, branch_name: str, target_hash: str) -> str:
    """Create a new branch"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        branch = await api.create_branch(repo_slug, branch_name, target_hash)
        return f"Created branch: {branch.get('name')}"
    except Exception as e:
        raise Exception(f"Error creating branch: {str(e)}")

@mcp.tool()
async def delete_branch(repo_slug: str, branch_name: str) -> str:
    """Delete a branch"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        await api.delete_branch(repo_slug, branch_name)
        return f"Deleted branch: {branch_name}"
    except Exception as e:
        raise Exception(f"Error deleting branch: {str(e)}")

@mcp.tool()
async def list_tags(repo_slug: str) -> str:
    """List tags in a repository"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        tags = await api.list_tags(repo_slug)
        return json.dumps(tags, indent=2)
    except Exception as e:
        raise Exception(f"Error listing tags: {str(e)}")

@mcp.tool()
async def create_tag(repo_slug: str, tag_name: str, target_hash: str) -> str:
    """Create a new tag"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        tag = await api.create_tag(repo_slug, tag_name, target_hash)
        return f"Created tag: {tag.get('name')}"
    except Exception as e:
        raise Exception(f"Error creating tag: {str(e)}")

# === COMMIT TOOLS ===

@mcp.tool()
async def list_commits(repo_slug: str, branch: str = None, path: str = None) -> str:
    """List commits in a repository"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        commits = await api.list_commits(repo_slug, branch, path)
        return json.dumps(commits, indent=2)
    except Exception as e:
        raise Exception(f"Error listing commits: {str(e)}")

@mcp.tool()
async def get_commit(repo_slug: str, commit_hash: str) -> str:
    """Get specific commit details"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        commit = await api.get_commit(repo_slug, commit_hash)
        return json.dumps(commit, indent=2)
    except Exception as e:
        raise Exception(f"Error getting commit: {str(e)}")

@mcp.tool()
async def get_commit_diff(repo_slug: str, commit_hash: str) -> str:
    """Get diff for a specific commit"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        diff = await api.get_commit_diff(repo_slug, commit_hash)
        return diff
    except Exception as e:
        raise Exception(f"Error getting commit diff: {str(e)}")

@mcp.tool()
async def add_commit_comment(repo_slug: str, commit_hash: str, comment: str) -> str:
    """Add a comment to a commit"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        result = await api.add_commit_comment(repo_slug, commit_hash, comment)
        return f"Added comment to commit {commit_hash}"
    except Exception as e:
        raise Exception(f"Error adding commit comment: {str(e)}")

# === SOURCE CODE TOOLS ===

@mcp.tool()
async def get_file_content(repo_slug: str, file_path: str, branch: str = "main") -> str:
    """Get the content of a file from a repository"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        content = await api.get_file_content(repo_slug, file_path, branch)
        return f"File: {file_path} (branch: {branch})\n\n{content}"
    except Exception as e:
        raise Exception(f"Error getting file content: {str(e)}")

@mcp.tool()
async def list_directory(repo_slug: str, path: str = "", branch: str = "main") -> str:
    """List contents of a directory in a repository"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        items = await api.list_directory(repo_slug, path, branch)
        return json.dumps(items, indent=2)
    except Exception as e:
        raise Exception(f"Error listing directory: {str(e)}")

@mcp.tool()
async def get_file_metadata(repo_slug: str, file_path: str, branch: str = "main") -> str:
    """Get metadata for a file"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        metadata = await api.get_file_metadata(repo_slug, file_path, branch)
        return json.dumps(metadata, indent=2)
    except Exception as e:
        raise Exception(f"Error getting file metadata: {str(e)}")

# === PULL REQUEST TOOLS ===

@mcp.tool()
async def list_pull_requests(repo_slug: str, state: str = "OPEN") -> str:
    """List pull requests in a repository"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        prs = await api.list_pull_requests(repo_slug, state)
        return json.dumps(prs, indent=2)
    except Exception as e:
        raise Exception(f"Error listing pull requests: {str(e)}")

@mcp.tool()
async def get_pull_request(repo_slug: str, pr_id: int) -> str:
    """Get details about a specific pull request"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        pr = await api.get_pull_request(repo_slug, pr_id)
        return json.dumps(pr, indent=2)
    except Exception as e:
        raise Exception(f"Error getting pull request: {str(e)}")

@mcp.tool()
async def create_pull_request(repo_slug: str, title: str, description: str, source_branch: str, destination_branch: str = "main") -> str:
    """Create a new pull request"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        pr = await api.create_pull_request(repo_slug, title, description, source_branch, destination_branch)
        return f"Created pull request #{pr.get('id')}: {pr.get('title')}"
    except Exception as e:
        raise Exception(f"Error creating pull request: {str(e)}")

@mcp.tool()
async def update_pull_request(repo_slug: str, pr_id: int, title: str = None, description: str = None, destination_branch: str = None) -> str:
    """Update a pull request"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        pr = await api.update_pull_request(repo_slug, pr_id, title, description, destination_branch)
        return f"Updated pull request #{pr.get('id')}"
    except Exception as e:
        raise Exception(f"Error updating pull request: {str(e)}")

@mcp.tool()
async def get_pr_diff(repo_slug: str, pr_id: int) -> str:
    """Get diff for a pull request"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        diff = await api.get_pr_diff(repo_slug, pr_id)
        return diff
    except Exception as e:
        raise Exception(f"Error getting PR diff: {str(e)}")

@mcp.tool()
async def get_pr_commits(repo_slug: str, pr_id: int) -> str:
    """Get commits in a pull request"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        commits = await api.get_pr_commits(repo_slug, pr_id)
        return json.dumps(commits, indent=2)
    except Exception as e:
        raise Exception(f"Error getting PR commits: {str(e)}")

@mcp.tool()
async def add_pr_comment(repo_slug: str, pr_id: int, comment: str) -> str:
    """Add a comment to a pull request"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        result = await api.add_pr_comment(repo_slug, pr_id, comment)
        return f"Added comment to PR #{pr_id}"
    except Exception as e:
        raise Exception(f"Error adding PR comment: {str(e)}")

@mcp.tool()
async def approve_pull_request(repo_slug: str, pr_id: int) -> str:
    """Approve a pull request"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        result = await api.approve_pull_request(repo_slug, pr_id)
        return f"Approved pull request #{pr_id}"
    except Exception as e:
        raise Exception(f"Error approving pull request: {str(e)}")

@mcp.tool()
async def unapprove_pull_request(repo_slug: str, pr_id: int) -> str:
    """Remove approval from a pull request"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        result = await api.unapprove_pull_request(repo_slug, pr_id)
        return f"Removed approval from pull request #{pr_id}"
    except Exception as e:
        raise Exception(f"Error removing approval from pull request: {str(e)}")

@mcp.tool()
async def merge_pull_request(repo_slug: str, pr_id: int, merge_strategy: str = "merge_commit", message: str = "") -> str:
    """Merge a pull request"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        result = await api.merge_pull_request(repo_slug, pr_id, merge_strategy, message)
        return f"Merged pull request #{pr_id}"
    except Exception as e:
        raise Exception(f"Error merging pull request: {str(e)}")

@mcp.tool()
async def decline_pull_request(repo_slug: str, pr_id: int) -> str:
    """Decline/close a pull request"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        result = await api.decline_pull_request(repo_slug, pr_id)
        return f"Declined pull request #{pr_id}"
    except Exception as e:
        raise Exception(f"Error declining pull request: {str(e)}")

@mcp.tool()
async def get_pr_comments(repo_slug: str, pr_id: int) -> str:
    """Get all comments on a pull request. Returns comment content, author, and metadata."""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        comments = await api.get_pr_comments(repo_slug, pr_id)
        comment_info = []
        for comment in comments:
            comment_info.append({
                "id": comment.get("id"),
                "content": comment.get("content", {}).get("raw", ""),
                "author": comment.get("user", {}).get("display_name", "Unknown"),
                "created_on": comment.get("created_on"),
                "updated_on": comment.get("updated_on"),
                "deleted": comment.get("deleted", False),
                "inline": comment.get("inline"),
                "parent_id": comment.get("parent", {}).get("id") if comment.get("parent") else None
            })
        
        return json.dumps(comment_info, indent=2)
    except Exception as e:
        raise Exception(f"Error getting PR comments: {str(e)}")

@mcp.tool()
async def get_pr_activity(repo_slug: str, pr_id: int) -> str:
    """Get activity log for a pull request including comments, approvals, and updates."""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        activities = await api.get_pr_activity(repo_slug, pr_id)
        activity_info = []
        for activity in activities:
            activity_entry = {}
            
            if "comment" in activity:
                comment = activity["comment"]
                activity_entry = {
                    "type": "comment",
                    "id": comment.get("id"),
                    "content": comment.get("content", {}).get("raw", ""),
                    "author": comment.get("user", {}).get("display_name", "Unknown"),
                    "created_on": comment.get("created_on"),
                    "inline": comment.get("inline")
                }
            elif "approval" in activity:
                approval = activity["approval"]
                activity_entry = {
                    "type": "approval",
                    "user": approval.get("user", {}).get("display_name", "Unknown"),
                    "date": approval.get("date")
                }
            elif "update" in activity:
                update = activity["update"]
                activity_entry = {
                    "type": "update",
                    "author": update.get("author", {}).get("display_name", "Unknown"),
                    "date": update.get("date"),
                    "state": update.get("state")
                }
            elif "changes_requested" in activity:
                cr = activity["changes_requested"]
                activity_entry = {
                    "type": "changes_requested",
                    "user": cr.get("user", {}).get("display_name", "Unknown"),
                    "date": cr.get("date")
                }
            else:
                activity_entry = {"type": "unknown", "raw": str(activity)[:200]}
            
            activity_info.append(activity_entry)
        
        return json.dumps(activity_info, indent=2)
    except Exception as e:
        raise Exception(f"Error getting PR activity: {str(e)}")

# === ISSUE TOOLS ===

@mcp.tool()
async def list_issues(repo_slug: str, status: str = None) -> str:
    """List issues in a repository"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        issues = await api.list_issues(repo_slug, status)
        return json.dumps(issues, indent=2)
    except Exception as e:
        raise Exception(f"Error listing issues: {str(e)}")

@mcp.tool()
async def get_issue(repo_slug: str, issue_id: int) -> str:
    """Get issue details"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        issue = await api.get_issue(repo_slug, issue_id)
        return json.dumps(issue, indent=2)
    except Exception as e:
        raise Exception(f"Error getting issue: {str(e)}")

@mcp.tool()
async def create_issue(repo_slug: str, title: str, content: str, kind: str = "bug", priority: str = "major") -> str:
    """Create a new issue"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        issue = await api.create_issue(repo_slug, title, content, kind, priority)
        return f"Created issue #{issue.get('id')}: {issue.get('title')}"
    except Exception as e:
        raise Exception(f"Error creating issue: {str(e)}")

@mcp.tool()
async def update_issue(repo_slug: str, issue_id: int, title: str = None, content: str = None, status: str = None, priority: str = None) -> str:
    """Update an issue"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        issue = await api.update_issue(repo_slug, issue_id, title, content, status, priority)
        return f"Updated issue #{issue.get('id')}"
    except Exception as e:
        raise Exception(f"Error updating issue: {str(e)}")

@mcp.tool()
async def add_issue_comment(repo_slug: str, issue_id: int, comment: str) -> str:
    """Add a comment to an issue"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        result = await api.add_issue_comment(repo_slug, issue_id, comment)
        return f"Added comment to issue #{issue_id}"
    except Exception as e:
        raise Exception(f"Error adding issue comment: {str(e)}")

# === PIPELINE TOOLS ===

@mcp.tool()
async def list_pipelines(repo_slug: str) -> str:
    """List pipelines in a repository"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        pipelines = await api.list_pipelines(repo_slug)
        return json.dumps(pipelines, indent=2)
    except Exception as e:
        raise Exception(f"Error listing pipelines: {str(e)}")

@mcp.tool()
async def get_pipeline(repo_slug: str, pipeline_uuid: str) -> str:
    """Get pipeline details"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        pipeline = await api.get_pipeline(repo_slug, pipeline_uuid)
        return json.dumps(pipeline, indent=2)
    except Exception as e:
        raise Exception(f"Error getting pipeline: {str(e)}")

@mcp.tool()
async def trigger_pipeline(repo_slug: str, branch: str = "main") -> str:
    """Trigger a new pipeline"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        pipeline = await api.trigger_pipeline(repo_slug, branch)
        return f"Triggered pipeline on branch {branch}"
    except Exception as e:
        raise Exception(f"Error triggering pipeline: {str(e)}")

@mcp.tool()
async def stop_pipeline(repo_slug: str, pipeline_uuid: str) -> str:
    """Stop a running pipeline"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        result = await api.stop_pipeline(repo_slug, pipeline_uuid)
        return f"Stopped pipeline {pipeline_uuid}"
    except Exception as e:
        raise Exception(f"Error stopping pipeline: {str(e)}")

# === WEBHOOK TOOLS ===

@mcp.tool()
async def list_webhooks(repo_slug: str) -> str:
    """List webhooks in a repository"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        webhooks = await api.list_webhooks(repo_slug)
        return json.dumps(webhooks, indent=2)
    except Exception as e:
        raise Exception(f"Error listing webhooks: {str(e)}")

@mcp.tool()
async def create_webhook(repo_slug: str, url: str, events: List[str], active: bool = True) -> str:
    """Create a new webhook"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        webhook = await api.create_webhook(repo_slug, url, events, active)
        return f"Created webhook: {webhook.get('uuid')}"
    except Exception as e:
        raise Exception(f"Error creating webhook: {str(e)}")

@mcp.tool()
async def delete_webhook(repo_slug: str, webhook_uid: str) -> str:
    """Delete a webhook"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        await api.delete_webhook(repo_slug, webhook_uid)
        return f"Deleted webhook: {webhook_uid}"
    except Exception as e:
        raise Exception(f"Error deleting webhook: {str(e)}")

# === WORKSPACE TOOLS ===

@mcp.tool()
async def get_workspace() -> str:
    """Get workspace details"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        workspace = await api.get_workspace()
        return json.dumps(workspace, indent=2)
    except Exception as e:
        raise Exception(f"Error getting workspace: {str(e)}")

@mcp.tool()
async def list_workspace_members() -> str:
    """List workspace members"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        members = await api.list_workspace_members()
        return json.dumps(members, indent=2)
    except Exception as e:
        raise Exception(f"Error listing workspace members: {str(e)}")

@mcp.tool()
async def list_workspace_projects() -> str:
    """List projects in the workspace"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        projects = await api.list_workspace_projects()
        return json.dumps(projects, indent=2)
    except Exception as e:
        raise Exception(f"Error listing workspace projects: {str(e)}")

@mcp.tool()
async def create_project(name: str, key: str, description: str = "", is_private: bool = True) -> str:
    """Create a new project"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        project = await api.create_project(name, key, description, is_private)
        return f"Created project: {project.get('name')} ({project.get('key')})"
    except Exception as e:
        raise Exception(f"Error creating project: {str(e)}")

# === USER TOOLS ===

@mcp.tool()
async def get_current_user() -> str:
    """Get current authenticated user details"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        user = await api.get_current_user()
        return json.dumps(user, indent=2)
    except Exception as e:
        raise Exception(f"Error getting current user: {str(e)}")

@mcp.tool()
async def get_user(username: str) -> str:
    """Get user details"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        user = await api.get_user(username)
        return json.dumps(user, indent=2)
    except Exception as e:
        raise Exception(f"Error getting user: {str(e)}")

# === SNIPPET TOOLS ===

@mcp.tool()
async def list_snippets() -> str:
    """List snippets in the workspace"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        snippets = await api.list_snippets()
        return json.dumps(snippets, indent=2)
    except Exception as e:
        raise Exception(f"Error listing snippets: {str(e)}")

@mcp.tool()
async def create_snippet(title: str, filename: str, content: str, is_private: bool = True) -> str:
    """Create a new snippet"""
    global api
    if api is None:
        raise Exception("Bitbucket API not initialized.")
    
    try:
        snippet = await api.create_snippet(title, filename, content, is_private)
        return f"Created snippet: {snippet.get('id')}"
    except Exception as e:
        raise Exception(f"Error creating snippet: {str(e)}")


def _load_credentials_file(path: str) -> dict:
    """Load credentials from a key=value env file, ignoring comments and blanks."""
    creds = {}
    try:
        with open(os.path.expanduser(path), 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    creds[key.strip()] = value.strip()
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.debug(f"Could not read credentials file {path}: {e}")
    return creds


def main():
    """Main entry point"""
    global api
    
    try:
        # Get configuration from environment
        username = os.getenv('BITBUCKET_USERNAME')
        app_password = os.getenv('BITBUCKET_APP_PASSWORD')
        api_token = os.getenv('BITBUCKET_API_TOKEN')
        workspace = os.getenv('BITBUCKET_WORKSPACE')
        email = os.getenv('BITBUCKET_EMAIL')

        if len(sys.argv) >= 4:
            username = sys.argv[1]
            app_password = sys.argv[2]
            workspace = sys.argv[3]

        # Fallback: read from ~/.claude-agents/credentials.env if env vars are missing
        if not workspace or (not api_token and not all([username, app_password])):
            logger.info("Env vars incomplete, trying ~/.claude-agents/credentials.env")
            file_creds = _load_credentials_file('~/.claude-agents/credentials.env')
            if not workspace:
                workspace = file_creds.get('BITBUCKET_WORKSPACE', workspace)
            if not api_token:
                api_token = file_creds.get('BITBUCKET_API_TOKEN', api_token)
            if not email:
                email = file_creds.get('BITBUCKET_EMAIL', email)
            if not username:
                username = file_creds.get('BITBUCKET_USERNAME', username)
            if not app_password:
                app_password = file_creds.get('BITBUCKET_APP_PASSWORD', app_password)
            if api_token and email:
                # Ensure BITBUCKET_EMAIL is available for the API client
                os.environ['BITBUCKET_EMAIL'] = email

        # Validate required parameters
        if not workspace:
            logger.error("Missing BITBUCKET_WORKSPACE")
            logger.error("Set via env var or in ~/.claude-agents/credentials.env")
            sys.exit(1)

        if not api_token and not all([username, app_password]):
            logger.error("Missing required auth configuration")
            logger.error("Set BITBUCKET_API_TOKEN + BITBUCKET_EMAIL, or BITBUCKET_USERNAME + BITBUCKET_APP_PASSWORD")
            logger.error("Via env vars or ~/.claude-agents/credentials.env")
            sys.exit(1)

        # Initialize the API client (prefer API token over app password)
        api = BitbucketAPI(workspace=workspace, app_password=app_password, username=username, api_token=api_token)
        logger.info(f"Bitbucket MCP Server (Extended) configured for workspace: {workspace}")
        logger.info("Starting server with comprehensive API support...")
        
        # Run the server
        mcp.run()
            
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
