import os
import sys
from pathlib import Path

# Add project root to sys.path for correct imports
sys.path.append(str(Path(__file__).resolve().parent.parent))

from google.adk.agents.llm_agent import Agent
from receipt_scanner.agent import receipt_agent

root_agent = Agent(
    model="gemini-2.5-flash",
    name="gdg_orchestrator",
    description="Main orchestrator agent of GDG Krakow",
    instruction="""You are the main assistant agent for GDG Krakow. 
Your task is to help the user with various requests. 
VERY IMPORTANT: If the user asks to process receipts, invoices, extract data from them, or create an Expense Report, you MUST use the `receipt_scanner` tool (sub-agent).
Pass the file paths or information about the uploaded documents to it, and return its response to the user.""",
    sub_agents=[receipt_agent]
)
