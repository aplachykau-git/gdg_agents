<script>
  import { 
    Workflow, 
    Video, 
    Receipt, 
    Share2, 
    Users, 
    Calendar, 
    Clock, 
    Mail, 
    Sparkles, 
    ArrowRight, 
    X, 
    CheckCircle2, 
    Zap, 
    Activity, 
    Cpu, 
    ExternalLink,
    Maximize2,
    Layers
  } from '@lucide/svelte';

  let { 
    currentExecutingAgent = 'root_agent', 
    isLoading = false, 
    selectedApp = 'root_agent', 
    onSelectAgent = null, 
    onClose = null 
  } = $props();

  let inspectedAgentId = $state('root_agent');

  const AGENTS_META = [
    {
      id: 'root_agent',
      name: 'Root Orchestrator',
      role: 'Main Router & Coordinator',
      model: 'gemini-2.5-flash',
      color: 'var(--agent-root)',
      bg: 'var(--bg-root)',
      icon: Workflow,
      isRoot: true,
      port: 8080,
      protocol: 'Local / SSE Hub',
      desc: 'Central dispatcher. Evaluates user intent, verifies execution prerequisites, and delegates tasks to specialized sub-agents via A2A or direct transfer.',
      tools: ['transfer_to_video_editor', 'transfer_to_receipt_scanner', 'transfer_to_linkedin_post_generator', 'transfer_to_registration_manager', 'transfer_to_event_planner', 'transfer_to_agenda_generator', 'transfer_to_office_secretary'],
      x: 50,
      y: 50
    },
    {
      id: 'video_editor',
      name: 'Live Video Editor',
      role: 'Speaker Video & Outpainting',
      model: 'Veo 3.1 / Omni Flash',
      color: 'var(--agent-video)',
      bg: 'var(--bg-video)',
      icon: Video,
      isA2A: true,
      port: 8081,
      protocol: 'A2A Protocol (gRPC/HTTP)',
      desc: 'Validates facial landmarks, outpaints portrait photos to 9:16 vertical ratio, generates 8s Veo video loops, and renders 4K MP4 / GIF cards.',
      tools: ['verify_portrait_photo', 'stage_uploaded_media', 'animate_photo', 'update_composer', 'render_composer'],
      x: 18,
      y: 20
    },
    {
      id: 'receipt_scanner',
      name: 'Receipt Scanner',
      role: 'Vision OCR & Pekao Rates',
      model: 'gemini-2.5-pro',
      color: 'var(--agent-receipt)',
      bg: 'var(--bg-receipt)',
      icon: Receipt,
      isA2A: true,
      port: 8082,
      protocol: 'A2A Protocol (gRPC/HTTP)',
      desc: 'High-reasoning Vision OCR for receipts and invoices. Fetches live Pekao Bank & NBP exchange rates, converts currencies, and populates Google Docs expense reports.',
      tools: ['read_receipt_file', 'get_usd_pln_rate', 'export_summary_to_google_doc', 'scan_receipt_with_vision'],
      x: 82,
      y: 20
    },
    {
      id: 'linkedin_post_generator',
      name: 'LinkedIn Planner',
      role: 'Announcements & Recaps',
      model: 'gemini-2.5-flash',
      color: 'var(--agent-linkedin)',
      bg: 'var(--bg-linkedin)',
      icon: Share2,
      port: 8080,
      protocol: 'In-Process Sub-Agent',
      desc: 'Generates viral speaker announcements and multi-variant event recap posts with hashtag tuning and tone adjustments.',
      tools: ['generate_speaker_announcement', 'generate_recap_variants'],
      x: 14,
      y: 56
    },
    {
      id: 'registration_manager',
      name: 'Registrations Manager',
      role: 'Capacity & Duplicate Filter',
      model: 'gemini-2.5-flash',
      color: 'var(--agent-registration)',
      bg: 'var(--bg-registration)',
      icon: Users,
      port: 8080,
      protocol: 'In-Process Sub-Agent',
      desc: 'Performs fuzzy phonetic deduplication, capacity thresholding, organizer verification, and exports clean DOCX participant lists.',
      tools: ['filter_and_clean_registrations', 'manage_organisers_config'],
      x: 86,
      y: 56
    },
    {
      id: 'event_planner',
      name: 'Event Scheduler',
      role: 'Meetup & Holiday Conflict Radar',
      model: 'gemini-2.5-flash',
      color: 'var(--agent-planner)',
      bg: 'var(--bg-planner)',
      icon: Calendar,
      port: 8080,
      protocol: 'In-Process Sub-Agent',
      desc: 'Scans Kraków tech meetups on Luma and Meetup.com, checks statutory Polish holiday clashes, and recommends optimal mid-week dates.',
      tools: ['find_optimal_meetup_date', 'check_holiday_clashes'],
      x: 24,
      y: 84
    },
    {
      id: 'agenda_generator',
      name: 'Agenda Formatter',
      role: 'Timeline Math & 5m Snapping',
      model: 'gemini-2.5-flash',
      color: 'var(--agent-agenda)',
      bg: 'var(--bg-agenda)',
      icon: Clock,
      port: 8080,
      protocol: 'In-Process Sub-Agent',
      desc: 'Dynamically computes minute-by-minute session schedules from 17:30 with 5-minute interval rounding, talk durations, and break pauses.',
      tools: ['generate_agenda_timeline'],
      x: 50,
      y: 88
    },
    {
      id: 'office_secretary',
      name: 'Office Secretary',
      role: 'Visitor Access & Event Hub',
      model: 'gemini-2.5-flash',
      color: 'var(--agent-office)',
      bg: 'var(--bg-office)',
      icon: Mail,
      port: 8080,
      protocol: 'In-Process Sub-Agent',
      desc: 'Validates mandatory dates, composes polite key access requests for external guests, and handles Event Hub space reservations.',
      tools: ['generate_office_email'],
      x: 76,
      y: 84
    }
  ];

  const inspectedAgent = $derived.by(() => {
    return AGENTS_META.find(a => a.id === inspectedAgentId) || AGENTS_META[0];
  });

  function isAgentActive(agentId) {
    if (!isLoading) return false;
    const cleanCurrent = (currentExecutingAgent || selectedApp || '').toLowerCase();
    return cleanCurrent.includes(agentId) || (agentId === 'root_agent' && cleanCurrent === 'root');
  }

  function handleSelect(agentId) {
    inspectedAgentId = agentId;
    if (onSelectAgent) {
      onSelectAgent(agentId);
    }
  }
</script>

<div class="agent-graph-backdrop" role="dialog" aria-modal="true">
  <div class="agent-graph-modal">
    <!-- Header -->
    <header class="graph-modal-header">
      <div class="header-title-group">
        <div class="graph-header-icon">
          <Workflow size={18} />
        </div>
        <div>
          <h3>Multi-Agent DAG Architecture</h3>
          <span class="header-sub">ADK 2.0 Autonomous Network &bull; Agent-to-Agent (A2A) Protocols</span>
        </div>
      </div>

      <div class="header-actions">
        {#if isLoading}
          <div class="live-pulse-badge">
            <span class="pulse-dot"></span>
            <span>Live Execution Active</span>
          </div>
        {/if}

        {#if onClose}
          <button class="close-btn" onclick={onClose} title="Close Graph View">
            <X size={18} />
          </button>
        {/if}
      </div>
    </header>

    <!-- Main Graph Canvas & Inspector Grid -->
    <div class="graph-body-layout">
      <!-- Left / Top: Interactive Topology Canvas -->
      <div class="graph-canvas-container">
        <!-- SVG Connection Lines -->
        <svg class="graph-svg-layer" viewBox="0 0 100 100" preserveAspectRatio="none">
          <!-- Edges from Root (50, 50) to all sub-agents -->
          {#each AGENTS_META as agent}
            {#if !agent.isRoot}
              {@const active = isAgentActive(agent.id)}
              <line 
                x1="50" 
                y1="50" 
                x2={agent.x} 
                y2={agent.y} 
                class="graph-edge-line" 
                class:edge-active={active}
                class:edge-a2a={agent.isA2A}
                style="--edge-color: {agent.color};"
              />
            {/if}
          {/each}
        </svg>

        <!-- HTML Interactive Nodes Layer -->
        <div class="graph-nodes-layer">
          {#each AGENTS_META as agent}
            {@const active = isAgentActive(agent.id)}
            {@const isSelected = inspectedAgentId === agent.id}
            {@const Icon = agent.icon}

            <button 
              class="agent-node-card" 
              class:node-root={agent.isRoot}
              class:node-active={active}
              class:node-selected={isSelected}
              style="left: {agent.x}%; top: {agent.y}%; --node-color: {agent.color}; --node-bg: {agent.bg};"
              onclick={() => handleSelect(agent.id)}
            >
              <div class="node-icon-box">
                <Icon size={agent.isRoot ? 22 : 16} />
              </div>

              <div class="node-info">
                <div class="node-title-row">
                  <span class="node-name">{agent.name}</span>
                  {#if agent.isA2A}
                    <span class="a2a-pill">A2A</span>
                  {/if}
                </div>
                <span class="node-role">{agent.role}</span>
              </div>

              {#if active}
                <div class="active-badge-tag">
                  <Activity size={10} />
                  <span>RUNNING</span>
                </div>
              {/if}
            </button>
          {/each}
        </div>
      </div>

      <!-- Right / Bottom: Agent Inspector Drawer -->
      <aside class="agent-inspector-panel">
        <div class="inspector-header" style="border-left: 4px solid {inspectedAgent.color}">
          <div class="inspector-title-row">
            <div class="inspector-icon-wrap" style="background: {inspectedAgent.bg}; color: {inspectedAgent.color}">
              <inspectedAgent.icon size={20} />
            </div>
            <div>
              <h4>{inspectedAgent.name}</h4>
              <span class="inspector-protocol-tag">{inspectedAgent.protocol}</span>
            </div>
          </div>

          <div class="inspector-model-badge">
            <Cpu size={13} />
            <span>{inspectedAgent.model}</span>
          </div>
        </div>

        <div class="inspector-body">
          <div class="inspector-section">
            <span class="section-label">Capabilities & Description</span>
            <p class="section-desc">{inspectedAgent.desc}</p>
          </div>

          <div class="inspector-section">
            <span class="section-label">Registered Tools ({inspectedAgent.tools.length})</span>
            <div class="tools-chips-grid">
              {#each inspectedAgent.tools as tool}
                <div class="tool-chip">
                  <Zap size={11} />
                  <span>{tool}</span>
                </div>
              {/each}
            </div>
          </div>

          {#if inspectedAgent.port}
            <div class="inspector-section">
              <span class="section-label">Service Port & Endpoints</span>
              <div class="endpoint-card">
                <span class="port-label">Port {inspectedAgent.port}</span>
                {#if inspectedAgent.isA2A}
                  <span class="agent-card-link">/.well-known/agent-card.json</span>
                {:else}
                  <span class="agent-card-link">Local Process Execution</span>
                {/if}
              </div>
            </div>
          {/if}
        </div>

        <div class="inspector-footer">
          <button 
            class="switch-agent-btn" 
            style="background: {inspectedAgent.color};"
            onclick={() => {
              if (onSelectAgent) onSelectAgent(inspectedAgent.id);
              if (onClose) onClose();
            }}
          >
            <span>Focus Chat on {inspectedAgent.name}</span>
            <ArrowRight size={14} />
          </button>
        </div>
      </aside>
    </div>
  </div>
</div>

<style>
  .agent-graph-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.75);
    backdrop-filter: blur(8px);
    z-index: 100;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
  }

  .agent-graph-modal {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    width: 95vw;
    max-width: 1200px;
    height: 85vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: var(--shadow-elevation-3);
  }

  /* Header */
  .graph-modal-header {
    height: 60px;
    padding: 0 20px;
    border-bottom: 1px solid var(--border-subtle);
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: var(--bg-surface-elevated);
  }

  .header-title-group {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .graph-header-icon {
    width: 34px;
    height: 34px;
    border-radius: var(--radius-sm);
    background: var(--bg-root);
    color: var(--agent-root);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .header-title-group h3 {
    font-size: var(--font-size-title-md);
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
  }

  .header-sub {
    font-size: var(--font-size-label);
    color: var(--text-tertiary);
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .live-pulse-badge {
    display: flex;
    align-items: center;
    gap: 6px;
    background: rgba(56, 189, 248, 0.15);
    color: var(--agent-root);
    border: 1px solid rgba(56, 189, 248, 0.3);
    padding: 4px 10px;
    border-radius: var(--radius-pill);
    font-size: var(--font-size-label);
    font-weight: 600;
  }

  .pulse-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--agent-root);
  }

  .close-btn {
    background: transparent;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    padding: 6px;
    border-radius: var(--radius-xs);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .close-btn:hover {
    background: var(--bg-surface-variant);
    color: var(--text-primary);
  }

  /* Body Layout */
  .graph-body-layout {
    flex: 1;
    display: grid;
    grid-template-columns: 1fr 340px;
    overflow: hidden;
  }

  /* Canvas */
  .graph-canvas-container {
    position: relative;
    background: radial-gradient(circle at 50% 50%, rgba(26, 115, 232, 0.04) 0%, transparent 70%), var(--bg-app);
    overflow: hidden;
  }

  .graph-svg-layer {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
  }

  .graph-edge-line {
    stroke: var(--border-medium);
    stroke-width: 0.35;
    stroke-dasharray: 1 1;
    transition: all 0.3s ease;
  }

  .graph-edge-line.edge-a2a {
    stroke: var(--agent-video);
    stroke-width: 0.45;
    stroke-dasharray: 1.5 1;
  }

  .graph-edge-line.edge-active {
    stroke: var(--edge-color);
    stroke-width: 0.8;
    stroke-dasharray: 2 1;
    animation: dash-flow 0.8s linear infinite;
    filter: drop-shadow(0 0 2px var(--edge-color));
  }

  @keyframes dash-flow {
    from { stroke-dashoffset: 6; }
    to { stroke-dashoffset: 0; }
  }

  /* Nodes */
  .graph-nodes-layer {
    position: absolute;
    inset: 0;
  }

  .agent-node-card {
    position: absolute;
    transform: translate(-50%, -50%);
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: 8px 12px;
    display: flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: var(--shadow-elevation-1);
    max-width: 220px;
  }

  .agent-node-card:hover {
    transform: translate(-50%, -54%) scale(1.04);
    border-color: var(--node-color);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3), 0 0 8px var(--node-color);
    z-index: 10;
  }

  .agent-node-card.node-root {
    padding: 12px 16px;
    border-width: 2px;
    border-color: var(--agent-root);
    box-shadow: 0 0 20px rgba(56, 189, 248, 0.2);
    z-index: 5;
  }

  .agent-node-card.node-selected {
    border-color: var(--node-color);
    background: var(--bg-surface-elevated);
    box-shadow: 0 0 12px var(--node-color);
  }

  .agent-node-card.node-active {
    border-color: var(--node-color);
    animation: active-node-pulse 1.5s infinite ease-in-out;
  }

  @keyframes active-node-pulse {
    0%, 100% { box-shadow: 0 0 8px var(--node-color); }
    50% { box-shadow: 0 0 24px var(--node-color); }
  }

  .node-icon-box {
    width: 32px;
    height: 32px;
    border-radius: var(--radius-sm);
    background: var(--node-bg);
    color: var(--node-color);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .node-info {
    display: flex;
    flex-direction: column;
    text-align: left;
    overflow: hidden;
  }

  .node-title-row {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .node-name {
    font-size: var(--font-size-body-sm);
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .node-role {
    font-size: var(--font-size-label);
    color: var(--text-tertiary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .a2a-pill {
    font-size: 9px;
    font-weight: 700;
    background: rgba(168, 85, 247, 0.2);
    color: var(--agent-video);
    padding: 1px 4px;
    border-radius: var(--radius-pill);
  }

  .active-badge-tag {
    position: absolute;
    top: -8px;
    right: -8px;
    background: var(--node-color);
    color: #121314;
    font-size: 9px;
    font-weight: 800;
    padding: 2px 6px;
    border-radius: var(--radius-pill);
    display: flex;
    align-items: center;
    gap: 3px;
  }

  /* Inspector Panel */
  .agent-inspector-panel {
    background: var(--bg-surface-elevated);
    border-left: 1px solid var(--border-subtle);
    display: flex;
    flex-direction: column;
    overflow-y: auto;
  }

  .inspector-header {
    padding: 16px;
    background: var(--bg-surface);
    border-bottom: 1px solid var(--border-subtle);
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .inspector-title-row {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .inspector-icon-wrap {
    width: 36px;
    height: 36px;
    border-radius: var(--radius-sm);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .inspector-title-row h4 {
    font-size: var(--font-size-body-md);
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
  }

  .inspector-protocol-tag {
    font-size: var(--font-size-label);
    color: var(--text-tertiary);
  }

  .inspector-model-badge {
    display: flex;
    align-items: center;
    gap: 6px;
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    padding: 4px 8px;
    border-radius: var(--radius-xs);
    font-family: var(--font-family-mono);
    font-size: var(--font-size-label);
    color: var(--text-secondary);
    width: fit-content;
  }

  .inspector-body {
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    flex: 1;
  }

  .inspector-section {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .section-label {
    font-size: var(--font-size-label);
    font-weight: 700;
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .section-desc {
    font-size: var(--font-size-body-sm);
    color: var(--text-secondary);
    line-height: 1.5;
  }

  .tools-chips-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .tool-chip {
    display: flex;
    align-items: center;
    gap: 4px;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    padding: 3px 8px;
    border-radius: var(--radius-xs);
    font-family: var(--font-family-mono);
    font-size: 11px;
    color: var(--text-primary);
  }

  .endpoint-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-xs);
    padding: 8px 10px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: var(--font-size-label);
  }

  .port-label {
    font-weight: 700;
    color: var(--primary-accent);
  }

  .agent-card-link {
    font-family: var(--font-family-mono);
    color: var(--text-tertiary);
  }

  .inspector-footer {
    padding: 14px;
    border-top: 1px solid var(--border-subtle);
    background: var(--bg-surface);
  }

  .switch-agent-btn {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 8px 14px;
    border-radius: var(--radius-pill);
    border: none;
    color: #121314;
    font-weight: 600;
    font-size: var(--font-size-body-sm);
    cursor: pointer;
    transition: opacity 0.15s ease;
  }

  .switch-agent-btn:hover {
    opacity: 0.9;
  }
</style>
