"""
RMACD Tools Registry - Comprehensive Test Suite
================================================

Tests all functionality with comprehensive error handling validation.

Author: Kash Kashyap
"""

import unittest
from pathlib import Path
import json
import tempfile
from rmacd_tools_registry import (
    ToolsRegistry,
    ToolDefinition,
    RMACDLevel,
    HITLLevel,
    DataClassification,
    create_registry,
    quick_register
)


class TestRMACDLevel(unittest.TestCase):
    """Test RMACD level enum functionality."""
    
    def test_from_code_valid(self):
        """Test valid RMACD code conversion."""
        self.assertEqual(RMACDLevel.from_code("R"), RMACDLevel.READ)
        self.assertEqual(RMACDLevel.from_code("M"), RMACDLevel.MOVE)
        self.assertEqual(RMACDLevel.from_code("A"), RMACDLevel.ADD)
        self.assertEqual(RMACDLevel.from_code("C"), RMACDLevel.CHANGE)
        self.assertEqual(RMACDLevel.from_code("D"), RMACDLevel.DELETE)
    
    def test_from_code_case_insensitive(self):
        """Test case-insensitive code conversion."""
        self.assertEqual(RMACDLevel.from_code("r"), RMACDLevel.READ)
        self.assertEqual(RMACDLevel.from_code("m"), RMACDLevel.MOVE)
    
    def test_from_code_invalid(self):
        """Test invalid code raises ValueError."""
        with self.assertRaises(ValueError):
            RMACDLevel.from_code("X")
    
    def test_from_code_invalid_type(self):
        """Test non-string input raises TypeError."""
        with self.assertRaises(TypeError):
            RMACDLevel.from_code(123)
    
    def test_level_comparison(self):
        """Test RMACD level comparison."""
        self.assertTrue(RMACDLevel.READ < RMACDLevel.DELETE)
        self.assertTrue(RMACDLevel.MOVE <= RMACDLevel.ADD)
        self.assertFalse(RMACDLevel.DELETE < RMACDLevel.READ)


class TestToolDefinition(unittest.TestCase):
    """Test ToolDefinition class."""
    
    def test_valid_tool_creation(self):
        """Test creating a valid tool definition."""
        tool = ToolDefinition(
            tool_id="test_tool",
            tool_name="Test Tool",
            rmacd_level=RMACDLevel.READ,
            description="A test tool"
        )
        self.assertEqual(tool.tool_id, "test_tool")
        self.assertEqual(tool.rmacd_level, RMACDLevel.READ)
    
    def test_tool_id_normalization(self):
        """Test tool ID gets normalized."""
        tool = ToolDefinition(
            tool_id="Test Tool",
            tool_name="Test Tool",
            rmacd_level="R"
        )
        self.assertEqual(tool.tool_id, "test_tool")
    
    def test_rmacd_level_string_conversion(self):
        """Test RMACD level string is converted to enum."""
        tool = ToolDefinition(
            tool_id="test",
            tool_name="Test",
            rmacd_level="R"
        )
        self.assertEqual(tool.rmacd_level, RMACDLevel.READ)
    
    def test_data_access_string_conversion(self):
        """Test data access string is converted to enum."""
        tool = ToolDefinition(
            tool_id="test",
            tool_name="Test",
            rmacd_level="R",
            data_access="internal"
        )
        self.assertEqual(tool.data_access, DataClassification.INTERNAL)
    
    def test_hitl_string_conversion(self):
        """Test HITL level string is converted to enum."""
        tool = ToolDefinition(
            tool_id="test",
            tool_name="Test",
            rmacd_level="R",
            required_hitl="logged"
        )
        self.assertEqual(tool.required_hitl, HITLLevel.LOGGED)
    
    def test_invalid_tool_id(self):
        """Test empty tool_id raises ValueError."""
        with self.assertRaises(ValueError):
            ToolDefinition(
                tool_id="",
                tool_name="Test",
                rmacd_level="R"
            )
    
    def test_invalid_tool_name(self):
        """Test empty tool_name raises ValueError."""
        with self.assertRaises(ValueError):
            ToolDefinition(
                tool_id="test",
                tool_name="",
                rmacd_level="R"
            )
    
    def test_risk_score_calculation(self):
        """Test automatic risk score calculation."""
        tool = ToolDefinition(
            tool_id="high_risk",
            tool_name="High Risk Tool",
            rmacd_level=RMACDLevel.DELETE,
            data_access=DataClassification.RESTRICTED,
            required_hitl=HITLLevel.AUTONOMOUS
        )
        self.assertGreater(tool.risk_score, 5.0)
    
    def test_to_dict_conversion(self):
        """Test tool conversion to dictionary."""
        tool = ToolDefinition(
            tool_id="test",
            tool_name="Test Tool",
            rmacd_level="R",
            operations=["read", "query"]
        )
        tool_dict = tool.to_dict()
        self.assertEqual(tool_dict["tool_id"], "test")
        self.assertEqual(tool_dict["rmacd_level"], "R")
        self.assertEqual(tool_dict["operations"], ["read", "query"])
    
    def test_from_dict_creation(self):
        """Test tool creation from dictionary."""
        data = {
            "tool_id": "test",
            "tool_name": "Test Tool",
            "rmacd_level": "R",
            "description": "Test description"
        }
        tool = ToolDefinition.from_dict(data)
        self.assertEqual(tool.tool_id, "test")
        self.assertEqual(tool.rmacd_level, RMACDLevel.READ)
    
    def test_from_dict_missing_required(self):
        """Test from_dict raises error on missing required fields."""
        data = {
            "tool_name": "Test Tool"
            # Missing tool_id and rmacd_level
        }
        with self.assertRaises(ValueError):
            ToolDefinition.from_dict(data)


class TestToolsRegistry(unittest.TestCase):
    """Test ToolsRegistry class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.registry = create_registry("test-registry")
    
    def test_registry_creation(self):
        """Test registry initialization."""
        self.assertEqual(self.registry.registry_id, "test-registry")
        self.assertEqual(len(self.registry), 0)
    
    def test_tool_registration(self):
        """Test registering a tool."""
        tool = ToolDefinition(
            tool_id="test_tool",
            tool_name="Test Tool",
            rmacd_level="R"
        )
        success = self.registry.register_tool(tool)
        self.assertTrue(success)
        self.assertEqual(len(self.registry), 1)
    
    def test_tool_registration_from_dict(self):
        """Test registering tool from dictionary."""
        tool_dict = {
            "tool_id": "test_dict",
            "tool_name": "Test Dict Tool",
            "rmacd_level": "M"
        }
        success = self.registry.register_tool(tool_dict)
        self.assertTrue(success)
        self.assertIn("test_dict", self.registry)
    
    def test_quick_register_helper(self):
        """Test quick_register convenience function."""
        success = quick_register(
            self.registry,
            "quick_tool",
            "Quick Tool",
            "A",
            description="Quick registration test"
        )
        self.assertTrue(success)
        self.assertIn("quick_tool", self.registry)
    
    def test_get_tool(self):
        """Test retrieving a tool by ID."""
        tool = ToolDefinition(
            tool_id="retrieve_test",
            tool_name="Retrieve Test",
            rmacd_level="R"
        )
        self.registry.register_tool(tool)
        
        retrieved = self.registry.get_tool("retrieve_test")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.tool_name, "Retrieve Test")
    
    def test_get_nonexistent_tool(self):
        """Test retrieving non-existent tool returns None."""
        tool = self.registry.get_tool("nonexistent")
        self.assertIsNone(tool)
    
    def test_get_tools_by_level(self):
        """Test getting tools by RMACD level."""
        # Register tools at different levels
        for i, level in enumerate(["R", "R", "M", "A"]):
            quick_register(
                self.registry,
                f"tool_{i}",
                f"Tool {i}",
                level
            )
        
        read_tools = self.registry.get_tools_by_level("R")
        self.assertEqual(len(read_tools), 2)
        
        move_tools = self.registry.get_tools_by_level(RMACDLevel.MOVE)
        self.assertEqual(len(move_tools), 1)
    
    def test_validate_tool_access_allowed(self):
        """Test successful tool access validation."""
        quick_register(
            self.registry,
            "read_tool",
            "Read Tool",
            "R"
        )
        
        is_allowed, reason = self.registry.validate_tool_access(
            "read_tool",
            ["R", "M"]
        )
        self.assertTrue(is_allowed)
        self.assertIn("Access granted", reason)
    
    def test_validate_tool_access_denied(self):
        """Test denied tool access validation."""
        quick_register(
            self.registry,
            "write_tool",
            "Write Tool",
            "C"
        )
        
        is_allowed, reason = self.registry.validate_tool_access(
            "write_tool",
            ["R"]
        )
        self.assertFalse(is_allowed)
        self.assertIn("requires C permission", reason)
    
    def test_validate_tool_access_nonexistent(self):
        """Test validation of non-existent tool."""
        is_allowed, reason = self.registry.validate_tool_access(
            "nonexistent",
            ["R"]
        )
        self.assertFalse(is_allowed)
        self.assertIn("not found", reason)
    
    def test_validate_tool_access_with_data_tier(self):
        """Test 3D model validation with data classification."""
        tool = ToolDefinition(
            tool_id="data_tool",
            tool_name="Data Tool",
            rmacd_level="R",
            data_access="confidential"
        )
        self.registry.register_tool(tool)
        
        # Should be allowed - internal <= confidential
        is_allowed, _ = self.registry.validate_tool_access(
            "data_tool",
            ["R"],
            "confidential"
        )
        self.assertTrue(is_allowed)
        
        # Should be denied - restricted < confidential
        is_allowed, reason = self.registry.validate_tool_access(
            "data_tool",
            ["R"],
            "internal"
        )
        self.assertFalse(is_allowed)
    
    def test_validate_prohibited_tool(self):
        """Test validation rejects prohibited tools."""
        tool = ToolDefinition(
            tool_id="prohibited_tool",
            tool_name="Prohibited Tool",
            rmacd_level="D",
            required_hitl="prohibited"
        )
        self.registry.register_tool(tool)
        
        is_allowed, reason = self.registry.validate_tool_access(
            "prohibited_tool",
            ["D"]
        )
        self.assertFalse(is_allowed)
        self.assertIn("prohibited", reason.lower())
    
    def test_calculate_workflow_risk(self):
        """Test workflow risk calculation."""
        # Register tools
        for i, level in enumerate(["R", "M", "C"]):
            quick_register(
                self.registry,
                f"workflow_tool_{i}",
                f"Workflow Tool {i}",
                level
            )
        
        risk = self.registry.calculate_workflow_risk(
            ["workflow_tool_0", "workflow_tool_1", "workflow_tool_2"]
        )
        
        self.assertEqual(risk["tool_count"], 3)
        self.assertEqual(risk["highest_rmacd"], "C")
        self.assertGreater(risk["total_risk"], 0)
    
    def test_calculate_workflow_risk_with_missing(self):
        """Test workflow risk with missing tools."""
        quick_register(self.registry, "tool1", "Tool 1", "R")
        
        risk = self.registry.calculate_workflow_risk(
            ["tool1", "missing_tool"]
        )
        
        self.assertEqual(risk["tool_count"], 1)
        self.assertIn("missing_tool", risk["missing_tools"])
    
    def test_export_import_json(self):
        """Test JSON export and import."""
        # Register some tools
        for i in range(3):
            quick_register(
                self.registry,
                f"export_tool_{i}",
                f"Export Tool {i}",
                "R"
            )
        
        # Export to temp file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_path = f.name
        
        try:
            # Export
            success = self.registry.export_to_json(temp_path)
            self.assertTrue(success)
            self.assertTrue(Path(temp_path).exists())
            
            # Verify JSON structure
            with open(temp_path, 'r') as f:
                data = json.load(f)
            self.assertEqual(data["tool_count"], 3)
            self.assertIn("tools", data)
            
            # Import into new registry
            new_registry = create_registry("import-test")
            import_success = new_registry.import_from_json(temp_path)
            self.assertTrue(import_success)
            self.assertEqual(len(new_registry), 3)
            
        finally:
            # Cleanup
            Path(temp_path).unlink(missing_ok=True)
    
    def test_import_invalid_json(self):
        """Test importing invalid JSON fails gracefully."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            f.write("invalid json{")
            temp_path = f.name
        
        try:
            success = self.registry.import_from_json(temp_path)
            self.assertFalse(success)
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_import_missing_file(self):
        """Test importing non-existent file fails gracefully."""
        success = self.registry.import_from_json("/nonexistent/path.json")
        self.assertFalse(success)
    
    def test_get_audit_log(self):
        """Test audit log retrieval."""
        quick_register(self.registry, "audit_tool", "Audit Tool", "R")
        
        log = self.registry.get_audit_log()
        self.assertGreater(len(log), 0)
        self.assertEqual(log[-1]["action"], "register")
    
    def test_get_audit_log_limited(self):
        """Test limited audit log retrieval."""
        for i in range(5):
            quick_register(self.registry, f"tool_{i}", f"Tool {i}", "R")
        
        log = self.registry.get_audit_log(last_n=2)
        self.assertEqual(len(log), 2)
    
    def test_get_stats(self):
        """Test registry statistics."""
        quick_register(self.registry, "r_tool", "R Tool", "R")
        quick_register(self.registry, "m_tool", "M Tool", "M")
        
        stats = self.registry.get_stats()
        self.assertEqual(stats["total_tools"], 2)
        self.assertEqual(stats["by_level"]["R"], 1)
        self.assertEqual(stats["by_level"]["M"], 1)
        self.assertIn("avg_risk_score", stats)
    
    def test_contains_operator(self):
        """Test 'in' operator for registry."""
        quick_register(self.registry, "test_tool", "Test Tool", "R")
        
        self.assertTrue("test_tool" in self.registry)
        self.assertFalse("nonexistent" in self.registry)
    
    def test_len_operator(self):
        """Test len() operator for registry."""
        self.assertEqual(len(self.registry), 0)
        
        quick_register(self.registry, "tool1", "Tool 1", "R")
        self.assertEqual(len(self.registry), 1)
        
        quick_register(self.registry, "tool2", "Tool 2", "M")
        self.assertEqual(len(self.registry), 2)


class TestErrorHandling(unittest.TestCase):
    """Test comprehensive error handling."""
    
    def test_invalid_rmacd_code_error(self):
        """Test invalid RMACD code raises proper error."""
        with self.assertRaises(ValueError) as context:
            RMACDLevel.from_code("X")
        self.assertIn("Invalid RMACD code", str(context.exception))
    
    def test_invalid_hitl_code_error(self):
        """Test invalid HITL code raises proper error."""
        with self.assertRaises(ValueError) as context:
            HITLLevel.from_code("invalid")
        self.assertIn("Invalid HITL code", str(context.exception))
    
    def test_invalid_data_classification_error(self):
        """Test invalid data classification raises proper error."""
        with self.assertRaises(ValueError) as context:
            DataClassification.from_code("invalid")
        self.assertIn("Invalid data classification", str(context.exception))
    
    def test_type_error_on_invalid_input(self):
        """Test TypeError on invalid input types."""
        with self.assertRaises(TypeError):
            RMACDLevel.from_code(123)
        
        with self.assertRaises(TypeError):
            HITLLevel.from_code(['list'])
    
    def test_registry_handles_invalid_tool_gracefully(self):
        """Test registry handles invalid tools gracefully."""
        registry = create_registry("error-test")
        
        # Try to register invalid tool
        with self.assertRaises(Exception):
            registry.register_tool({"invalid": "data"})
        
        # Registry should still be functional
        self.assertEqual(len(registry), 0)


def run_tests():
    """Run all tests and display results."""
    print("\n" + "="*70)
    print("RMACD TOOLS REGISTRY - COMPREHENSIVE TEST SUITE")
    print("="*70)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestRMACDLevel))
    suite.addTests(loader.loadTestsFromTestCase(TestToolDefinition))
    suite.addTests(loader.loadTestsFromTestCase(TestToolsRegistry))
    suite.addTests(loader.loadTestsFromTestCase(TestErrorHandling))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.wasSuccessful():
        print("\n✅ ALL TESTS PASSED!")
    else:
        print("\n❌ SOME TESTS FAILED")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)
