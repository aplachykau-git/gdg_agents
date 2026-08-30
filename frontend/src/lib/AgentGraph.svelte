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
    Layers,
    Terminal,
    Radio,
    FileCode2,
    Clock3,
    ArrowUpRight,
    FileText
  } from '@lucide/svelte';
  import { AGENT_CAPABILITIES_CATALOG } from './constants.js';

  let { 
    events = [],
    currentExecutingAgent = 'root_agent', 
    isLoading = false, 
    selectedApp = 'root_agent', 
    onSelectAgent = null, 
    onClose = null 
  } = $props();

  let inspectedAgentId = $state('root_agent');
  let activeTab = $state('telemetry'); // 'telemetry' | 'spec'

  const AGENTS_META = [
    {
      id: 'root_agent',
      name: 'Main',
      role: 'Main Router & Coordinator',
      model: 'gemini-3.5-flash-lite',
      color: '#38BDF8',
      bg: 'rgba(56, 189, 248, 0.12)',
      icon: Layers,
      isRoot: true,
      port: 8080,
      protocol: 'Dispatcher / SSE Hub',
      desc: 'Central dispatcher. Coordinates specialized agents and manages multi-agent workflows for community tasks.',
      tools: ['transfer_to_agent (video_editor)', 'transfer_to_agent (receipt_scanner)', 'transfer_to_agent (linkedin_post_generator)', 'transfer_to_agent (registration_manager)', 'transfer_to_agent (event_planner)', 'transfer_to_agent (agenda_generator)', 'transfer_to_agent (office_secretary)'],
      x: 50,
      y: 50
    },
    {
      id: 'video_editor',
      name: 'Live Video Editor',
      role: 'Speaker Video & Cards',
      model: 'Omni Video / Omni Flash',
      color: '#C084FC',
      bg: 'rgba(192, 132, 252, 0.12)',
      icon: Video,
      isA2A: true,
      port: 8080,
      protocol: 'A2A Protocol (JSON-RPC)',
      desc: 'Transforms portrait photos into animated speaker intro videos and branded presentation cards with Omni.',
      tools: ['verify_portrait_photo', 'stage_uploaded_media', 'animate_photo', 'update_composer', 'render_composer', 'extend_portrait_canvas'],
      x: 18,
      y: 20
    },
    {
      id: 'receipt_scanner',
      name: 'Receipt Scanner',
      role: 'Expenses & Exchange Rates',
      model: 'gemini-3.7-flash',
      color: '#34D399',
      bg: 'rgba(52, 211, 153, 0.12)',
      icon: Receipt,
      isA2A: true,
      port: 8080,
      protocol: 'A2A Protocol (JSON-RPC)',
      desc: 'Reads receipts and invoices, fetches live banking exchange rates, converts currencies, and creates Google Docs reports.',
      tools: ['read_receipt_file', 'get_usd_pln_rate', 'export_summary_to_google_doc', 'scan_receipt_with_vision'],
      x: 82,
      y: 20
    },
    {
      id: 'linkedin_post_generator',
      name: 'LinkedIn Planner',
      role: 'Announcements & Recaps',
      model: 'gemini-3.5-flash-lite',
      color: '#0A66C2',
      bg: 'rgba(10, 102, 194, 0.12)',
      icon: Share2,
      port: 8080,
      protocol: 'In-Process Sub-Agent',
      desc: 'Generates engaging speaker announcements and multi-variant event recap posts with tailored hashtags.',
      tools: ['generate_speaker_announcement', 'generate_recap_variants'],
      x: 14,
      y: 56
    },
    {
      id: 'registration_manager',
      name: 'Registrations Manager',
      role: 'Capacity & Rosters',
      model: 'gemini-3.5-flash-lite',
      color: '#FB923C',
      bg: 'rgba(251, 146, 60, 0.12)',
      icon: Users,
      port: 8080,
      protocol: 'In-Process Sub-Agent',
      desc: 'Cleans attendee registration lists, filters duplicates, and partitions confirmed attendees and waitlists.',
      tools: ['process_registrations', 'stage_uploaded_registration', 'stage_manual_text_registrations', 'get_organisers_list', 'add_organiser', 'remove_organiser'],
      x: 86,
      y: 56
    },
    {
      id: 'event_planner',
      name: 'Event Scheduler',
      role: 'Meetups & Holidays',
      model: 'gemini-3.5-flash-lite',
      color: '#F472B6',
      bg: 'rgba(244, 114, 182, 0.12)',
      icon: Calendar,
      port: 8080,
      protocol: 'In-Process Sub-Agent',
      desc: 'Scans tech meetup calendars and public holidays to recommend optimal, conflict-free event dates.',
      tools: ['get_public_holidays', 'google_search'],
      x: 24,
      y: 84
    },
    {
      id: 'agenda_generator',
      name: 'Agenda Formatter',
      role: 'Timelines & Breaks',
      model: 'gemini-3.5-flash-lite',
      color: '#FBBF24',
      bg: 'rgba(251, 191, 36, 0.12)',
      icon: Clock,
      port: 8080,
      protocol: 'In-Process Sub-Agent',
      desc: 'Computes structured minute-by-minute session schedules with talk durations, networking, and breaks.',
      tools: ['generate_agenda_timeline'],
      x: 50,
      y: 88
    },
    {
      id: 'office_secretary',
      name: 'Office Secretary',
      role: 'Visitor Access & Requests',
      model: 'gemini-3.5-flash-lite',
      color: '#2DD4BF',
      bg: 'rgba(45, 212, 191, 0.12)',
      icon: Mail,
      port: 8080,
      protocol: 'In-Process Sub-Agent',
      desc: 'Composes polite building security visitor access requests and meeting room reservation emails.',
      tools: ['generate_office_email'],
      x: 76,
      y: 84
    }
  ];

  const inspectedAgent = $derived.by(() => {
    return AGENTS_META.find(a => a.id === inspectedAgentId) || AGENTS_META[0];
  });

  const inspectedAgentDetails = $derived.by(() => {
    return AGENT_CAPABILITIES_CATALOG.find(a => a.id === inspectedAgent.id);
  });

  // Determine which agents have actively participated in the current session events
  const participatedAgentIds = $derived.by(() => {
    const ids = new Set(['root_agent']);
    if (selectedApp && selectedApp !== 'root_agent') {
      ids.add(selectedApp);
    }
    if (currentExecutingAgent && currentExecutingAgent !== 'root_agent') {
      ids.add(currentExecutingAgent);
    }
    for (const ev of events) {
      if (ev.author && ev.author !== 'user') {
        const a = ev.author.toLowerCase();
        for (const meta of AGENTS_META) {
          if (a.includes(meta.id) || a.includes(meta.id.replace('_agent', ''))) {
            ids.add(meta.id);
          }
        }
      }
      if (ev.actions?.transferToAgent) {
        ids.add(ev.actions.transferToAgent);
      }
      if (ev.nodeInfo?.path) {
        const p = ev.nodeInfo.path.toLowerCase();
        for (const meta of AGENTS_META) {
          if (p.includes(meta.id)) {
            ids.add(meta.id);
          }
        }
      }
      if (ev.content?.parts) {
        for (const part of ev.content.parts) {
          const fc = part.function_call || part.functionCall;
          if (fc) {
            if (fc.name === 'transfer_to_agent' && fc.args?.agent_name) {
              ids.add(fc.args.agent_name);
            }
            for (const meta of AGENTS_META) {
              if (meta.tools.some(t => t.includes(fc.name))) {
                ids.add(meta.id);
              }
            }
          }
        }
      }
    }
    return Array.from(ids);
  });

  // Filter telemetry items for the currently inspected agent
  const agentTelemetryItems = $derived.by(() => {
    const items = [];
    let stepNum = 1;
    for (const ev of events) {
      if (ev.author === 'user') continue;

      const authorClean = (ev.author || '').toLowerCase();
      const nodePath = (ev.nodeInfo?.path || '').toLowerCase();
      const isForInspected = inspectedAgentId === 'root_agent' 
        ? true 
        : (authorClean.includes(inspectedAgentId) || nodePath.includes(inspectedAgentId) || ev.actions?.transferToAgent === inspectedAgentId);

      if (ev.actions?.transferToAgent) {
        if (isForInspected || ev.actions.transferToAgent === inspectedAgentId) {
          items.push({
            id: `transfer-${stepNum++}`,
            type: 'transfer',
            title: `Transfer to ${ev.actions.transferToAgent}`,
            desc: `Delegated execution to ${ev.actions.transferToAgent}`,
            author: ev.author || 'root_agent',
            target: ev.actions.transferToAgent,
            timestamp: ev.timestamp ? new Date(ev.timestamp * 1000).toLocaleTimeString() : 'Now',
            raw: ev.actions
          });
        }
      }

      if (ev.content?.parts) {
        for (const part of ev.content.parts) {
          const fc = part.function_call || part.functionCall;
          const fr = part.function_response || part.functionResponse;

          if (fc) {
            const isFcForAgent = inspectedAgentId === 'root_agent' || isForInspected || (fc.args?.agent_name === inspectedAgentId);
            if (isFcForAgent) {
              items.push({
                id: `fc-${stepNum++}`,
                type: 'call',
                title: `Tool Call: ${fc.name}`,
                desc: JSON.stringify(fc.args || {}),
                author: ev.author || inspectedAgentId,
                timestamp: ev.timestamp ? new Date(ev.timestamp * 1000).toLocaleTimeString() : 'Now',
                raw: fc
              });
            }
          }

          if (fr) {
            const isFrForAgent = inspectedAgentId === 'root_agent' || isForInspected;
            if (isFrForAgent) {
              items.push({
                id: `fr-${stepNum++}`,
                type: 'response',
                title: `Tool Result: ${fr.name}`,
                desc: typeof fr.response === 'string' ? fr.response.slice(0, 160) + '...' : JSON.stringify(fr.response || {}).slice(0, 160) + '...',
                author: ev.author || inspectedAgentId,
                timestamp: ev.timestamp ? new Date(ev.timestamp * 1000).toLocaleTimeString() : 'Now',
                raw: fr
              });
            }
          }

          if (part.text && isForInspected) {
            items.push({
              id: `text-${stepNum++}`,
              type: 'text',
              title: `Agent Response Output`,
              desc: part.text.slice(0, 180) + (part.text.length > 180 ? '...' : ''),
              author: ev.author || inspectedAgentId,
              timestamp: ev.timestamp ? new Date(ev.timestamp * 1000).toLocaleTimeString() : 'Now',
              raw: part.text
            });
          }
        }
      }
    }
    return items.reverse(); // Newest first
  });

  function isAgentRunning(agentId) {
    if (!isLoading) return false;
    const cleanCurrent = (currentExecutingAgent || selectedApp || '').toLowerCase();
    return cleanCurrent.includes(agentId) || (agentId === 'root_agent' && (cleanCurrent === 'root' || cleanCurrent === 'root_agent'));
  }

  function isAgentParticipated(agentId) {
    return participatedAgentIds.includes(agentId);
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
          <Workflow size={20} />
        </div>
        <div>
          <div class="header-title-row">
            <h3>Multi-Agent Architecture</h3>
            <span class="active-badge-counter">{AGENTS_META.length} Active Nodes</span>
          </div>
          <span class="header-sub">Google ADK 2.0 Network &bull; Live Agent-to-Agent (A2A) Protocols</span>
        </div>
      </div>

      <div class="header-actions">
        {#if isLoading}
          {@const runningAgent = AGENTS_META.find(a => isAgentRunning(a.id)) || AGENTS_META[0]}
          <div class="live-pulse-badge" style="border-color: {runningAgent.color}; color: {runningAgent.color}">
            <span class="pulse-dot" style="background: {runningAgent.color}"></span>
            <span>Running: {runningAgent.name}</span>
          </div>
        {:else}
          <div class="idle-badge">
            <span class="idle-dot"></span>
            <span>Network Standby ({events.length} Telemetry Events)</span>
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
        <!-- Background Grid Effect -->
        <div class="canvas-grid-pattern"></div>

        <!-- SVG Connection Lines Layer with Animated Packets -->
        <svg class="graph-svg-layer" viewBox="0 0 100 100" preserveAspectRatio="none">
          <defs>
            {#each AGENTS_META as agent}
              <filter id="glow-{agent.id}" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="0.8" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            {/each}
          </defs>

          <!-- Edges from Root (50, 50) to all sub-agents -->
          {#each AGENTS_META as agent}
            {#if !agent.isRoot}
              {@const isRunning = isAgentRunning(agent.id)}
              {@const isParticipated = isAgentParticipated(agent.id)}
              {@const isSelected = inspectedAgentId === agent.id}

              <!-- Base / Background Edge Line -->
              <line 
                x1="50" 
                y1="50" 
                x2={agent.x} 
                y2={agent.y} 
                class="graph-edge-line" 
                class:edge-running={isRunning}
                class:edge-participated={isParticipated}
                class:edge-selected={isSelected}
                class:edge-a2a={agent.isA2A}
                style="--edge-color: {agent.color};"
              />

              <!-- Flowing Packet Animation on Active / Participated Edges -->
              {#if isRunning || (isLoading && isParticipated)}
                <!-- Outer Glow Packet -->
                <circle r="1.4" fill={agent.color} filter="url(#glow-{agent.id})">
                  <animateMotion 
                    path="M 50 50 L {agent.x} {agent.y}" 
                    dur={isRunning ? "0.9s" : "2.2s"} 
                    repeatCount="indefinite" 
                  />
                </circle>
                <!-- Core White Particle -->
                <circle r="0.8" fill="#FFFFFF">
                  <animateMotion 
                    path="M 50 50 L {agent.x} {agent.y}" 
                    dur={isRunning ? "0.9s" : "2.2s"} 
                    repeatCount="indefinite" 
                  />
                </circle>
              {/if}
            {/if}
          {/each}
        </svg>

        <!-- Floating Protocol Chips on Canvas Midpoints (A2A edges) -->
        {#each AGENTS_META as agent}
          {#if !agent.isRoot && agent.isA2A}
            {@const isRunning = isAgentRunning(agent.id)}
            {@const isParticipated = isAgentParticipated(agent.id)}
            {@const midX = (50 + agent.x) / 2}
            {@const midY = (50 + agent.y) / 2}

            <div 
              class="edge-protocol-chip chip-a2a"
              class:chip-active={isRunning || isParticipated}
              style="left: {midX}%; top: {midY}%; --chip-color: {agent.color}"
            >
              <Zap size={9} />
              <span>A2A ⚡</span>
            </div>
          {/if}
        {/each}

        <!-- HTML Interactive Nodes Layer -->
        <div class="graph-nodes-layer">
          {#each AGENTS_META as agent}
            {@const isRunning = isAgentRunning(agent.id)}
            {@const isParticipated = isAgentParticipated(agent.id)}
            {@const isSelected = inspectedAgentId === agent.id}
            {@const Icon = agent.icon}

            <button 
              class="agent-node-card" 
              class:node-root={agent.isRoot}
              class:node-running={isRunning}
              class:node-participated={isParticipated && !isRunning}
              class:node-selected={isSelected}
              style="left: {agent.x}%; top: {agent.y}%; --node-color: {agent.color}; --node-bg: {agent.bg};"
              onclick={() => handleSelect(agent.id)}
            >
              <!-- Pulsing Aura for active running agent -->
              {#if isRunning}
                <div class="node-pulse-aura" style="background: {agent.color}"></div>
              {/if}

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

              {#if isRunning}
                <div class="active-badge-tag running-badge" style="background: {agent.color}">
                  <Activity size={10} class="spin-icon" />
                  <span>RUNNING</span>
                </div>
              {:else if isParticipated && !agent.isRoot}
                <div class="active-badge-tag active-history-badge">
                  <CheckCircle2 size={9} />
                  <span>READY</span>
                </div>
              {/if}
            </button>
          {/each}
        </div>
      </div>

      <!-- Right: Live Telemetry & Inspector Drawer -->
      <aside class="agent-inspector-panel">
        <!-- Inspector Agent Header -->
        <div class="inspector-header" style="border-left: 4px solid {inspectedAgent.color}">
          <div class="inspector-title-row">
            <div class="inspector-icon-wrap" style="background: {inspectedAgent.bg}; color: {inspectedAgent.color}">
              <inspectedAgent.icon size={20} />
            </div>
            <div>
              <h4>{inspectedAgent.name}</h4>
              <div class="inspector-meta-sub">
                <span class="protocol-chip">{inspectedAgent.protocol}</span>
                {#if isAgentRunning(inspectedAgent.id)}
                  <span class="live-status-pill running">⚡ ACTIVE NOW</span>
                {:else if isAgentParticipated(inspectedAgent.id)}
                  <span class="live-status-pill ready">✓ PARTICIPATED</span>
                {:else}
                  <span class="live-status-pill standby">STANDBY</span>
                {/if}
              </div>
            </div>
          </div>

          <div class="inspector-model-badge">
            <Cpu size={13} />
            <span>{inspectedAgent.model}</span>
          </div>
        </div>

        <!-- Inspector Tabs -->
        <div class="inspector-tabs">
          <button 
            class="tab-btn" 
            class:active={activeTab === 'telemetry'}
            onclick={() => activeTab = 'telemetry'}
          >
            <Radio size={13} />
            <span>Live Telemetry</span>
            <span class="tab-badge">{agentTelemetryItems.length}</span>
          </button>
          <button 
            class="tab-btn" 
            class:active={activeTab === 'spec'}
            onclick={() => activeTab = 'spec'}
          >
            <FileCode2 size={13} />
            <span>Capabilities & Tools</span>
          </button>
        </div>

        <!-- Tab 1: Live Event Stream & Tool Call Trace -->
        {#if activeTab === 'telemetry'}
          <div class="inspector-body telemetry-scroll-pane">
            {#if agentTelemetryItems.length === 0}
              <div class="empty-telemetry">
                <Clock3 size={24} />
                <p>No active execution events in current session for <strong>{inspectedAgent.name}</strong>.</p>
                <span class="empty-hint">Send a message or delegate a task to see live A2A and ADK telemetry events.</span>
              </div>
            {:else}
              <div class="telemetry-stream-list">
                {#each agentTelemetryItems as item (item.id)}
                  <div class="telemetry-card type-{item.type}">
                    <div class="telemetry-card-top">
                      <div class="card-type-badge">
                        {#if item.type === 'call'}
                          <Zap size={11} />
                        {:else if item.type === 'response'}
                          <CheckCircle2 size={11} />
                        {:else if item.type === 'transfer'}
                          <ArrowUpRight size={11} />
                        {:else}
                          <Sparkles size={11} />
                        {/if}
                        <span>{item.title}</span>
                      </div>
                      <span class="telemetry-time">{item.timestamp}</span>
                    </div>
                    <div class="telemetry-card-desc">{item.desc}</div>
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        {:else}
          <!-- Tab 2: Capabilities & Registered Tools -->
          <div class="inspector-body">
            <div class="inspector-section">
              <span class="section-label">Overview & Purpose</span>
              <p class="section-desc">{inspectedAgentDetails?.summary || inspectedAgent.desc}</p>
            </div>

            {#if inspectedAgentDetails?.whenToUse || inspectedAgentDetails?.keyCapabilities}
              {@const list = inspectedAgentDetails.whenToUse || inspectedAgentDetails.keyCapabilities}
              <div class="inspector-section">
                <span class="section-label">When to Use ({list.length})</span>
                <div class="capabilities-list-compact">
                  {#each list as cap}
                    <div class="cap-item-compact">
                      <CheckCircle2 size={12} class="cap-check-icon" style="color: {inspectedAgent.color};" />
                      <span>{cap}</span>
                    </div>
                  {/each}
                </div>
              </div>
            {/if}

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

            {#if inspectedAgentDetails?.outputDeliverables}
              <div class="inspector-section">
                <span class="section-label">Primary Deliverable</span>
                <div class="deliverable-card-compact">
                  <FileText size={12} class="deliverable-icon-compact" />
                  <span>{inspectedAgentDetails.outputDeliverables}</span>
                </div>
              </div>
            {/if}

            {#if inspectedAgent.port}
              <div class="inspector-section">
                <span class="section-label">Service Port & Endpoints</span>
                <div class="endpoint-card">
                  <span class="port-label">Port {inspectedAgent.port}</span>
                  {#if inspectedAgent.isA2A}
                    <span class="agent-card-link">/.well-known/agent-card.json</span>
                  {:else}
                    <span class="agent-card-link">In-Process Sub-Agent</span>
                  {/if}
                </div>
              </div>
            {/if}
          </div>
        {/if}

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
    background: rgba(0, 0, 0, 0.78);
    backdrop-filter: blur(10px);
    z-index: 100;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
    animation: fadeIn 0.2s ease-out;
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: scale(0.98); }
    to { opacity: 1; transform: scale(1); }
  }

  .agent-graph-modal {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    width: 95vw;
    max-width: 1240px;
    height: 86vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: 0 24px 64px rgba(0, 0, 0, 0.6);
  }

  /* Header */
  .graph-modal-header {
    height: 64px;
    padding: 0 24px;
    border-bottom: 1px solid var(--border-subtle);
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: var(--bg-surface-elevated);
  }

  .header-title-group {
    display: flex;
    align-items: center;
    gap: 14px;
  }

  .graph-header-icon {
    width: 36px;
    height: 36px;
    border-radius: var(--radius-sm);
    background: rgba(56, 189, 248, 0.15);
    color: #38BDF8;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .header-title-row {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .header-title-group h3 {
    font-size: var(--font-size-title-md);
    font-weight: 700;
    color: var(--text-primary);
    margin: 0;
  }

  .active-badge-counter {
    font-size: 11px;
    font-weight: 700;
    background: rgba(56, 189, 248, 0.15);
    color: #38BDF8;
    padding: 2px 8px;
    border-radius: var(--radius-pill);
  }

  .header-sub {
    font-size: var(--font-size-label);
    color: var(--text-tertiary);
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 14px;
  }

  .live-pulse-badge {
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(56, 189, 248, 0.12);
    border: 1px solid;
    padding: 6px 12px;
    border-radius: var(--radius-pill);
    font-size: var(--font-size-label);
    font-weight: 700;
    animation: badge-glow 1.5s infinite alternate;
  }

  @keyframes badge-glow {
    from { opacity: 0.85; }
    to { opacity: 1; filter: drop-shadow(0 0 6px currentColor); }
  }

  .idle-badge {
    display: flex;
    align-items: center;
    gap: 8px;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    color: var(--text-secondary);
    padding: 5px 12px;
    border-radius: var(--radius-pill);
    font-size: var(--font-size-label);
    font-weight: 600;
  }

  .pulse-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    animation: pulse 1s infinite alternate;
  }

  .idle-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #10B981;
  }

  @keyframes pulse {
    0% { transform: scale(0.8); opacity: 0.5; }
    100% { transform: scale(1.3); opacity: 1; }
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
    transition: all 0.15s ease;
  }

  .close-btn:hover {
    background: var(--bg-surface-variant);
    color: var(--text-primary);
  }

  /* Body Layout */
  .graph-body-layout {
    flex: 1;
    display: grid;
    grid-template-columns: 1fr 380px;
    overflow: hidden;
  }

  /* Canvas */
  .graph-canvas-container {
    position: relative;
    background: radial-gradient(circle at 50% 50%, rgba(56, 189, 248, 0.05) 0%, transparent 70%), var(--bg-app);
    overflow: hidden;
  }

  .canvas-grid-pattern {
    position: absolute;
    inset: 0;
    background-image: linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px),
                      linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
    background-size: 32px 32px;
    pointer-events: none;
  }

  .graph-svg-layer {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
  }

  .graph-edge-line {
    stroke: rgba(255, 255, 255, 0.12);
    stroke-width: 0.35;
    stroke-dasharray: 1 1;
    transition: all 0.3s ease;
  }

  .graph-edge-line.edge-a2a {
    stroke: rgba(192, 132, 252, 0.35);
    stroke-width: 0.45;
    stroke-dasharray: 1.5 1;
  }

  .graph-edge-line.edge-participated {
    stroke: var(--edge-color);
    stroke-opacity: 0.6;
    stroke-width: 0.6;
  }

  .graph-edge-line.edge-running {
    stroke: var(--edge-color);
    stroke-width: 1.0;
    stroke-dasharray: 2 1;
    animation: dash-flow 0.8s linear infinite;
    filter: drop-shadow(0 0 3px var(--edge-color));
  }

  @keyframes dash-flow {
    from { stroke-dashoffset: 6; }
    to { stroke-dashoffset: 0; }
  }

  /* Protocol Chips at Midpoints */
  .edge-protocol-chip {
    position: absolute;
    transform: translate(-50%, -50%);
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    color: var(--text-tertiary);
    font-size: 9px;
    font-weight: 700;
    font-family: var(--font-family-mono);
    padding: 1px 6px;
    border-radius: var(--radius-pill);
    display: flex;
    align-items: center;
    gap: 3px;
    pointer-events: none;
    z-index: 2;
    transition: all 0.3s ease;
  }

  .edge-protocol-chip.chip-a2a {
    background: rgba(192, 132, 252, 0.12);
    border-color: rgba(192, 132, 252, 0.3);
    color: #C084FC;
  }

  .edge-protocol-chip.chip-active {
    background: var(--chip-color);
    color: #121314;
    border-color: var(--chip-color);
    font-weight: 800;
    box-shadow: 0 0 10px var(--chip-color);
  }

  /* Nodes Layer */
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
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: var(--shadow-elevation-1);
    max-width: 220px;
    z-index: 4;
  }

  .agent-node-card:hover {
    transform: translate(-50%, -54%) scale(1.05);
    border-color: var(--node-color);
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4), 0 0 12px var(--node-color);
    z-index: 10;
  }

  .agent-node-card.node-root {
    padding: 12px 16px;
    border-width: 2px;
    border-color: #38BDF8;
    box-shadow: 0 0 24px rgba(56, 189, 248, 0.25);
    z-index: 5;
  }

  .agent-node-card.node-selected {
    border-color: var(--node-color);
    background: var(--bg-surface-elevated);
    box-shadow: 0 0 14px var(--node-color);
  }

  .agent-node-card.node-participated {
    border-color: var(--node-color);
    box-shadow: 0 0 8px rgba(255, 255, 255, 0.1);
  }

  .agent-node-card.node-running {
    border-color: var(--node-color);
    box-shadow: 0 0 24px var(--node-color);
    animation: active-node-pulse 1.4s infinite ease-in-out;
  }

  .node-pulse-aura {
    position: absolute;
    inset: -6px;
    border-radius: var(--radius-md);
    opacity: 0.3;
    animation: aura-expand 1.4s infinite ease-out;
    pointer-events: none;
  }

  @keyframes aura-expand {
    0% { transform: scale(0.95); opacity: 0.5; }
    100% { transform: scale(1.15); opacity: 0; }
  }

  @keyframes active-node-pulse {
    0%, 100% { box-shadow: 0 0 10px var(--node-color); }
    50% { box-shadow: 0 0 28px var(--node-color); }
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
    font-weight: 800;
    background: rgba(192, 132, 252, 0.2);
    color: #C084FC;
    padding: 1px 4px;
    border-radius: var(--radius-pill);
  }

  .active-badge-tag {
    position: absolute;
    top: -8px;
    right: -8px;
    font-size: 9px;
    font-weight: 800;
    padding: 2px 6px;
    border-radius: var(--radius-pill);
    display: flex;
    align-items: center;
    gap: 3px;
    z-index: 10;
  }

  .running-badge {
    color: #121314;
    box-shadow: 0 0 10px var(--node-color);
  }

  .active-history-badge {
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-medium);
    color: var(--text-secondary);
  }

  :global(.spin-icon) {
    animation: spin 2s linear infinite;
  }

  @keyframes spin {
    100% { transform: rotate(360deg); }
  }

  /* Inspector Panel */
  .agent-inspector-panel {
    background: var(--bg-surface-elevated);
    border-left: 1px solid var(--border-subtle);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .inspector-header {
    padding: 16px 20px;
    background: var(--bg-surface);
    border-bottom: 1px solid var(--border-subtle);
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .inspector-title-row {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .inspector-icon-wrap {
    width: 38px;
    height: 38px;
    border-radius: var(--radius-sm);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .inspector-title-row h4 {
    font-size: var(--font-size-body-md);
    font-weight: 700;
    color: var(--text-primary);
    margin: 0 0 3px 0;
  }

  .inspector-meta-sub {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .protocol-chip {
    font-size: 10px;
    color: var(--text-tertiary);
  }

  .live-status-pill {
    font-size: 9px;
    font-weight: 800;
    padding: 1px 5px;
    border-radius: var(--radius-pill);
  }

  .live-status-pill.running {
    background: rgba(56, 189, 248, 0.2);
    color: #38BDF8;
  }

  .live-status-pill.ready {
    background: rgba(16, 185, 129, 0.15);
    color: #10B981;
  }

  .live-status-pill.standby {
    background: rgba(255, 255, 255, 0.06);
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

  /* Inspector Tabs */
  .inspector-tabs {
    display: flex;
    border-bottom: 1px solid var(--border-subtle);
    background: var(--bg-surface);
  }

  .tab-btn {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 10px 12px;
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--text-tertiary);
    font-size: var(--font-size-label);
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .tab-btn:hover {
    color: var(--text-primary);
  }

  .tab-btn.active {
    color: var(--primary-accent);
    border-bottom-color: var(--primary-accent);
    background: var(--bg-surface-elevated);
  }

  .tab-badge {
    font-size: 10px;
    font-weight: 700;
    background: rgba(255, 255, 255, 0.08);
    padding: 1px 6px;
    border-radius: var(--radius-pill);
  }

  .inspector-body {
    padding: 16px 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    flex: 1;
    overflow-y: auto;
  }

  .telemetry-scroll-pane {
    padding: 12px;
  }

  .empty-telemetry {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 40px 16px;
    gap: 10px;
    color: var(--text-tertiary);
  }

  .empty-telemetry p {
    font-size: var(--font-size-body-sm);
    margin: 0;
    color: var(--text-secondary);
  }

  .empty-hint {
    font-size: var(--font-size-label);
    color: var(--text-tertiary);
  }

  .telemetry-stream-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .telemetry-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 8px 10px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    animation: fadeIn 0.2s ease-out;
  }

  .telemetry-card.type-transfer {
    border-left: 3px solid #38BDF8;
  }

  .telemetry-card.type-call {
    border-left: 3px solid #C084FC;
  }

  .telemetry-card.type-response {
    border-left: 3px solid #10B981;
  }

  .telemetry-card.type-text {
    border-left: 3px solid #FB923C;
  }

  .telemetry-card-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .card-type-badge {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    font-weight: 700;
    color: var(--text-primary);
  }

  .telemetry-time {
    font-family: var(--font-family-mono);
    font-size: 10px;
    color: var(--text-tertiary);
  }

  .telemetry-card-desc {
    font-family: var(--font-family-mono);
    font-size: 11px;
    color: var(--text-secondary);
    line-height: 1.4;
    word-break: break-all;
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

  .capabilities-list-compact {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .cap-item-compact {
    display: flex;
    align-items: flex-start;
    gap: 6px;
    font-size: 11.5px;
    color: var(--text-secondary);
    line-height: 1.4;
  }

  .cap-item-compact :global(.cap-check-icon) {
    flex-shrink: 0;
    margin-top: 2px;
  }

  .deliverable-card-compact {
    display: flex;
    align-items: center;
    gap: 6px;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    padding: 6px 10px;
    border-radius: var(--radius-xs);
    font-size: 11.5px;
    color: var(--text-secondary);
  }

  .deliverable-card-compact :global(.deliverable-icon-compact) {
    color: var(--primary-accent);
    flex-shrink: 0;
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
    padding: 14px 20px;
    border-top: 1px solid var(--border-subtle);
    background: var(--bg-surface);
  }

  .switch-agent-btn {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 9px 14px;
    border-radius: var(--radius-pill);
    border: none;
    color: #121314;
    font-weight: 700;
    font-size: var(--font-size-body-sm);
    cursor: pointer;
    transition: opacity 0.15s ease;
  }

  .switch-agent-btn:hover {
    opacity: 0.9;
  }
</style>
