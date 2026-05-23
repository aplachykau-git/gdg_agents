# GDG Krakow Tool (Agent Development Kit)

This project is a multi-agent system built on the [Google Agent Development Kit (ADK) 2.0](https://adk.dev/), written in Python. It leverages the capabilities of Vertex AI (Gemini) models to automatically extract data from receipts and invoices, convert currencies, and generate beautifully formatted Google Docs expense reports using custom templates.

## Project Structure

The project is decoupled into independent modules for better maintainability and portability:
* `orchestrator/` — The main coordinating agent (`gdg_orchestrator`), running on `gemini-2.5-flash`.
* `receipt_scanner/` — A specialized sub-agent for receipt and invoice OCR, currency conversion, and data export.
  * `agent.py` — Configuration and systemic instructions for the sub-agent.
  * `tools.py` — Agent tools (receipt OCR processing, Google Docs/Drive templates integration, exchange rate fetching).
  * `utils.py` — Helper utilities for processing media files (image auto-rotation, PDF first-page rendering).
  * `test_runner.py` — A command-line script to test the sub-agent locally without launching the web interface.

---

## Local Environment Setup

1. Make sure you have Python installed (version 3.9+).
2. Clone the repository:
   ```bash
   git clone https://github.com/aplachykau-git/gdg_agents.git
   cd gdg_agents
   ```

3. Initialize a virtual environment and install the package along with its dependencies in `editable` mode:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   pip install -e .
   ```

4. Authenticate with Google Cloud to use Vertex AI:
   ```bash
   bash <(curl -sSL https://storage.googleapis.com/cloud-samples-data/adc/setup_adc.sh)
   ```
   *When prompted, enter your Google Cloud Project ID (e.g., `gdg-agents-496611`) and complete the authentication in your web browser.*

---

## Environment Variables (.env)

The project relies on `.env` files to store configuration parameters securely (these are ignored in Git).
Each module (`orchestrator` and `receipt_scanner`) has its own `.env` file.

Create a `.env` file in the corresponding directory with the following contents:

```env
# Set to 1 to use Vertex AI, or 0 to use Google AI Studio
GOOGLE_GENAI_USE_VERTEXAI=1

# Your Google Cloud Project ID
GOOGLE_CLOUD_PROJECT=gdg-agents-496611

# The Google Cloud region where models are located
GOOGLE_CLOUD_LOCATION=europe-central2

# The chosen Gemini model
GEMINI_PRO_MODEL=gemini-2.5-pro

# Google Drive and Google Docs parameters for export
GOOGLE_DRIVE_FOLDER_ID=your_drive_folder_id
GOOGLE_DOCS_TEMPLATE_ID=your_docs_template_id
```

---

## Running the Agents

### 1. Launch via ADK Developer UI (Web Interface)
1. Activate the virtual environment:
   ```bash
   source .venv/bin/activate
   ```
2. Navigate to the folder of the desired agent (e.g., the main orchestrator):
   ```bash
   cd orchestrator
   ```
3. Start the ADK web server:
   ```bash
   adk web --port 8000
   ```
4. Open `http://localhost:8000` in your web browser to interact with the agent using a rich web interface.

### 2. Run Local CLI Test (Script)
You can test the receipt scanner sub-agent directly via a command-line script:
```bash
python receipt_scanner/test_runner.py
```
Thanks to dynamic path resolution, the script will run seamlessly on any machine.
