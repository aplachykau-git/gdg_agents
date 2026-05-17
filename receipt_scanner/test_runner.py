import asyncio
import os
import sys

sys.path.insert(0, "/Users/aplachykau/Experiments/gdg_krakow_tool")
sys.path.insert(0, "/Users/aplachykau/Experiments/gdg_krakow_tool/receipt_agent")

os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "1"
os.environ["GOOGLE_CLOUD_PROJECT"] = "gdg-agents-496611"
os.environ["GOOGLE_CLOUD_LOCATION"] = "europe-central2"

from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types
from receipt_agent.agent import root_agent

async def main():
    session_service = InMemorySessionService()
    runner = Runner(
        app_name="receipt_agent",
        agent=root_agent,
        session_service=session_service,
        auto_create_session=True
    )
    
    file_path = "/Users/aplachykau/Experiments/gdg_krakow_tool/gdg_agent/invoice_processing/exemplary_data/case_001/invoice.pdf"
    print(f"Sending request for: {file_path}...")
    
    user_query = f"Analyze receipt: {file_path}"
    
    async for event in runner.run_async(
        user_id="test_user",
        session_id="test_session",
        new_message=types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_query)]
        )
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
