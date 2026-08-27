import asyncio
import os
import sys
import warnings
from pathlib import Path

# Suppress upstream Google ADK BaseAgentConfig deprecation warning
warnings.filterwarnings("ignore", message=".*BaseAgentConfig.*")

# Dynamically add project root and subfolders for clean imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "agents"))
sys.path.insert(0, str(project_root / "agents" / "receipt_scanner"))

from dotenv import load_dotenv

# Load environment configuration from .env
load_dotenv(project_root / ".env")

from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

from agents.receipt_scanner.agent import receipt_agent


async def main():
    session_service = InMemorySessionService()
    runner = Runner(
        app_name="receipt_agent", agent=receipt_agent, session_service=session_service, auto_create_session=True
    )

    # Dynamically find the test invoice relative to the project root or fixtures
    if len(sys.argv) > 1:
        file_path = Path(sys.argv[1]).resolve()
    else:
        fixtures_dir = project_root / "agents" / "receipt_scanner" / "evaluation" / "fixtures"
        sample_files = sorted(
            list(fixtures_dir.glob("*.jpg")) + list(fixtures_dir.glob("*.pdf")) + list(fixtures_dir.glob("*.png"))
        )
        file_path = sample_files[0] if sample_files else fixtures_dir / "sample_invoice.pdf"

    print(f"Sending request for: {file_path}...")

    user_query = f"Analyze receipt: {file_path}"

    async for event in runner.run_async(
        user_id="test_user",
        session_id="test_session",
        new_message=types.Content(role="user", parts=[types.Part.from_text(text=user_query)]),
    ):
        # Print all text parts
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    print(part.text, end="", flush=True)
                elif part.function_call:
                    print(f"\n[Tool Call] {part.function_call.name}({part.function_call.args})")
                elif part.function_response:
                    print(f"\n[Tool Response] {part.function_response.name}: {part.function_response.response}")

    print("\n\n--- Finished ---")


if __name__ == "__main__":
    asyncio.run(main())
