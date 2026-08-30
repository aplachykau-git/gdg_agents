# Video Editor Agent Flow

> **Visual Assets**: [🖼️ PNG Diagram](file:///Users/aplachykau/Experiments/gdg_krakow_tool/agents/video_editor/docs/assets/video_editor_dag.png) • [📄 PDF Document](file:///Users/aplachykau/Experiments/gdg_krakow_tool/agents/video_editor/docs/assets/video_editor_dag.pdf) • [📐 SVG Vector](file:///Users/aplachykau/Experiments/gdg_krakow_tool/agents/video_editor/docs/assets/video_editor_dag.svg)

```mermaid
%%{init: {
  'theme': 'dark',
  'themeVariables': {
    'darkMode': true,
    'background': '#0f172a',
    'primaryColor': '#1e293b',
    'primaryTextColor': '#f8fafc',
    'primaryBorderColor': '#f59e0b',
    'lineColor': '#38bdf8',
    'textColor': '#f8fafc',
    'fontSize': '13px',
    'fontFamily': 'Inter, system-ui, -apple-system, sans-serif',
    'clusterBkg': '#131926',
    'clusterBorder': '#334155',
    'edgeLabelBackground': '#1e293b',
    'tertiaryColor': '#1e293b',
    'tertiaryBorderColor': '#334155',
    'nodeBorder': '#38bdf8',
    'mainBkg': '#1e293b',
    'nodeTextColor': '#f8fafc'
  }
}}%%

flowchart TD
    User[/"👤 User / Root Agent Request"/]
    Agent["🎬 <b>Conversational Video Editor Agent</b><br/><i>gemini-3.5-flash-lite</i>"]
    Help["💡 <b>Capability & Guidance Responder</b><br/><i>Answers format/help queries</i>"]
    Tool["⚙️ <b>create_video_card tool</b><br/><i>Session staging & schema validation</i>"]
    Draft[("💾 <b>Session Draft State</b><br/><i>Speaker details & uploaded media</i>")]
    Confirm{"❓ <b>Confirmation Required?</b><br/><i>CONFIRM_BEFORE_RENDER</i>"}
    Render["🎥 <b>Deterministic Render Pipeline</b><br/>• Outpainting 9:16 (Flash Lite Image)<br/>• Gemini Omni / Veo 3.1 Video Gen<br/>• HyperFrames 1080p / 4K Composition"]
    Result["📦 <b>Rendered Assets / Typed Error</b><br/>• MP4 Video • PNG Poster • Avatar"]

    User --> Agent
    Agent -->|Unrelated query| Help
    Help --> User
    Agent -->|Details, media, prompt, or confirm| Tool
    Tool <--> Draft
    Tool -->|Missing fields or typo notice| Agent
    Tool --> Confirm
    Confirm -->|Draft approval required| Agent
    Confirm -->|Ready to render| Render
    Render --> Result
    Result --> Agent
    Agent --> User

    classDef default fill:#1e293b,stroke:#475569,stroke-width:1.5px,color:#f8fafc;
    classDef agentNode fill:#1e293b,stroke:#f59e0b,stroke-width:2px,color:#f8fafc;
    classDef toolNode fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#f8fafc;
    classDef renderNode fill:#1e293b,stroke:#10b981,stroke-width:2px,color:#f8fafc;
    classDef stateNode fill:#1e293b,stroke:#a855f7,stroke-width:2px,color:#f8fafc;
    classDef decisionNode fill:#1e293b,stroke:#f97316,stroke-width:2px,color:#f8fafc;

    class Agent agentNode;
    class Tool toolNode;
    class Render renderNode;
    class Draft stateNode;
    class Confirm decisionNode;
```
