import os
import unittest
from unittest.mock import patch

from agents.video_editor.agent import typo_instruction


class TestVideoEditorAgentInstruction(unittest.TestCase):
    def test_typo_instruction_requires_confirmation_when_enabled(self):
        with patch.dict(os.environ, {"VIDEO_EDITOR_PROPOSE_TYPO_CORRECTIONS": "true"}):
            instruction = typo_instruction()

        self.assertIn("must propose", instruction)
        self.assertIn("explicit confirmation", instruction)

    def test_typo_instruction_disables_proposals_when_flag_is_false(self):
        with patch.dict(os.environ, {"VIDEO_EDITOR_PROPOSE_TYPO_CORRECTIONS": "false"}):
            instruction = typo_instruction()

        self.assertIn("Do not propose", instruction)
        self.assertIn("Preserve the user’s supplied", instruction)


if __name__ == "__main__":
    unittest.main(verbosity=2)
