"""
RMACD Tools Registry - Example Usage & Catalog
===============================================

Demonstrates the tools registry with real-world examples including:
- Common AI/agent tools
- MCP (Model Context Protocol) tools
- DevOps/infrastructure tools
- Data processing tools

Author: Kash Kashyap
"""

from rmacd_tools_registry import (
    ToolsRegistry,
    ToolDefinition,
    RMACDLevel,
    HITLLevel,
    DataClassification,
    create_registry,
    quick_register
)
import json
from pathlib import Path


def create_comprehensive_catalog() -> ToolsRegistry:
    """
    Create a comprehensive tools catalog with real-world examples.
    
    Returns:
        ToolsRegistry: Populated registry
    """
    
    try:
        print("\n" + "="*70)
        print("Creating Comprehensive RMACD Tools Catalog")
        print("="*70)
        
        registry = create_registry("comprehensive-v1")
        
        # =================================================================
        # READ LEVEL TOOLS - Near-Zero Risk
        # =================================================================
        print("\n[READ] Registering READ level tools...")
        
        read_tools = [
            {
                "tool_id": "web_search",
                "tool_name": "Web Search",
                "rmacd_level": "R",
                "description": "Search the web for information",
                "operations": ["query", "search", "retrieve"],
                "data_access": "public",
                "required_hitl": "auto",
                "tags": {"search", "web", "information"}
            },
            {
                "tool_id": "file_view",
                "tool_name": "File Viewer",
                "rmacd_level": "R",
                "description": "View file contents without modification",
                "operations": ["read", "display", "preview"],
                "data_access": "internal",
                "required_hitl": "logged",
                "tags": {"file", "read", "view"}
            },
            {
                "tool_id": "database_query",
                "tool_name": "Database Query (Read-Only)",
                "rmacd_level": "R",
                "description": "Execute SELECT queries on database",
                "operations": ["select", "query", "analyze"],
                "data_access": "confidential",
                "required_hitl": "logged",
                "tags": {"database", "query", "analytics"}
            },
            {
                "tool_id": "slack_read",
                "tool_name": "Slack Message Reader",
                "rmacd_level": "R",
                "description": "Read Slack messages and channels",
                "operations": ["read_messages", "search_messages"],
                "data_access": "internal",
                "required_hitl": "logged",
                "tags": {"slack", "communication", "read"}
            },
            {
                "tool_id": "metrics_monitor",
                "tool_name": "System Metrics Monitor",
                "rmacd_level": "R",
                "description": "Monitor system performance and health",
                "operations": ["monitor", "observe", "analyze"],
                "data_access": "internal",
                "required_hitl": "auto",
                "tags": {"monitoring", "metrics", "observability"}
            }
        ]
        
        for tool in read_tools:
            registry.register_tool(tool)
            print(f"  + {tool['tool_name']} ({tool['data_access']})")
        
        # =================================================================
        # MOVE LEVEL TOOLS - Low-Medium Risk
        # =================================================================
        print("\n[MOVE] Registering MOVE level tools...")
        
        move_tools = [
            {
                "tool_id": "file_move",
                "tool_name": "File Mover",
                "rmacd_level": "M",
                "description": "Move or rename files between locations",
                "operations": ["move", "rename", "relocate"],
                "data_access": "internal",
                "required_hitl": "notify",
                "tags": {"file", "move", "organize"}
            },
            {
                "tool_id": "github_transfer",
                "tool_name": "GitHub Repository Transfer",
                "rmacd_level": "M",
                "description": "Transfer repositories between organizations",
                "operations": ["transfer", "migrate"],
                "data_access": "internal",
                "required_hitl": "approve",
                "tags": {"github", "repository", "transfer"}
            },
            {
                "tool_id": "email_forward",
                "tool_name": "Email Forwarder",
                "rmacd_level": "M",
                "description": "Forward emails to different addresses",
                "operations": ["forward", "redirect"],
                "data_access": "confidential",
                "required_hitl": "notify",
                "tags": {"email", "forward", "communication"}
            },
            {
                "tool_id": "container_relocate",
                "tool_name": "Container Relocator",
                "rmacd_level": "M",
                "description": "Move containers between clusters",
                "operations": ["migrate", "relocate"],
                "data_access": "internal",
                "required_hitl": "approve",
                "tags": {"kubernetes", "container", "migration"}
            }
        ]
        
        for tool in move_tools:
            registry.register_tool(tool)
            print(f"  + {tool['tool_name']} ({tool['data_access']})")
        
        # =================================================================
        # ADD LEVEL TOOLS - Medium Risk
        # =================================================================
        print("\n[ADD] Registering ADD level tools...")
        
        add_tools = [
            {
                "tool_id": "file_create",
                "tool_name": "File Creator",
                "rmacd_level": "A",
                "description": "Create new files with content",
                "operations": ["create", "write", "generate"],
                "data_access": "internal",
                "required_hitl": "notify",
                "tags": {"file", "create", "write"}
            },
            {
                "tool_id": "github_create_repo",
                "tool_name": "GitHub Repository Creator",
                "rmacd_level": "A",
                "description": "Create new GitHub repositories",
                "operations": ["create_repository", "initialize"],
                "data_access": "internal",
                "required_hitl": "approve",
                "tags": {"github", "repository", "create"}
            },
            {
                "tool_id": "database_insert",
                "tool_name": "Database Record Creator",
                "rmacd_level": "A",
                "description": "Insert new records into database",
                "operations": ["insert", "create"],
                "data_access": "confidential",
                "required_hitl": "approve",
                "tags": {"database", "insert", "create"}
            },
            {
                "tool_id": "slack_post",
                "tool_name": "Slack Message Poster",
                "rmacd_level": "A",
                "description": "Post messages to Slack channels",
                "operations": ["post", "send", "publish"],
                "data_access": "internal",
                "required_hitl": "notify",
                "tags": {"slack", "message", "post"}
            },
            {
                "tool_id": "kubernetes_deploy",
                "tool_name": "Kubernetes Deployment",
                "rmacd_level": "A",
                "description": "Deploy new applications to Kubernetes",
                "operations": ["deploy", "provision", "create"],
                "data_access": "internal",
                "required_hitl": "approve",
                "tags": {"kubernetes", "deploy", "provision"}
            },
            {
                "tool_id": "aws_s3_upload",
                "tool_name": "AWS S3 Uploader",
                "rmacd_level": "A",
                "description": "Upload files to S3 buckets",
                "operations": ["upload", "store"],
                "data_access": "confidential",
                "required_hitl": "logged",
                "tags": {"aws", "s3", "upload"}
            }
        ]
        
        for tool in add_tools:
            registry.register_tool(tool)
            print(f"  + {tool['tool_name']} ({tool['data_access']})")
        
        # =================================================================
        # CHANGE LEVEL TOOLS - High Risk
        # =================================================================
        print("\n[CHANGE] Registering CHANGE level tools...")
        
        change_tools = [
            {
                "tool_id": "file_edit",
                "tool_name": "File Editor",
                "rmacd_level": "C",
                "description": "Modify existing file contents",
                "operations": ["edit", "modify", "update"],
                "data_access": "confidential",
                "required_hitl": "approve",
                "tags": {"file", "edit", "modify"}
            },
            {
                "tool_id": "github_commit",
                "tool_name": "GitHub Commit Creator",
                "rmacd_level": "C",
                "description": "Commit changes to GitHub repositories",
                "operations": ["commit", "push", "modify"],
                "data_access": "internal",
                "required_hitl": "approve",
                "tags": {"github", "commit", "modify"}
            },
            {
                "tool_id": "database_update",
                "tool_name": "Database Record Updater",
                "rmacd_level": "C",
                "description": "Update existing database records",
                "operations": ["update", "modify"],
                "data_access": "confidential",
                "required_hitl": "elevated",
                "tags": {"database", "update", "modify"}
            },
            {
                "tool_id": "user_permission_modify",
                "tool_name": "User Permission Manager",
                "rmacd_level": "C",
                "description": "Modify user access permissions",
                "operations": ["grant", "revoke", "modify"],
                "data_access": "restricted",
                "required_hitl": "elevated",
                "tags": {"security", "permissions", "access"}
            },
            {
                "tool_id": "config_update",
                "tool_name": "Configuration Updater",
                "rmacd_level": "C",
                "description": "Update system configuration files",
                "operations": ["update", "reconfigure"],
                "data_access": "internal",
                "required_hitl": "approve",
                "tags": {"config", "system", "update"}
            },
            {
                "tool_id": "dns_record_modify",
                "tool_name": "DNS Record Manager",
                "rmacd_level": "C",
                "description": "Modify DNS records and zones",
                "operations": ["update", "modify"],
                "data_access": "internal",
                "required_hitl": "elevated",
                "tags": {"dns", "network", "modify"}
            }
        ]
        
        for tool in change_tools:
            registry.register_tool(tool)
            print(f"  + {tool['tool_name']} ({tool['data_access']})")
        
        # =================================================================
        # DELETE LEVEL TOOLS - Critical Risk
        # =================================================================
        print("\n[DELETE]  Registering DELETE level tools...")
        
        delete_tools = [
            {
                "tool_id": "file_delete",
                "tool_name": "File Deleter",
                "rmacd_level": "D",
                "description": "Permanently delete files",
                "operations": ["delete", "remove", "destroy"],
                "data_access": "confidential",
                "required_hitl": "elevated",
                "tags": {"file", "delete", "destroy"}
            },
            {
                "tool_id": "github_delete_repo",
                "tool_name": "GitHub Repository Deleter",
                "rmacd_level": "D",
                "description": "Delete GitHub repositories permanently",
                "operations": ["delete", "destroy"],
                "data_access": "internal",
                "required_hitl": "elevated",
                "tags": {"github", "delete", "destroy"}
            },
            {
                "tool_id": "database_delete",
                "tool_name": "Database Record Deleter",
                "rmacd_level": "D",
                "description": "Delete records from database",
                "operations": ["delete", "remove"],
                "data_access": "restricted",
                "required_hitl": "prohibited",  # Requires manual intervention
                "tags": {"database", "delete", "remove"}
            },
            {
                "tool_id": "user_account_delete",
                "tool_name": "User Account Deleter",
                "rmacd_level": "D",
                "description": "Delete user accounts and data",
                "operations": ["delete", "deactivate", "purge"],
                "data_access": "restricted",
                "required_hitl": "prohibited",
                "tags": {"security", "user", "delete"}
            },
            {
                "tool_id": "s3_bucket_delete",
                "tool_name": "S3 Bucket Deleter",
                "rmacd_level": "D",
                "description": "Delete S3 buckets and all contents",
                "operations": ["delete", "purge"],
                "data_access": "confidential",
                "required_hitl": "elevated",
                "tags": {"aws", "s3", "delete"}
            },
            {
                "tool_id": "kubernetes_delete",
                "tool_name": "Kubernetes Resource Deleter",
                "rmacd_level": "D",
                "description": "Delete Kubernetes deployments and resources",
                "operations": ["delete", "destroy"],
                "data_access": "internal",
                "required_hitl": "elevated",
                "tags": {"kubernetes", "delete", "destroy"}
            }
        ]
        
        for tool in delete_tools:
            registry.register_tool(tool)
            print(f"  + {tool['tool_name']} ({tool['data_access']})")
        
        print(f"\n[OK] Registry created successfully with {len(registry)} tools")
        return registry
        
    except Exception as e:
        print(f"\n[ERROR] Error creating catalog: {e}")
        raise


def demonstrate_registry_features(registry: ToolsRegistry):
    """
    Demonstrate all registry features with comprehensive examples.
    
    Args:
        registry: Populated tools registry
    """
    
    try:
        print("\n" + "="*70)
        print("Demonstrating Registry Features")
        print("="*70)
        
        # Feature 1: Get tools by RMACD level
        print("\n[SEARCH] Feature 1: Query Tools by RMACD Level")
        print("-" * 70)
        for level in RMACDLevel:
            tools = registry.get_tools_by_level(level)
            print(f"{level.code} ({level.operation_name}): {len(tools)} tools")
            for tool in tools[:2]:  # Show first 2
                print(f"  - {tool.tool_name} (risk: {tool.risk_score})")
        
        # Feature 2: Tool lookup and details
        print("\n[INFO] Feature 2: Tool Lookup and Details")
        print("-" * 70)
        test_tool = registry.get_tool("database_update")
        if test_tool:
            print(f"Tool: {test_tool.tool_name}")
            print(f"  RMACD Level: {test_tool.rmacd_level.code} ({test_tool.rmacd_level.operation_name})")
            print(f"  Risk Level: {test_tool.rmacd_level.risk_level}")
            print(f"  Data Access: {test_tool.data_access.code if test_tool.data_access else 'N/A'}")
            print(f"  HITL Required: {test_tool.required_hitl.code if test_tool.required_hitl else 'N/A'}")
            print(f"  Risk Score: {test_tool.risk_score}/10")
            print(f"  Operations: {', '.join(test_tool.operations)}")
        
        # Feature 3: Permission validation
        print("\n[SECURITY] Feature 3: Permission Validation")
        print("-" * 70)
        
        # Test case 1: Observer profile (Read-only)
        print("\nTest Case 1: Observer Profile (Read-only)")
        allowed_levels = ["R"]
        test_tools = ["web_search", "file_create", "database_delete"]
        
        for tool_id in test_tools:
            is_allowed, reason = registry.validate_tool_access(
                tool_id, allowed_levels, "internal"
            )
            status = "[OK] ALLOWED" if is_allowed else "[ERROR] DENIED"
            print(f"  {status}: {tool_id}")
            print(f"    Reason: {reason}")
        
        # Test case 2: Developer profile (Read, Move, Add, Change)
        print("\nTest Case 2: Developer Profile (R, M, A, C)")
        allowed_levels = ["R", "M", "A", "C"]
        test_tools = ["github_commit", "database_delete", "slack_post"]
        
        for tool_id in test_tools:
            is_allowed, reason = registry.validate_tool_access(
                tool_id, allowed_levels, "confidential"
            )
            status = "[OK] ALLOWED" if is_allowed else "[ERROR] DENIED"
            print(f"  {status}: {tool_id}")
            print(f"    Reason: {reason}")
        
        # Feature 4: Workflow risk analysis
        print("\n[WARNING]  Feature 4: Workflow Risk Analysis")
        print("-" * 70)
        
        workflows = [
            {
                "name": "Data Analysis Pipeline",
                "tools": ["web_search", "database_query", "file_view", "slack_post"]
            },
            {
                "name": "Deployment Workflow",
                "tools": ["github_commit", "kubernetes_deploy", "dns_record_modify"]
            },
            {
                "name": "Dangerous Cleanup",
                "tools": ["database_delete", "s3_bucket_delete", "user_account_delete"]
            }
        ]
        
        for workflow in workflows:
            print(f"\n{workflow['name']}:")
            risk_analysis = registry.calculate_workflow_risk(workflow['tools'])
            print(f"  Total Risk: {risk_analysis['total_risk']}/10")
            print(f"  Max Risk: {risk_analysis['max_risk']}/10")
            print(f"  Avg Risk: {risk_analysis['avg_risk']}/10")
            print(f"  Highest RMACD: {risk_analysis['highest_rmacd']}")
            print(f"  Highest Risk Tool: {risk_analysis['highest_risk_tool']}")
            print(f"  Risk Distribution: {risk_analysis['risk_distribution']}")
        
        # Feature 5: Registry statistics
        print("\n[STATS] Feature 5: Registry Statistics")
        print("-" * 70)
        stats = registry.get_stats()
        print(f"Registry ID: {stats['registry_id']}")
        print(f"Total Tools: {stats['total_tools']}")
        print(f"Average Risk Score: {stats['avg_risk_score']}/10")
        print(f"Tools by Level:")
        for level, count in stats['by_level'].items():
            print(f"  {level}: {count} tools")
        
        # Feature 6: Audit log
        print("\n[LOG] Feature 6: Audit Log (Last 5 entries)")
        print("-" * 70)
        audit_entries = registry.get_audit_log(last_n=5)
        for entry in audit_entries:
            print(f"{entry['timestamp']}: {entry['action']} - {entry['tool_id']}")
        
        print("\n[OK] Feature demonstration complete!")
        
    except Exception as e:
        print(f"\n[ERROR] Error demonstrating features: {e}")
        raise


def demonstrate_export_import(registry: ToolsRegistry):
    """
    Demonstrate JSON export/import capabilities.
    
    Args:
        registry: Registry to export
    """
    
    try:
        print("\n" + "="*70)
        print("Demonstrating Export/Import")
        print("="*70)
        
        # Export to JSON
        export_path = Path("rmacd_tools_catalog.json")
        print(f"\n[EXPORT] Exporting registry to: {export_path}")
        success = registry.export_to_json(export_path)
        
        if success:
            print("[OK] Export successful!")
            
            # Show file info
            file_size = export_path.stat().st_size
            print(f"   File size: {file_size:,} bytes")
            
            # Load and show sample
            with open(export_path, 'r') as f:
                data = json.load(f)
            print(f"   Tool count: {data['tool_count']}")
            print(f"   Version: {data['version']}")
            
            # Test import into new registry
            print(f"\n[IMPORT] Testing import into new registry...")
            new_registry = create_registry("imported-v1")
            import_success = new_registry.import_from_json(export_path)
            
            if import_success:
                print("[OK] Import successful!")
                print(f"   Tools imported: {len(new_registry)}")
                
                # Verify data integrity
                print("\n[SEARCH] Verifying data integrity...")
                original_stats = registry.get_stats()
                imported_stats = new_registry.get_stats()
                
                if original_stats['total_tools'] == imported_stats['total_tools']:
                    print("[OK] Tool count matches!")
                else:
                    print("[WARNING]  Tool count mismatch!")
                
                if original_stats['by_level'] == imported_stats['by_level']:
                    print("[OK] RMACD distribution matches!")
                else:
                    print("[WARNING]  RMACD distribution mismatch!")
            else:
                print("[ERROR] Import failed!")
        else:
            print("[ERROR] Export failed!")
        
    except Exception as e:
        print(f"\n[ERROR] Error in export/import: {e}")
        raise


def create_permission_profiles():
    """
    Create example permission profiles that can use the registry.
    """
    
    print("\n" + "="*70)
    print("Example Permission Profiles")
    print("="*70)
    
    profiles = [
        {
            "profile_id": "observer",
            "profile_name": "Observer (Read-Only)",
            "permissions": ["R"],
            "description": "Can only observe and query, no modifications",
            "use_cases": ["Monitoring", "Reporting", "Analytics"]
        },
        {
            "profile_id": "coordinator",
            "profile_name": "Coordinator (R, M)",
            "permissions": ["R", "M"],
            "description": "Can read and reorganize, but not create or modify",
            "use_cases": ["File organization", "Data migration", "Workflow orchestration"]
        },
        {
            "profile_id": "contributor",
            "profile_name": "Contributor (R, M, A)",
            "permissions": ["R", "M", "A"],
            "description": "Can read, move, and add new resources",
            "use_cases": ["Content creation", "Deployment", "Resource provisioning"]
        },
        {
            "profile_id": "developer",
            "profile_name": "Developer (R, M, A, C)",
            "permissions": ["R", "M", "A", "C"],
            "description": "Can read, move, add, and modify resources",
            "use_cases": ["Development", "Configuration", "System updates"]
        },
        {
            "profile_id": "admin",
            "profile_name": "Administrator (R, M, A, C, D)",
            "permissions": ["R", "M", "A", "C", "D"],
            "description": "Full permissions including deletion",
            "use_cases": ["System administration", "Data cleanup", "Emergency response"]
        }
    ]
    
    for profile in profiles:
        print(f"\n{profile['profile_name']}")
        print(f"  ID: {profile['profile_id']}")
        print(f"  Permissions: {', '.join(profile['permissions'])}")
        print(f"  Description: {profile['description']}")
        print(f"  Use Cases: {', '.join(profile['use_cases'])}")
    
    # Save profiles
    profiles_path = Path("rmacd_permission_profiles.json")
    with open(profiles_path, 'w') as f:
        json.dump({"profiles": profiles}, f, indent=2)
    print(f"\n[OK] Profiles saved to: {profiles_path}")


def main():
    """Main execution function with comprehensive error handling."""
    
    try:
        print("\n" + "="*70)
        print("RMACD TOOLS REGISTRY - COMPREHENSIVE DEMONSTRATION")
        print("="*70)
        print("\nAuthor: Kash Kashyap")
        print("Framework: RMACD (Read, Move, Add, Change, Delete)")
        print("Purpose: AI Agent Governance - ITIL for the Agentic Era")
        
        # Step 1: Create catalog
        registry = create_comprehensive_catalog()
        
        # Step 2: Demonstrate features
        demonstrate_registry_features(registry)
        
        # Step 3: Export/Import
        demonstrate_export_import(registry)
        
        # Step 4: Show permission profiles
        create_permission_profiles()
        
        print("\n" + "="*70)
        print("[OK] ALL DEMONSTRATIONS COMPLETED SUCCESSFULLY!")
        print("="*70)
        print("\nGenerated files:")
        print("  - rmacd_tools_catalog.json (Tool registry export)")
        print("  - rmacd_permission_profiles.json (Permission profiles)")
        print("\nNext steps:")
        print("  1. Review the catalog structure")
        print("  2. Add your organization's specific tools")
        print("  3. Integrate with your agent runtime")
        print("  4. Customize permission profiles for your use cases")
        
    except Exception as e:
        print(f"\n[ERROR] CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
