#!/usr/bin/env python3
"""
Linear Tasks Creation Script for Wedding WebApp SAAS Technical Debt

This script creates Linear tasks from the code analysis findings.
Requires Linear API key and team ID.

Usage:
    python scripts/create_linear_tasks.py --api-key YOUR_API_KEY --team-id YOUR_TEAM_ID

Environment variables (preferred):
    LINEAR_API_KEY=your_api_key
    LINEAR_TEAM_ID=your_team_id
"""

import json
import os
import sys
import argparse
import requests
from typing import Dict, List, Optional

class LinearTaskCreator:
    def __init__(self, api_key: str, team_id: str):
        self.api_key = api_key
        self.team_id = team_id
        self.base_url = "https://api.linear.app/graphql"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
    def create_epic(self, title: str, description: str, labels: List[str]) -> str:
        """Create an epic and return its ID"""
        query = """
        mutation CreateIssue($input: IssueCreateInput!) {
            issueCreate(input: $input) {
                success
                issue {
                    id
                    title
                }
            }
        }
        """
        
        variables = {
            "input": {
                "title": title,
                "description": description,
                "teamId": self.team_id,
                "priority": 1,  # High priority
                "labelIds": []  # Would need to map labels to IDs
            }
        }
        
        response = requests.post(
            self.base_url,
            headers=self.headers,
            json={"query": query, "variables": variables}
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("data", {}).get("issueCreate", {}).get("success"):
                return data["data"]["issueCreate"]["issue"]["id"]
        
        raise Exception(f"Failed to create epic: {response.text}")
    
    def create_task(self, title: str, description: str, priority: int = 3, 
                   estimate: Optional[int] = None, parent_id: Optional[str] = None) -> str:
        """Create a task and return its ID"""
        query = """
        mutation CreateIssue($input: IssueCreateInput!) {
            issueCreate(input: $input) {
                success
                issue {
                    id
                    title
                }
            }
        }
        """
        
        input_data = {
            "title": title,
            "description": description,
            "teamId": self.team_id,
            "priority": priority
        }
        
        if estimate:
            input_data["estimate"] = estimate
            
        if parent_id:
            input_data["parentId"] = parent_id
        
        variables = {"input": input_data}
        
        response = requests.post(
            self.base_url,
            headers=self.headers,
            json={"query": query, "variables": variables}
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("data", {}).get("issueCreate", {}).get("success"):
                return data["data"]["issueCreate"]["issue"]["id"]
        
        raise Exception(f"Failed to create task: {response.text}")

def load_tasks_data():
    """Load tasks data from JSON file"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(script_dir, '..', 'linear-tasks-import.json')
    
    with open(json_path, 'r') as f:
        return json.load(f)

def priority_to_number(priority_str: str) -> int:
    """Convert priority string to Linear priority number"""
    priority_map = {
        "Low": 4,
        "Low-Medium": 3,
        "Medium": 3,
        "High": 2,
        "Critical": 1
    }
    return priority_map.get(priority_str, 3)

def create_all_tasks(api_key: str, team_id: str, dry_run: bool = False):
    """Create all tasks from the JSON data"""
    creator = LinearTaskCreator(api_key, team_id)
    tasks_data = load_tasks_data()
    
    print("🚀 Starting Linear tasks creation...")
    print(f"Total story points: {tasks_data['metadata']['total_story_points']}")
    print(f"Total tasks to create: {tasks_data['metadata']['total_tasks']}")
    
    if dry_run:
        print("\n🔍 DRY RUN MODE - No tasks will be created")
        return
    
    # Create epic
    epic_data = tasks_data["epic"]
    print(f"\n📋 Creating epic: {epic_data['title']}")
    
    try:
        epic_id = creator.create_epic(
            title=epic_data["title"],
            description=epic_data["description"],
            labels=epic_data["labels"]
        )
        print(f"✅ Epic created with ID: {epic_id}")
    except Exception as e:
        print(f"❌ Failed to create epic: {e}")
        return
    
    # Create parent tasks and their children
    for parent_task in tasks_data["parent_tasks"]:
        print(f"\n📁 Creating parent task: {parent_task['title']}")
        
        try:
            parent_id = creator.create_task(
                title=parent_task["title"],
                description=parent_task["description"],
                priority=priority_to_number(parent_task["priority"]),
                estimate=parent_task["estimate"],
                parent_id=epic_id
            )
            print(f"✅ Parent task created with ID: {parent_id}")
            
            # Create child tasks
            for child_task in parent_task.get("children", []):
                print(f"  📝 Creating child task: {child_task['title']}")
                
                # Format description with acceptance criteria
                description = child_task["description"]
                if "acceptance_criteria" in child_task:
                    description += "\n\n**Acceptance Criteria:**\n"
                    for criteria in child_task["acceptance_criteria"]:
                        description += f"- [ ] {criteria}\n"
                
                child_id = creator.create_task(
                    title=child_task["title"],
                    description=description,
                    priority=priority_to_number(child_task["priority"]),
                    estimate=child_task["estimate"],
                    parent_id=parent_id
                )
                print(f"  ✅ Child task created with ID: {child_id}")
                
        except Exception as e:
            print(f"  ❌ Failed to create task: {e}")
            continue
    
    print(f"\n🎉 Task creation completed!")
    print("\n📊 Summary:")
    print(f"- Epic: {epic_data['title']}")
    print(f"- Parent tasks: {len(tasks_data['parent_tasks'])}")
    print(f"- Total story points: {tasks_data['metadata']['total_story_points']}")
    print(f"- Estimated duration: {tasks_data['metadata']['estimated_duration']}")

def main():
    parser = argparse.ArgumentParser(description="Create Linear tasks from code analysis")
    parser.add_argument("--api-key", help="Linear API key")
    parser.add_argument("--team-id", help="Linear team ID")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be created without actually creating")
    
    args = parser.parse_args()
    
    # Get credentials from args or environment
    api_key = args.api_key or os.getenv("LINEAR_API_KEY")
    team_id = args.team_id or os.getenv("LINEAR_TEAM_ID")
    
    if not api_key:
        print("❌ Error: LINEAR_API_KEY not provided")
        print("Set environment variable or use --api-key flag")
        sys.exit(1)
    
    if not team_id:
        print("❌ Error: LINEAR_TEAM_ID not provided")
        print("Set environment variable or use --team-id flag")
        sys.exit(1)
    
    try:
        create_all_tasks(api_key, team_id, args.dry_run)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()