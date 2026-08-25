import asyncio
import os
import sys
from pathlib import Path

# Dynamically add project root and subfolders for clean imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "agents"))
sys.path.insert(0, str(project_root / "agents" / "receipt_scanner"))

os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "1"
os.environ["GOOGLE_CLOUD_PROJECT"] = "gdg-agents-496611"
os.environ["GOOGLE_CLOUD_LOCATION"] = "europe-central2"

from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

from agents.receipt_scanner.agent import receipt_agent


async def main():
    session_service = InMemorySessionService()
    runner = Runner(
        app_name="receipt_agent", agent=receipt_agent, session_service=session_service, auto_create_session=True
    )

    # Dynamically find the test invoice relative to the project root
    file_path = project_root / "gdg_agent" / "invoice_processing" / "exemplary_data" / "case_001" / "invoice.pdf"
    if not file_path.exists():
        # Fallback to local sibling directory
        sibling_path = (
            project_root.parent / "gdg_agent" / "invoice_processing" / "exemplary_data" / "case_001" / "invoice.pdf"
        )
        if sibling_path.exists():
            file_path = sibling_path
        else:
            # Legacy absolute path fallback
            legacy_path = Path(
                "/Users/aplachykau/Experiments/gdg_krakow_tool/gdg_agent/invoice_processing/exemplary_data/case_001/invoice.pdf"
            )
            if legacy_path.exists():
                file_path = legacy_path

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
