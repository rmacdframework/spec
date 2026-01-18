"""
RMACD Tools Registry System
============================

A comprehensive tool governance system that maps tools to RMACD operational levels
and provides validation, auditing, and risk assessment capabilities.

Author: Kash Kashyap
License: CC BY 4.0
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Set, Tuple, Union, Callable
from enum import Enum, auto
from datetime import datetime
import json
import logging
from pathlib import Path
import hashlib


# Configure logging with comprehensive error tracking
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RMACDLevel(Enum):
    """RMACD operational permission levels in order of increasing risk."""
    READ = ("R", "Read", "Near-Zero", "Observe, query, analyze — no state change")
    MOVE = ("M", "Move", "Low-Medium", "Relocate, transfer — reversible")
    ADD = ("A", "Add", "Medium", "Create, provision — additive impact")
    CHANGE = ("C", "Change", "High", "Modify, update — state mutation")
    DELETE = ("D", "Delete", "Critical", "Remove, destroy — potentially irreversible")
    
    def __init__(self, code: str, name: str, risk: str, description: str):
        self.code = code
        self.operation_name = name
        self.risk_level = risk
        self.description = description
    
    @classmethod
    def from_code(cls, code: str) -> 'RMACDLevel':
        """Get RMACD level from single-letter code with error handling."""
        try:
            code_upper = code.upper().strip()
            for level in cls:
                if level.code == code_upper:
                    return level
            raise ValueError(f"Invalid RMACD code: {code}. Valid codes: R, M, A, C, D")
        except AttributeError as e:
            logger.error(f"Invalid input type for RMACD code: {type(code)}")
            raise TypeError(f"RMACD code must be a string, got {type(code)}") from e
    
    def __lt__(self, other: 'RMACDLevel') -> bool:
        """Compare risk levels for sorting and validation."""
        if not isinstance(other, RMACDLevel):
            raise TypeError(f"Cannot compare RMACDLevel with {type(other)}")
        order = [RMACDLevel.READ, RMACDLevel.MOVE, RMACDLevel.ADD, 
                 RMACDLevel.CHANGE, RMACDLevel.DELETE]
        return order.index(self) < order.index(other)
    
    def __le__(self, other: 'RMACDLevel') -> bool:
        return self < other or self == other


class HITLLevel(Enum):
    """Human-in-the-Loop control levels."""
    AUTONOMOUS = ("auto", "Autonomous", "Execute without human involvement")
    LOGGED = ("logged", "Logged", "Execute and log for audit")
    NOTIFY = ("notify", "Notify", "Execute and notify human")
    APPROVE = ("approve", "Approve", "Require approval before execution")
    ELEVATED = ("elevated", "Elevated Approval", "Require senior approval")
    PROHIBITED = ("prohibited", "Prohibited", "Cannot be executed")
    
    def __init__(self, code: str, name: str, description: str):
        self.code = code
        self.control_name = name
        self.description = description
    
    @classmethod
    def from_code(cls, code: str) -> 'HITLLevel':
        """Get HITL level from code with error handling."""
        try:
            code_lower = code.lower().strip()
            for level in cls:
                if level.code == code_lower:
                    return level
            valid_codes = ", ".join([l.code for l in cls])
            raise ValueError(f"Invalid HITL code: {code}. Valid codes: {valid_codes}")
        except AttributeError as e:
            logger.error(f"Invalid input type for HITL code: {type(code)}")
            raise TypeError(f"HITL code must be a string, got {type(code)}") from e


class DataClassification(Enum):
    """Enterprise data classification tiers."""
    PUBLIC = ("public", "Public", "Publicly available information")
    INTERNAL = ("internal", "Internal", "Internal use only")
    CONFIDENTIAL = ("confidential", "Confidential", "Sensitive business information")
    RESTRICTED = ("restricted", "Restricted", "Highly sensitive, regulated data")
    
    def __init__(self, code: str, name: str, description: str):
        self.code = code
        self.tier_name = name
        self.description = description
    
    @classmethod
    def from_code(cls, code: str) -> 'DataClassification':
        """Get data classification from code with error handling."""
        try:
            code_lower = code.lower().strip()
            for tier in cls:
                if tier.code == code_lower:
                    return tier
            valid_codes = ", ".join([t.code for t in cls])
            raise ValueError(f"Invalid data classification: {code}. Valid codes: {valid_codes}")
        except AttributeError as e:
            logger.error(f"Invalid input type for data classification: {type(code)}")
            raise TypeError(f"Data classification must be a string, got {type(code)}") from e


@dataclass
class ToolDefinition:
    """Comprehensive tool definition with RMACD classification."""
    
    tool_id: str
    tool_name: str
    rmacd_level: RMACDLevel
    description: str = ""
    operations: List[str] = field(default_factory=list)
    data_access: Optional[DataClassification] = None
    required_hitl: Optional[HITLLevel] = None
    risk_score: float = 0.0
    tags: Set[str] = field(default_factory=set)
    metadata: Dict[str, any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Validate and normalize tool definition with comprehensive error checking."""
        try:
            # Validate tool_id
            if not self.tool_id or not isinstance(self.tool_id, str):
                raise ValueError("tool_id must be a non-empty string")
            
            # Normalize tool_id
            self.tool_id = self.tool_id.strip().lower().replace(" ", "_")
            
            # Validate tool_name
            if not self.tool_name or not isinstance(self.tool_name, str):
                raise ValueError("tool_name must be a non-empty string")
            
            # Ensure rmacd_level is enum
            if isinstance(self.rmacd_level, str):
                self.rmacd_level = RMACDLevel.from_code(self.rmacd_level)
            elif not isinstance(self.rmacd_level, RMACDLevel):
                raise TypeError(f"rmacd_level must be RMACDLevel or string, got {type(self.rmacd_level)}")
            
            # Ensure data_access is enum if provided
            if self.data_access is not None:
                if isinstance(self.data_access, str):
                    self.data_access = DataClassification.from_code(self.data_access)
                elif not isinstance(self.data_access, DataClassification):
                    raise TypeError(f"data_access must be DataClassification or string, got {type(self.data_access)}")
            
            # Ensure required_hitl is enum if provided
            if self.required_hitl is not None:
                if isinstance(self.required_hitl, str):
                    self.required_hitl = HITLLevel.from_code(self.required_hitl)
                elif not isinstance(self.required_hitl, HITLLevel):
                    raise TypeError(f"required_hitl must be HITLLevel or string, got {type(self.required_hitl)}")
            
            # Calculate risk score if not provided
            if self.risk_score == 0.0:
                self.risk_score = self._calculate_risk_score()
            
            # Ensure tags is a set
            if not isinstance(self.tags, set):
                self.tags = set(self.tags) if self.tags else set()
            
            # Validate operations list
            if not isinstance(self.operations, list):
                raise TypeError("operations must be a list")
            
            logger.info(f"Tool definition validated: {self.tool_id}")
            
        except Exception as e:
            logger.error(f"Error validating tool definition: {e}")
            raise
    
    def _calculate_risk_score(self) -> float:
        """
        Calculate risk score based on RMACD level, data classification, and HITL.
        
        Risk scoring:
        - RMACD level: 0.0 (R) to 1.0 (D)
        - Data classification: 0.0 (public) to 1.0 (restricted)
        - HITL reduction: 0.0 (prohibited/elevated) to 0.8 (autonomous)
        """
        try:
            # Base risk from RMACD level
            rmacd_risk = {
                RMACDLevel.READ: 0.0,
                RMACDLevel.MOVE: 0.25,
                RMACDLevel.ADD: 0.50,
                RMACDLevel.CHANGE: 0.75,
                RMACDLevel.DELETE: 1.0
            }.get(self.rmacd_level, 0.5)
            
            # Data sensitivity multiplier
            data_risk = 0.0
            if self.data_access:
                data_risk = {
                    DataClassification.PUBLIC: 0.0,
                    DataClassification.INTERNAL: 0.33,
                    DataClassification.CONFIDENTIAL: 0.67,
                    DataClassification.RESTRICTED: 1.0
                }.get(self.data_access, 0.5)
            
            # HITL control modifier (reduces risk)
            hitl_modifier = 1.0
            if self.required_hitl:
                hitl_modifier = {
                    HITLLevel.PROHIBITED: 0.0,
                    HITLLevel.ELEVATED: 0.2,
                    HITLLevel.APPROVE: 0.4,
                    HITLLevel.NOTIFY: 0.6,
                    HITLLevel.LOGGED: 0.8,
                    HITLLevel.AUTONOMOUS: 1.0
                }.get(self.required_hitl, 0.5)
            
            # Combined risk score (0.0 - 10.0 scale)
            base_risk = (rmacd_risk * 0.6 + data_risk * 0.4) * hitl_modifier
            return round(base_risk * 10, 2)
            
        except Exception as e:
            logger.error(f"Error calculating risk score: {e}")
            return 5.0  # Default medium risk on error
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization with error handling."""
        try:
            return {
                "tool_id": self.tool_id,
                "tool_name": self.tool_name,
                "rmacd_level": self.rmacd_level.code,
                "rmacd_description": self.rmacd_level.description,
                "description": self.description,
                "operations": self.operations,
                "data_access": self.data_access.code if self.data_access else None,
                "required_hitl": self.required_hitl.code if self.required_hitl else None,
                "risk_score": self.risk_score,
                "tags": list(self.tags),
                "metadata": self.metadata,
                "created_at": self.created_at.isoformat()
            }
        except Exception as e:
            logger.error(f"Error converting tool to dict: {e}")
            raise
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ToolDefinition':
        """Create tool from dictionary with comprehensive error handling."""
        try:
            # Required fields
            required_fields = ["tool_id", "tool_name", "rmacd_level"]
            missing_fields = [f for f in required_fields if f not in data]
            if missing_fields:
                raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
            
            # Convert datetime if string
            created_at = data.get("created_at")
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at)
            elif created_at is None:
                created_at = datetime.now()
            
            return cls(
                tool_id=data["tool_id"],
                tool_name=data["tool_name"],
                rmacd_level=data["rmacd_level"],
                description=data.get("description", ""),
                operations=data.get("operations", []),
                data_access=data.get("data_access"),
                required_hitl=data.get("required_hitl"),
                risk_score=data.get("risk_score", 0.0),
                tags=set(data.get("tags", [])),
                metadata=data.get("metadata", {}),
                created_at=created_at
            )
        except Exception as e:
            logger.error(f"Error creating tool from dict: {e}")
            raise


class ToolsRegistry:
    """
    Central registry for managing tools and their RMACD classifications.
    
    Provides:
    - Tool registration and lookup
    - Permission validation
    - Risk assessment
    - Audit logging
    - JSON import/export
    """
    
    def __init__(self, registry_id: str = "default"):
        """Initialize the tools registry with error handling."""
        try:
            self.registry_id = registry_id
            self._tools: Dict[str, ToolDefinition] = {}
            self._index_by_level: Dict[RMACDLevel, Set[str]] = {
                level: set() for level in RMACDLevel
            }
            self._audit_log: List[Dict] = []
            self._version = "1.0.0"
            logger.info(f"Tools registry '{registry_id}' initialized")
        except Exception as e:
            logger.error(f"Error initializing registry: {e}")
            raise
    
    def register_tool(self, tool: Union[ToolDefinition, Dict]) -> bool:
        """
        Register a new tool in the registry with comprehensive validation.
        
        Args:
            tool: ToolDefinition object or dictionary
            
        Returns:
            bool: True if successful, False otherwise
            
        Raises:
            ValueError: If tool validation fails
            TypeError: If tool is wrong type
        """
        try:
            # Convert dict to ToolDefinition if needed
            if isinstance(tool, dict):
                tool = ToolDefinition.from_dict(tool)
            elif not isinstance(tool, ToolDefinition):
                raise TypeError(f"Tool must be ToolDefinition or dict, got {type(tool)}")
            
            # Check for duplicates
            if tool.tool_id in self._tools:
                logger.warning(f"Tool '{tool.tool_id}' already registered, updating...")
            
            # Register tool
            self._tools[tool.tool_id] = tool
            self._index_by_level[tool.rmacd_level].add(tool.tool_id)
            
            # Log audit event
            self._log_audit("register", tool.tool_id, {
                "rmacd_level": tool.rmacd_level.code,
                "risk_score": tool.risk_score
            })
            
            logger.info(f"Tool '{tool.tool_id}' registered successfully with RMACD level {tool.rmacd_level.code}")
            return True
            
        except Exception as e:
            logger.error(f"Error registering tool: {e}")
            raise
    
    def get_tool(self, tool_id: str) -> Optional[ToolDefinition]:
        """
        Retrieve a tool by ID with error handling.
        
        Args:
            tool_id: Tool identifier
            
        Returns:
            ToolDefinition if found, None otherwise
        """
        try:
            if not isinstance(tool_id, str):
                raise TypeError(f"tool_id must be string, got {type(tool_id)}")
            
            normalized_id = tool_id.strip().lower().replace(" ", "_")
            tool = self._tools.get(normalized_id)
            
            if tool is None:
                logger.warning(f"Tool '{tool_id}' not found in registry")
            
            return tool
            
        except Exception as e:
            logger.error(f"Error retrieving tool '{tool_id}': {e}")
            return None
    
    def get_tools_by_level(self, rmacd_level: Union[RMACDLevel, str]) -> List[ToolDefinition]:
        """
        Get all tools at a specific RMACD level with error handling.
        
        Args:
            rmacd_level: RMACD level enum or code string
            
        Returns:
            List of tools at that level
        """
        try:
            # Convert string to enum if needed
            if isinstance(rmacd_level, str):
                rmacd_level = RMACDLevel.from_code(rmacd_level)
            elif not isinstance(rmacd_level, RMACDLevel):
                raise TypeError(f"rmacd_level must be RMACDLevel or string, got {type(rmacd_level)}")
            
            tool_ids = self._index_by_level.get(rmacd_level, set())
            tools = [self._tools[tid] for tid in tool_ids if tid in self._tools]
            
            logger.info(f"Found {len(tools)} tools at level {rmacd_level.code}")
            return tools
            
        except Exception as e:
            logger.error(f"Error getting tools by level: {e}")
            return []
    
    def validate_tool_access(
        self,
        tool_id: str,
        allowed_levels: List[Union[RMACDLevel, str]],
        data_tier: Optional[Union[DataClassification, str]] = None
    ) -> Tuple[bool, str]:
        """
        Validate if a tool can be accessed based on permission profile.
        
        Args:
            tool_id: Tool to validate
            allowed_levels: List of allowed RMACD levels
            data_tier: Optional data classification for 3D model
            
        Returns:
            Tuple of (is_allowed: bool, reason: str)
        """
        try:
            # Get tool
            tool = self.get_tool(tool_id)
            if tool is None:
                return False, f"Tool '{tool_id}' not found in registry"
            
            # Convert allowed levels to enums
            allowed_enums = []
            for level in allowed_levels:
                if isinstance(level, str):
                    allowed_enums.append(RMACDLevel.from_code(level))
                elif isinstance(level, RMACDLevel):
                    allowed_enums.append(level)
                else:
                    logger.warning(f"Skipping invalid level type: {type(level)}")
            
            # Check RMACD level permission
            if tool.rmacd_level not in allowed_enums:
                reason = f"Tool requires {tool.rmacd_level.code} permission, but only {[l.code for l in allowed_enums]} allowed"
                logger.warning(f"Access denied for '{tool_id}': {reason}")
                return False, reason
            
            # Check data classification if 3D model
            if data_tier is not None:
                if isinstance(data_tier, str):
                    data_tier = DataClassification.from_code(data_tier)
                
                if tool.data_access is not None:
                    # Simplified check: tool's data requirement must not exceed allowed tier
                    tier_order = list(DataClassification)
                    if tier_order.index(tool.data_access) > tier_order.index(data_tier):
                        reason = f"Tool requires {tool.data_access.code} data access, but only {data_tier.code} allowed"
                        logger.warning(f"Access denied for '{tool_id}': {reason}")
                        return False, reason
            
            # Check HITL requirements
            if tool.required_hitl == HITLLevel.PROHIBITED:
                reason = "Tool is explicitly prohibited"
                logger.warning(f"Access denied for '{tool_id}': {reason}")
                return False, reason
            
            # Log successful validation
            self._log_audit("validate_access", tool_id, {
                "allowed": True,
                "allowed_levels": [l.code for l in allowed_enums]
            })
            
            return True, f"Access granted for {tool.rmacd_level.code} operation"
            
        except Exception as e:
            logger.error(f"Error validating tool access: {e}")
            return False, f"Validation error: {str(e)}"
    
    def calculate_workflow_risk(self, tool_ids: List[str]) -> Dict:
        """
        Calculate aggregate risk for a workflow using multiple tools.
        
        Args:
            tool_ids: List of tool IDs in the workflow
            
        Returns:
            Dict with risk analysis
        """
        try:
            if not isinstance(tool_ids, list):
                raise TypeError(f"tool_ids must be list, got {type(tool_ids)}")
            
            tools = []
            missing = []
            
            for tid in tool_ids:
                tool = self.get_tool(tid)
                if tool:
                    tools.append(tool)
                else:
                    missing.append(tid)
            
            if missing:
                logger.warning(f"Missing tools in workflow: {missing}")
            
            if not tools:
                return {
                    "total_risk": 0.0,
                    "max_risk": 0.0,
                    "avg_risk": 0.0,
                    "tool_count": 0,
                    "highest_rmacd": None,
                    "missing_tools": missing,
                    "error": "No valid tools found"
                }
            
            # Calculate metrics
            risk_scores = [t.risk_score for t in tools]
            rmacd_levels = [t.rmacd_level for t in tools]
            
            total_risk = sum(risk_scores)
            max_risk = max(risk_scores)
            avg_risk = total_risk / len(tools)
            highest_rmacd = max(rmacd_levels)
            
            # Get tool with highest risk
            highest_risk_tool = max(tools, key=lambda t: t.risk_score)
            
            result = {
                "total_risk": round(total_risk, 2),
                "max_risk": round(max_risk, 2),
                "avg_risk": round(avg_risk, 2),
                "tool_count": len(tools),
                "highest_rmacd": highest_rmacd.code,
                "highest_risk_tool": highest_risk_tool.tool_id,
                "missing_tools": missing,
                "risk_distribution": {
                    level.code: len([t for t in tools if t.rmacd_level == level])
                    for level in RMACDLevel
                }
            }
            
            logger.info(f"Workflow risk calculated: {result['total_risk']}")
            return result
            
        except Exception as e:
            logger.error(f"Error calculating workflow risk: {e}")
            return {
                "error": str(e),
                "total_risk": 0.0,
                "max_risk": 0.0,
                "avg_risk": 0.0,
                "tool_count": 0
            }
    
    def export_to_json(self, filepath: Union[str, Path]) -> bool:
        """
        Export registry to JSON file with error handling.
        
        Args:
            filepath: Path to output file
            
        Returns:
            bool: True if successful
        """
        try:
            filepath = Path(filepath)
            
            # Create directory if needed
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            export_data = {
                "registry_id": self.registry_id,
                "version": self._version,
                "exported_at": datetime.now().isoformat(),
                "tool_count": len(self._tools),
                "tools": [tool.to_dict() for tool in self._tools.values()]
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Registry exported to {filepath}")
            return True
            
        except IOError as e:
            logger.error(f"IO error exporting registry: {e}")
            return False
        except Exception as e:
            logger.error(f"Error exporting registry: {e}")
            return False
    
    def import_from_json(self, filepath: Union[str, Path]) -> bool:
        """
        Import tools from JSON file with comprehensive error handling.
        
        Args:
            filepath: Path to input file
            
        Returns:
            bool: True if successful
        """
        try:
            filepath = Path(filepath)
            
            if not filepath.exists():
                raise FileNotFoundError(f"File not found: {filepath}")
            
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Validate structure
            if "tools" not in data:
                raise ValueError("Invalid registry file: missing 'tools' key")
            
            # Import tools
            success_count = 0
            error_count = 0
            
            for tool_data in data["tools"]:
                try:
                    self.register_tool(tool_data)
                    success_count += 1
                except Exception as e:
                    logger.error(f"Error importing tool {tool_data.get('tool_id', 'unknown')}: {e}")
                    error_count += 1
            
            logger.info(f"Import complete: {success_count} tools imported, {error_count} errors")
            return error_count == 0
            
        except FileNotFoundError as e:
            logger.error(f"File not found: {e}")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            return False
        except Exception as e:
            logger.error(f"Error importing registry: {e}")
            return False
    
    def _log_audit(self, action: str, tool_id: str, details: Dict):
        """Internal method to log audit events."""
        try:
            audit_entry = {
                "timestamp": datetime.now().isoformat(),
                "action": action,
                "tool_id": tool_id,
                "details": details
            }
            self._audit_log.append(audit_entry)
        except Exception as e:
            logger.error(f"Error logging audit event: {e}")
    
    def get_audit_log(self, last_n: Optional[int] = None) -> List[Dict]:
        """
        Retrieve audit log entries with error handling.
        
        Args:
            last_n: Optional limit to last N entries
            
        Returns:
            List of audit entries
        """
        try:
            if last_n is not None:
                if not isinstance(last_n, int) or last_n < 1:
                    raise ValueError("last_n must be positive integer")
                return self._audit_log[-last_n:]
            return self._audit_log.copy()
        except Exception as e:
            logger.error(f"Error retrieving audit log: {e}")
            return []
    
    def get_stats(self) -> Dict:
        """Get registry statistics with error handling."""
        try:
            return {
                "registry_id": self.registry_id,
                "total_tools": len(self._tools),
                "by_level": {
                    level.code: len(tools)
                    for level, tools in self._index_by_level.items()
                },
                "avg_risk_score": round(
                    sum(t.risk_score for t in self._tools.values()) / max(len(self._tools), 1),
                    2
                ),
                "audit_entries": len(self._audit_log)
            }
        except Exception as e:
            logger.error(f"Error calculating stats: {e}")
            return {"error": str(e)}
    
    def __len__(self) -> int:
        """Return number of registered tools."""
        return len(self._tools)
    
    def __contains__(self, tool_id: str) -> bool:
        """Check if tool is registered."""
        try:
            normalized_id = tool_id.strip().lower().replace(" ", "_")
            return normalized_id in self._tools
        except:
            return False
    
    def __repr__(self) -> str:
        """String representation of registry."""
        return f"ToolsRegistry(id='{self.registry_id}', tools={len(self._tools)})"


# Convenience functions for quick registry operations

def create_registry(registry_id: str = "default") -> ToolsRegistry:
    """Create a new tools registry with error handling."""
    try:
        return ToolsRegistry(registry_id)
    except Exception as e:
        logger.error(f"Error creating registry: {e}")
        raise


def quick_register(
    registry: ToolsRegistry,
    tool_id: str,
    tool_name: str,
    rmacd_level: str,
    **kwargs
) -> bool:
    """Quick tool registration helper with error handling."""
    try:
        tool = ToolDefinition(
            tool_id=tool_id,
            tool_name=tool_name,
            rmacd_level=rmacd_level,
            **kwargs
        )
        return registry.register_tool(tool)
    except Exception as e:
        logger.error(f"Error in quick_register: {e}")
        return False
