"""
Comprehensive Integration Tests for GDG Agentic Workspace.
Tests agent initialization, path resolution, tool resilience, and A2A cards.
"""

import os
import sys
import unittest
from pathlib import Path

# Set up paths
WORKSPACE_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(WORKSPACE_ROOT))


class TestAgentImportsAndDeclarations(unittest.TestCase):
    """Verifies all sub-agents and root_agent load without import/configuration errors."""

    def test_root_agent_import(self):
        from agents.root_agent.agent import root_agent
        self.assertIsNotNone(root_agent)
        self.assertEqual(root_agent.name, "root_agent")
        self.assertEqual(len(root_agent.sub_agents), 7)

    def test_video_editor_agent_import(self):
        from agents.video_editor.agent import video_editor_agent
        self.assertIsNotNone(video_editor_agent)
        self.assertEqual(video_editor_agent.name, "video_editor")
        self.assertTrue(len(video_editor_agent.tools) >= 5)

    def test_receipt_scanner_agent_import(self):
        from agents.receipt_scanner.agent import receipt_agent
        self.assertIsNotNone(receipt_agent)
        self.assertEqual(receipt_agent.name, "receipt_scanner")
        self.assertTrue(len(receipt_agent.tools) >= 3)

    def test_registration_manager_agent_import(self):
        from agents.registration_manager.agent import root_agent as reg_agent
        self.assertIsNotNone(reg_agent)
        self.assertEqual(reg_agent.name, "registration_manager")

    def test_event_planner_agent_import(self):
        from agents.event_planner.agent import planner_agent
        self.assertIsNotNone(planner_agent)
        self.assertEqual(planner_agent.name, "event_planner")

    def test_agenda_generator_agent_import(self):
        from agents.agenda_generator.agent import agenda_agent
        self.assertIsNotNone(agenda_agent)
        self.assertEqual(agenda_agent.name, "agenda_generator")

    def test_office_secretary_agent_import(self):
        from agents.office_secretary.agent import office_agent
        self.assertIsNotNone(office_agent)
        self.assertEqual(office_agent.name, "office_secretary")

    def test_linkedin_post_generator_agent_import(self):
        from agents.linkedin_post_generator.agent import root_agent as linkedin_agent
        self.assertIsNotNone(linkedin_agent)
        self.assertEqual(linkedin_agent.name, "linkedin_post_generator")


class TestPathResolutions(unittest.TestCase):
    """Verifies that resolve_path functions handle varied relative and nested path formats correctly."""

    def test_registration_manager_resolve_path(self):
        from agents.registration_manager.tools import resolve_path, BASE_DIR
        # Test 1: Simple relative path inside agent
        res1 = resolve_path("results/staged_manual_registrations.csv")
        self.assertTrue(res1.endswith("staged_manual_registrations.csv"))
        
        # Test 2: Prefix with agents/registration_manager/
        res2 = resolve_path("agents/registration_manager/results/staged_manual_registrations.csv")
        self.assertTrue(res2.endswith("staged_manual_registrations.csv"))

        # Test 3: Prefix with registration_manager/
        res3 = resolve_path("registration_manager/results/staged_manual_registrations.csv")
        self.assertTrue(res3.endswith("staged_manual_registrations.csv"))

    def test_video_editor_resolve_path(self):
        from agents.video_editor.tools.composer_tools import resolve_path as comp_resolve
        from agents.video_editor.tools.media_tools import resolve_path as media_resolve

        p1 = comp_resolve("assets/portrait_outpainted.png")
        self.assertTrue(p1.endswith("portrait_outpainted.png"))

        p2 = media_resolve("video_editor/assets/portrait_outpainted.png")
        self.assertTrue(p2.endswith("portrait_outpainted.png"))

        p3 = comp_resolve("agents/video_editor/assets/portrait_outpainted.png")
        self.assertTrue(p3.endswith("portrait_outpainted.png"))


class TestToolExecutionAndResilience(unittest.TestCase):
    """Verifies tool functions execute and return clean error strings without crashing."""

    def test_process_registrations_missing_file_handling(self):
        from agents.registration_manager.tools import process_registrations
        # Must return an error string and NOT raise unhandled exception
        result = process_registrations("non_existent_file_12345.csv", capacity=50)
        self.assertIsInstance(result, str)
        self.assertTrue(result.startswith("Error:"))

    def test_stage_manual_text_registrations(self):
        from agents.registration_manager.tools import stage_manual_text_registrations, process_registrations
        sample_text = "Jan Kowalski\nAnna Nowak\nPiotr Wiśniewski"
        staged_path = stage_manual_text_registrations(sample_text)
        self.assertTrue(isinstance(staged_path, str) and len(staged_path) > 0)
        
        # Process the newly staged file
        result = process_registrations(staged_path, capacity=2)
        self.assertIsInstance(result, str)
        self.assertIn("Confirmed Registrants", result)
        self.assertIn("Waitlist", result)

    def test_get_usd_pln_rate(self):
        from agents.receipt_scanner.tools import get_usd_pln_rate
        res = get_usd_pln_rate()
        self.assertIsInstance(res, dict)
        self.assertTrue(res.get("success", False))
        self.assertGreater(res.get("rate", 0), 0)

    def test_get_public_holidays(self):
        from agents.event_planner.tools import get_public_holidays
        res = get_public_holidays(year=2026, country_code="PL")
        self.assertIsInstance(res, dict)
        self.assertTrue(res.get("success", False))
        self.assertGreater(len(res.get("holidays", [])), 0)


class TestA2AMicroservices(unittest.TestCase):
    """Verifies A2A applications build valid schemas and AgentCards."""

    def test_video_editor_a2a_app(self):
        from agents.video_editor.a2a_server import a2a_app
        self.assertIsNotNone(a2a_app)

    def test_receipt_scanner_a2a_app(self):
        from agents.receipt_scanner.a2a_server import a2a_app
        self.assertIsNotNone(a2a_app)


if __name__ == "__main__":
    unittest.main(verbosity=2)
