"""Every agent the root agent routes to is wired into the UI, the docs and the diagram.

An agent touches many files (see "Adding or Changing an Agent" in AGENTS.md). This test fails
when one of them is forgotten, e.g. a new agent missing from the architecture diagram.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def sub_agent_names() -> list[str]:
    source = read("agents/root_agent/agent.py")
    block = re.search(r"sub_agents=\[(.*?)\]", source, re.DOTALL).group(1)
    variables = re.findall(r"(\w+_agent)\b", block)
    names = []
    for var in variables:
        if var == "video_agent":
            names.append("video_editor")
        elif var == "receipt_agent":
            names.append("receipt_scanner")
        else:
            module = re.search(rf"from agents\.(\w+)\.agent import {var}\b", source)
            if module is None:
                module = re.search(rf"from (\w+)\.agent import {var}\b", source)
            names.append(module.group(1))
    return names


class AgentWiringConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.agents = sub_agent_names()

    def test_found_all_sub_agents(self):
        self.assertIn("qr_code_generator", self.agents)
        self.assertGreaterEqual(len(self.agents), 8)

    def check(self, rel: str, pattern: str) -> None:
        text = read(rel)
        missing = [a for a in self.agents if not re.search(pattern.format(agent=re.escape(a)), text)]
        self.assertEqual(missing, [], f"{rel} does not mention: {', '.join(missing)}")

    def test_frontend(self):
        self.check("frontend/src/lib/config.js", r"name: '{agent}'")  # DEFAULT_APPS
        self.check("frontend/src/lib/config.js", r"id: '{agent}'")  # capabilities catalog
        self.check("frontend/src/App.svelte", r'id: "{agent}"')
        self.check("frontend/src/lib/AgentGraph.svelte", r"id: '{agent}'")
        self.check("frontend/src/lib/agents.js", r"transfer_to_{agent}:")

    def test_docs(self):
        self.check("AGENTS.md", r"\| `{agent}` \|")
        self.check("docs/design.md", r"\| `{agent}` \|")
        self.check("docs/architecture.mmd", r"<i>{agent}</i>")
        self.check("docs/SOLUTION_ARCHITECTURE.md", r"`{agent}`")

    def test_readme_embeds_the_current_diagram(self):
        diagram = read("docs/architecture.mmd").strip()
        self.assertIn(diagram, read("README.md"), "Paste docs/architecture.mmd into the README mermaid block")

    def test_docs_use_relative_links(self):
        doc_paths = [
            "README.md",
            "AGENTS.md",
            *(str(p.relative_to(ROOT)) for p in (ROOT / "docs").glob("*.md")),
            *(str(p.relative_to(ROOT)) for p in (ROOT / "agents").rglob("*.md")),
        ]
        for rel in doc_paths:
            self.assertNotRegex(read(rel), r"\]\(file:///", rel)


if __name__ == "__main__":
    unittest.main()
