<script>
  import { onMount } from "svelte";
  import {
    Sparkles,
    History,
    Paperclip,
    Sun,
    Moon,
    ChevronDown,
    HelpCircle,
    ArrowRight,
    Receipt,
    Video,
    Share2,
    Users,
    Calendar,
    Clock,
    Mail,
    Workflow,
    Layers,
    AlertCircle,
    Plus,
    Settings,
    MoreVertical,
    X,
  } from "@lucide/svelte";

  import AgentGraph from "./lib/AgentGraph.svelte";
  import Sidebar from "./lib/Sidebar.svelte";
  import ChatMessage from "./lib/ChatMessage.svelte";
  import ChatInput from "./lib/ChatInput.svelte";
  import SettingsModal from "./lib/SettingsModal.svelte";

  import {
    DEFAULT_APPS,
    STATUS_TICKERS,
    getAgentTheme,
    isIntermediateEvent,
    getAppConfig,
    saveAppConfig,
  } from "./lib/constants.js";

  import {
    fetchApps,
    fetchSessions,
    createSession,
    fetchSessionHistory,
    deleteSessionRequest,
    runSSEStream,
  } from "./lib/api.js";

  // State Variables
  let apps = $state.raw(DEFAULT_APPS);
  let selectedApp = $state("root_agent");
  let userId = $state("user");
  let sessions = $state.raw([]);
  let selectedSessionId = $state("");
  let events = $state.raw([]);
  let queryText = $state("");
  let isLoading = $state(false);
  let errorMsg = $state("");
  let isDarkMode = $state(true);
  let studioConfig = $state(getAppConfig());

  // Layout Panels & Drawers
  let showSessions = $state(false);
  let showLegend = $state(false);
  let showAgentGraph = $state(false);
  let showSettings = $state(false);
  let showMoreMenu = $state(false);

  // Staged files & Drag State
  let isDragging = $state(false);
  let stagedFiles = $state([]);
  let textareaElement = $state();

  let statusText = $state("Orchestrating agents...");
  let statusInterval;
  let currentExecutingAgent = $state("root_agent");
  let chatBodyElement = $state();
  let dragCounter = 0;

  const activeAgentTheme = $derived(getAgentTheme(selectedApp));
  const filteredEvents = $derived(
    events.filter((e) => !isIntermediateEvent(e)),
  );

  // Theme Toggler
  function toggleTheme() {
    isDarkMode = !isDarkMode;
    if (isDarkMode) {
      document.documentElement.classList.add("dark");
      document.documentElement.setAttribute("data-theme", "dark");
    } else {
      document.documentElement.classList.remove("dark");
      document.documentElement.setAttribute("data-theme", "light");
    }
  }

  // Load Apps
  async function loadApps() {
    apps = await fetchApps();
    await loadSessions();
  }

  // Load Sessions
  async function loadSessions() {
    if (!selectedApp) return;
    try {
      errorMsg = "";
      sessions = await fetchSessions(selectedApp, userId);
      if (sessions.length > 0) {
        if (
          !selectedSessionId ||
          !sessions.some((s) => s.session_id === selectedSessionId)
        ) {
          selectSession(sessions[0].session_id);
        }
      } else {
        selectedSessionId = "";
        events = [];
      }
    } catch (e) {
      console.error(e);
      errorMsg = `Failed to load sessions: ${e.message}`;
    }
  }

  // Start New Session
  async function startNewSession() {
    if (!selectedApp) return;
    const newSessionId = `session_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
    try {
      errorMsg = "";
      isLoading = true;
      await createSession(selectedApp, userId, newSessionId);
      await loadSessions();
      selectSession(newSessionId);
    } catch (e) {
      console.error(e);
      errorMsg = `Failed to start session: ${e.message}`;
    } finally {
      isLoading = false;
    }
  }

  // Select Existing Session
  async function selectSession(sessionId) {
    selectedSessionId = sessionId;
    if (!selectedSessionId) {
      events = [];
      return;
    }
    try {
      errorMsg = "";
      events = await fetchSessionHistory(
        selectedApp,
        userId,
        selectedSessionId,
      );
      scrollToBottom();
    } catch (e) {
      console.error(e);
      errorMsg = `Failed to load session history: ${e.message}`;
    }
  }

  // Delete Session
  async function deleteSession(sessionId) {
    if (
      !confirm("Are you sure you want to delete this session and its history?")
    )
      return;
    try {
      errorMsg = "";
      await deleteSessionRequest(selectedApp, userId, sessionId);
      if (selectedSessionId === sessionId) {
        selectedSessionId = "";
        events = [];
      }
      await loadSessions();
    } catch (e) {
      console.error(e);
      errorMsg = `Failed to delete session: ${e.message}`;
    }
  }

  // Drag & Drop handlers
  function handleDragEnter(e) {
    e.preventDefault();
    dragCounter++;
    isDragging = true;
  }

  function handleDragOver(e) {
    e.preventDefault();
    if (!isDragging) isDragging = true;
  }

  function handleDragLeave(e) {
    e.preventDefault();
    dragCounter--;
    if (dragCounter <= 0) {
      dragCounter = 0;
      isDragging = false;
    }
  }

  function handleDrop(e) {
    e.preventDefault();
    dragCounter = 0;
    isDragging = false;
    const files = e.dataTransfer ? e.dataTransfer.files : null;
    if (files && files.length > 0) {
      Array.from(files).forEach((file) => {
        const isImage = file.type.startsWith("image/");
        const reader = new FileReader();
        reader.onload = (evt) => {
          const dataUrl = evt.target.result;
          const base64Data = dataUrl.split(",")[1];
          stagedFiles = [
            ...stagedFiles,
            {
              name: file.name,
              type: file.type || "application/octet-stream",
              data: base64Data,
              preview: isImage ? dataUrl : null,
            },
          ];
        };
        reader.readAsDataURL(file);
      });
    }
  }

  // Ticker for agent statuses
  function startStatusTicker(app) {
    const list = STATUS_TICKERS[app] || [
      "Processing request...",
      "Executing agent logic...",
      "Invoking external tool pipeline...",
    ];
    let idx = 0;
    statusText = list[0];
    clearInterval(statusInterval);
    statusInterval = setInterval(() => {
      idx = (idx + 1) % list.length;
      statusText = list[idx];
    }, 2200);
  }

  function scrollToBottom() {
    setTimeout(() => {
      if (chatBodyElement) {
        chatBodyElement.scrollTo({
          top: chatBodyElement.scrollHeight,
          behavior: "smooth",
        });
      }
    }, 50);
  }

  function refineVariant(bodyText) {
    const cleanBody = bodyText.trim();
    const quoted = cleanBody
      .split("\n")
      .map((l) => `> ${l}`)
      .join("\n");
    queryText = `Please refine the following option:\n\n${quoted}\n\nMy adjustments:\n`;
    setTimeout(() => {
      if (textareaElement) {
        textareaElement.style.height = "auto";
        textareaElement.style.height = textareaElement.scrollHeight + "px";
        textareaElement.focus();
      }
    }, 50);
  }

  let isSubmitting = false;

  // Send Message / Run Agent
  async function sendMessage() {
    if (isLoading || isSubmitting) return;
    if (!queryText.trim() && stagedFiles.length === 0) return;

    isSubmitting = true;
    isLoading = true;

    if (!selectedSessionId) {
      const newSessionId = `session_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
      try {
        await createSession(selectedApp, userId, newSessionId);
        selectedSessionId = newSessionId;
        loadSessions();
      } catch (err) {
        selectedSessionId = newSessionId;
      }
    }

    const currentText = queryText;
    const currentFiles = [...stagedFiles];

    queryText = "";
    if (textareaElement) {
      textareaElement.style.height = "auto";
    }
    stagedFiles = [];
    errorMsg = "";
    currentExecutingAgent = selectedApp || "root_agent";
    startStatusTicker(selectedApp);

    try {
      const parts = [];
      currentFiles.forEach((f) => {
        parts.push({
          inline_data: {
            mime_type: f.type,
            data: f.data,
          },
        });
      });
      if (currentText.trim()) {
        parts.push({ text: currentText });
      }

      // Add user message to events list
      events = [
        ...events,
        {
          author: "user",
          content: { parts: parts },
          timestamp: Date.now() / 1000,
        },
      ];
      scrollToBottom();

      await runSSEStream({
        appName: selectedApp,
        userId,
        sessionId: selectedSessionId,
        parts,
        onEvent: (eventObj) => {
          if (!eventObj) return;

          if (eventObj.author && eventObj.author !== "user") {
            currentExecutingAgent = eventObj.author;
            startStatusTicker(currentExecutingAgent);
          }

          const existingIdx = eventObj.id
            ? events.findIndex((e) => e.id === eventObj.id)
            : -1;

          if (existingIdx !== -1) {
            // Existing event with same ID
            const existingEv = events[existingIdx];
            const updatedEvents = [...events];

            if (eventObj.partial === false) {
              // Final complete event emitted by ADK: replace with final consolidated payload
              updatedEvents[existingIdx] = eventObj;
            } else {
              // Partial stream chunk: append text deltas
              const newText = eventObj.content?.parts?.[0]?.text || "";
              const prevText = existingEv.content?.parts?.[0]?.text || "";
              updatedEvents[existingIdx] = {
                ...eventObj,
                content: {
                  ...eventObj.content,
                  parts: [
                    {
                      ...(eventObj.content?.parts?.[0] || {}),
                      text: prevText + newText,
                    },
                  ],
                },
              };
            }
            events = updatedEvents;
          } else {
            // New event ID or first chunk
            events = [...events, eventObj];
          }
          scrollToBottom();
        },
      });
    } catch (e) {
      console.error(e);
      errorMsg = e.message || "Execution failed";
    } finally {
      isLoading = false;
      isSubmitting = false;
      clearInterval(statusInterval);
      scrollToBottom();
    }
  }

  function updateConfig(newConfig) {
    studioConfig = newConfig;
    saveAppConfig(newConfig);
  }

  onMount(() => {
    document.documentElement.classList.add("dark");
    document.documentElement.setAttribute("data-theme", "dark");
    loadApps();
  });
</script>

<svelte:window
  onkeydown={(e) => {
    if (e.key === "Escape") showMoreMenu = false;
  }}
  onclick={(e) => {
    if (showMoreMenu && !e.target.closest?.(".more-menu-container"))
      showMoreMenu = false;
  }}
/>

<div
  class="studio-layout"
  class:thinking-active={isLoading}
  style="--active-agent-color: {activeAgentTheme.color}"
>
  <!-- =========================================================================
   * TOP APP BAR (Sleek Modern Header)
   * ========================================================================= -->
  <header class="studio-header">
    <div class="header-left">
      <!-- Community Studio Brand Typography (Leftmost) -->
      <button
        class="brand-badge"
        onclick={() => {
          selectedSessionId = "";
          events = [];
        }}
        data-tooltip="Home / Select Agent"
        aria-label="Home / Select Agent"
      >
        <div class="brand-text">
          <span class="brand-name">Community Studio</span>
          <span class="brand-sub"
            >{studioConfig.communityName || "GDG Krakow"}</span
          >
        </div>
      </button>

      <div class="header-divider"></div>

      <!-- New Session Button (With label) -->
      <button
        class="header-btn-new-session"
        onclick={startNewSession}
        disabled={isLoading}
        data-tooltip="Start New Session"
        aria-label="Start New Session"
      >
        <Plus size={15} strokeWidth={2.2} />
        <span>New session</span>
      </button>

      <!-- Sidebar toggle (History) -->
      <button
        class="icon-btn"
        class:active={showSessions}
        onclick={() => (showSessions = !showSessions)}
        data-tooltip="Session History (Sidebar)"
        aria-label="Session History (Sidebar)"
      >
        <History size={18} strokeWidth={1.75} />
      </button>
    </div>

    <div class="header-right">
      <!-- Active Agent Selector with integrated Online dot -->
      <div class="app-picker">
        <span class="picker-label">Agent:</span>
        <div
          class="select-wrapper"
          class:has-session={Boolean(selectedSessionId)}
          class:is-main={selectedApp === "root_agent"}
        >
          {#if selectedSessionId}
            <span
              class="live-status-dot"
              data-tooltip="Session Active • Connected"
              aria-label="Session Active • Connected"
            ></span>
          {:else if selectedApp === "root_agent"}
            <span
              class="main-badge-icon"
              data-tooltip="Main Coordinator"
              aria-label="Main Coordinator"
            >
              <Layers size={12} strokeWidth={2} />
            </span>
          {/if}
          <select
            id="appSelect"
            bind:value={selectedApp}
            onchange={() => {
              selectedSessionId = "";
              loadSessions();
            }}
          >
            {#each apps as app}
              <option value={app.name}>
                {app.root_agent_name || app.name}
              </option>
            {/each}
          </select>
          <ChevronDown size={14} class="select-chevron" />
        </div>
      </div>

      <div class="header-divider"></div>

      <!-- Multi-Agent DAG Architecture -->
      <button
        class="icon-btn"
        class:active={showAgentGraph}
        onclick={() => (showAgentGraph = true)}
        data-tooltip="Multi-Agent DAG Architecture"
        aria-label="Multi-Agent DAG Architecture"
      >
        <Workflow size={18} strokeWidth={1.75} />
      </button>

      <!-- More Options Dropdown Menu (Theme, Capabilities, Settings) -->
      <div class="more-menu-container">
        <button
          class="icon-btn"
          class:active={showMoreMenu}
          onclick={(e) => {
            e.stopPropagation();
            showMoreMenu = !showMoreMenu;
          }}
          data-tooltip="More options"
          aria-label="More options"
        >
          <MoreVertical size={18} strokeWidth={1.75} />
        </button>

        {#if showMoreMenu}
          <div class="dropdown-menu">
            <button
              class="dropdown-item"
              onclick={() => {
                toggleTheme();
                showMoreMenu = false;
              }}
            >
              {#if isDarkMode}
                <Sun size={15} strokeWidth={1.75} class="dropdown-icon" />
                <span>Light Theme</span>
              {:else}
                <Moon size={15} strokeWidth={1.75} class="dropdown-icon" />
                <span>Dark Theme</span>
              {/if}
            </button>

            <button
              class="dropdown-item"
              onclick={() => {
                showLegend = true;
                showMoreMenu = false;
              }}
            >
              <HelpCircle size={15} strokeWidth={1.75} class="dropdown-icon" />
              <span>Capabilities</span>
            </button>

            <button
              class="dropdown-item"
              onclick={() => {
                showSettings = true;
                showMoreMenu = false;
              }}
            >
              <Settings size={15} strokeWidth={1.75} class="dropdown-icon" />
              <span>Settings</span>
            </button>
          </div>
        {/if}
      </div>
    </div>
  </header>

  <div class="studio-body">
    <!-- Left Sidebar -->
    {#if showSessions}
      <Sidebar
        {sessions}
        {selectedSessionId}
        {isLoading}
        onSelectSession={selectSession}
        onNewSession={startNewSession}
        onDeleteSession={deleteSession}
      />
    {/if}

    <!-- Central Workspace -->
    <main
      class="studio-main"
      ondragenter={handleDragEnter}
      ondragover={handleDragOver}
      ondragleave={handleDragLeave}
      ondrop={handleDrop}
    >
      <!-- Drag & Drop Overlay -->
      {#if isDragging}
        <div class="drag-zone-overlay">
          <div class="drag-zone-card">
            <Paperclip size={36} class="drag-icon" />
            <h3>Drop Files for Multimodal Inference</h3>
            <p>
              Accepts receipts, invoice images, portrait photos, spreadsheets,
              and PDFs
            </p>
          </div>
        </div>
      {/if}

      <!-- Global Error Notification Banner -->
      {#if errorMsg}
        <div class="global-error-banner">
          <div class="global-error-content">
            <AlertCircle size={18} class="error-banner-icon" />
            <span class="error-banner-text">{errorMsg}</span>
          </div>
          <button
            class="error-banner-close"
            onclick={() => (errorMsg = "")}
            title="Dismiss error"
          >
            <X size={15} />
          </button>
        </div>
      {/if}

      {#if !selectedSessionId}
        <!-- Welcome Hub View / Main Agents Catalog -->
        <div class="hub-welcome-view">
          <div class="hub-container">
            <div class="hub-header">
              <h1 class="hub-title">Specialized AI Agents</h1>
              <p class="hub-subtitle">
                Select an agent to begin, or use the <strong>Main</strong> agent to automatically coordinate tasks.
              </p>
            </div>

            <!-- Quick 3-Step Guide -->
            <div class="workflow-steps-strip">
              <div class="step-badge">
                <span class="step-num">1</span>
                <span>Select agent or attach docs</span>
              </div>
              <div class="step-separator"></div>
              <div class="step-badge">
                <span class="step-num">2</span>
                <span>Run prompt (Ctrl+Enter)</span>
              </div>
              <div class="step-separator"></div>
              <div class="step-badge">
                <span class="step-num">3</span>
                <span>Inspect tool calls & copy outputs</span>
              </div>
            </div>

            <!-- Agents Catalog Grid -->
            <div class="agents-catalog-grid">
            <button
              class="agent-catalog-card"
              style="--card-accent: var(--agent-root); --card-bg: var(--bg-root);"
              onclick={() => {
                selectedApp = "root_agent";
                startNewSession();
              }}
            >
              <div class="agent-card-header">
                <div class="agent-icon-box">
                  <Layers size={18} strokeWidth={1.75} />
                </div>
                <div class="agent-title-col">
                  <strong>Main</strong>
                  <span class="agent-type-tag">Router & Coordinator</span>
                </div>
              </div>
              <p class="agent-card-desc">
                Parses complex multi-step requests, verifies prerequisites, and
                delegates tasks to sub-agents.
              </p>
              <div class="card-footer-action">
                <span>Start workflow</span>
                <ArrowRight size={14} />
              </div>
            </button>

            <button
              class="agent-catalog-card"
              style="--card-accent: var(--agent-receipt); --card-bg: var(--bg-receipt);"
              onclick={() => {
                selectedApp = "receipt_scanner";
                startNewSession();
              }}
            >
              <div class="agent-card-header">
                <div class="agent-icon-box">
                  <Receipt size={18} strokeWidth={1.75} />
                </div>
                <div class="agent-title-col">
                  <strong>Receipt Scanner</strong>
                  <span class="agent-type-tag">OCR & Financials</span>
                </div>
              </div>
              <p class="agent-card-desc">
                Extracts line items, queries live banking exchange rates, and
                exports formatted expense reports.
              </p>
              <div class="card-footer-action">
                <span>Scan receipts</span>
                <ArrowRight size={14} />
              </div>
            </button>

            <button
              class="agent-catalog-card"
              style="--card-accent: var(--agent-video); --card-bg: var(--bg-video);"
              onclick={() => {
                selectedApp = "video_editor";
                startNewSession();
              }}
            >
              <div class="agent-card-header">
                <div class="agent-icon-box">
                  <Video size={18} strokeWidth={1.75} />
                </div>
                <div class="agent-title-col">
                  <strong>Live Video Editor</strong>
                  <span class="agent-type-tag">Veo & Media AI</span>
                </div>
              </div>
              <p class="agent-card-desc">
                Detects face landmarks, executes 9:16 outpainting, and generates
                cinematic speaker intro videos.
              </p>
              <div class="card-footer-action">
                <span>Generate video</span>
                <ArrowRight size={14} />
              </div>
            </button>

            <button
              class="agent-catalog-card"
              style="--card-accent: var(--agent-linkedin); --card-bg: var(--bg-linkedin);"
              onclick={() => {
                selectedApp = "linkedin_post_generator";
                startNewSession();
              }}
            >
              <div class="agent-card-header">
                <div class="agent-icon-box">
                  <Share2 size={18} strokeWidth={1.75} />
                </div>
                <div class="agent-title-col">
                  <strong>LinkedIn Planner</strong>
                  <span class="agent-type-tag">Copy & Social</span>
                </div>
              </div>
              <p class="agent-card-desc">
                Drafts promotional posts, speaker spotlights, and multi-option
                event recap posts with hashtags.
              </p>
              <div class="card-footer-action">
                <span>Draft post</span>
                <ArrowRight size={14} />
              </div>
            </button>

            <button
              class="agent-catalog-card"
              style="--card-accent: var(--agent-registration); --card-bg: var(--bg-registration);"
              onclick={() => {
                selectedApp = "registration_manager";
                startNewSession();
              }}
            >
              <div class="agent-card-header">
                <div class="agent-icon-box">
                  <Users size={18} strokeWidth={1.75} />
                </div>
                <div class="agent-title-col">
                  <strong>Registrations Manager</strong>
                  <span class="agent-type-tag">Roster & Partitioning</span>
                </div>
              </div>
              <p class="agent-card-desc">
                Cleans participant rosters, deduplicates names, partitions
                confirmed/waitlisted, and writes DOCX files.
              </p>
              <div class="card-footer-action">
                <span>Process roster</span>
                <ArrowRight size={14} />
              </div>
            </button>

            <button
              class="agent-catalog-card"
              style="--card-accent: var(--agent-planner); --card-bg: var(--bg-planner);"
              onclick={() => {
                selectedApp = "event_planner";
                startNewSession();
              }}
            >
              <div class="agent-card-header">
                <div class="agent-icon-box">
                  <Calendar size={18} strokeWidth={1.75} />
                </div>
                <div class="agent-title-col">
                  <strong>Event Scheduler</strong>
                  <span class="agent-type-tag">Calendars & Holidays</span>
                </div>
              </div>
              <p class="agent-card-desc">
                Cross-references Polish holidays, tech calendars, and long
                weekends to avoid meetup collisions.
              </p>
              <div class="card-footer-action">
                <span>Plan dates</span>
                <ArrowRight size={14} />
              </div>
            </button>

            <button
              class="agent-catalog-card"
              style="--card-accent: var(--agent-agenda); --card-bg: var(--bg-agenda);"
              onclick={() => {
                selectedApp = "agenda_generator";
                startNewSession();
              }}
            >
              <div class="agent-card-header">
                <div class="agent-icon-box">
                  <Clock size={18} strokeWidth={1.75} />
                </div>
                <div class="agent-title-col">
                  <strong>Agenda Formatter</strong>
                  <span class="agent-type-tag">Timeline & Schedule</span>
                </div>
              </div>
              <p class="agent-card-desc">
                Calculates minute-level event schedules with networking and
                speaker sessions formatted for easy sharing.
              </p>
              <div class="card-footer-action">
                <span>Format agenda</span>
                <ArrowRight size={14} />
              </div>
            </button>

            <button
              class="agent-catalog-card"
              style="--card-accent: var(--agent-office); --card-bg: var(--bg-office);"
              onclick={() => {
                selectedApp = "office_secretary";
                startNewSession();
              }}
            >
              <div class="agent-card-header">
                <div class="agent-icon-box">
                  <Mail size={18} strokeWidth={1.75} />
                </div>
                <div class="agent-title-col">
                  <strong>Office Secretary</strong>
                  <span class="agent-type-tag">Office & Reservations</span>
                </div>
              </div>
              <p class="agent-card-desc">
                Generates polite visitor key access and room reservation
                requests with strict date validation.
              </p>
              <div class="card-footer-action">
                <span>Draft email</span>
                <ArrowRight size={14} />
              </div>
            </button>
          </div>
        </div>
      </div>
      {:else}
        <!-- Active Chat Message Stream -->
        <div class="chat-viewport" bind:this={chatBodyElement}>
          <div class="chat-stream-container">
            {#each filteredEvents as event, idx}
              <ChatMessage
                {event}
                index={idx}
                allEvents={filteredEvents}
                onRefine={refineVariant}
              />
            {/each}

            {#if isLoading}
              {@const execTheme = getAgentTheme(
                currentExecutingAgent || selectedApp,
              )}
              <div
                class="generating-live-card"
                style="--exec-color: {execTheme.color}; --exec-bg: {execTheme.bg};"
              >
                <div class="generating-header">
                  <div
                    class="executing-agent-badge"
                    style="background: {execTheme.bg}; color: {execTheme.color}; border: 1px solid {execTheme.color}40;"
                  >
                    <span
                      class="live-pulse-dot"
                      style="background: {execTheme.color};"
                    ></span>
                    <span class="executing-agent-label">{execTheme.label}</span>
                  </div>
                  <span class="generating-status">{statusText}</span>
                  <span class="streaming-cursor"></span>
                </div>
                <div class="skeleton-shimmer-group">
                  <div class="skeleton-line" style="width: 85%;"></div>
                  <div class="skeleton-line" style="width: 65%;"></div>
                </div>
              </div>
            {/if}
          </div>
        </div>

        <!-- Floating Prompt Input Bar (only shown in active session) -->
        <ChatInput
          bind:queryText
          bind:stagedFiles
          bind:textareaElement
          {isLoading}
          onSend={sendMessage}
        />
      {/if}
    </main>
  </div>
</div>

<!-- Capabilities Modal -->
{#if showLegend}
  <div
    class="modal-backdrop"
    role="button"
    tabindex="-1"
    onclick={(e) => {
      if (e.target === e.currentTarget) showLegend = false;
    }}
    onkeydown={(e) => {
      if (e.key === "Enter" || e.key === " ") showLegend = false;
    }}
  >
    <div class="modal-card">
      <header class="modal-header">
        <div class="modal-title-group">
          <Sparkles size={20} class="modal-gemini-icon" />
          <h2>Community Studio Multi-Agent System</h2>
        </div>
        <button class="modal-close-btn" onclick={() => (showLegend = false)}
          >&times;</button
        >
      </header>

      <div class="modal-body">
        <p class="modal-intro">
          The Community Studio platform is powered by Google ADK with an A2A
          architecture coordinating specialized reasoning engines for {studioConfig.communityName ||
            "GDG Krakow"}:
        </p>

        <div class="capabilities-grid">
          <div
            class="capability-card"
            style="--card-accent: var(--agent-root); --card-bg: var(--bg-root)"
          >
            <div class="capability-top">
              <div
                class="capability-icon-box"
                style="color: var(--agent-root);"
              >
                <Layers size={16} strokeWidth={1.75} />
              </div>
              <h3>Main</h3>
            </div>
            <p>
              Directs incoming intent, verifies task prerequisites, and invokes
              specialized sub-agents via tool-calling and A2A protocols.
            </p>
          </div>
          <div
            class="capability-card"
            style="--card-accent: var(--agent-receipt); --card-bg: var(--bg-receipt)"
          >
            <div class="capability-top">
              <div
                class="capability-icon-box"
                style="color: var(--agent-receipt);"
              >
                <Receipt size={16} strokeWidth={1.75} />
              </div>
              <h3>Receipt Scanner</h3>
            </div>
            <p>
              Vision OCR analyzer. Extracts line items, VAT, fetches live banking
              exchange rates, and exports formatted expense reports.
            </p>
          </div>
          <div
            class="capability-card"
            style="--card-accent: var(--agent-video); --card-bg: var(--bg-video)"
          >
            <div class="capability-top">
              <div
                class="capability-icon-box"
                style="color: var(--agent-video);"
              >
                <Video size={16} strokeWidth={1.75} />
              </div>
              <h3>Live Video Editor</h3>
            </div>
            <p>
              Speaker portrait outpainting and cinematic video animation
              generation using Veo models.
            </p>
          </div>
          <div
            class="capability-card"
            style="--card-accent: var(--agent-linkedin); --card-bg: var(--bg-linkedin)"
          >
            <div class="capability-top">
              <div
                class="capability-icon-box"
                style="color: var(--agent-linkedin);"
              >
                <Share2 size={16} strokeWidth={1.75} />
              </div>
              <h3>LinkedIn Planner</h3>
            </div>
            <p>
              Generates high-engagement speaker announcements and structured
              multi-option event recap posts.
            </p>
          </div>
          <div
            class="capability-card"
            style="--card-accent: var(--agent-registration); --card-bg: var(--bg-registration)"
          >
            <div class="capability-top">
              <div
                class="capability-icon-box"
                style="color: var(--agent-registration);"
              >
                <Users size={16} strokeWidth={1.75} />
              </div>
              <h3>Registrations Manager</h3>
            </div>
            <p>
              Cleans participant datasets, filters duplicates, normalizes names
              across scripts, and generates clean DOCX files.
            </p>
          </div>
          <div
            class="capability-card"
            style="--card-accent: var(--agent-planner); --card-bg: var(--bg-planner)"
          >
            <div class="capability-top">
              <div
                class="capability-icon-box"
                style="color: var(--agent-planner);"
              >
                <Calendar size={16} strokeWidth={1.75} />
              </div>
              <h3>Event Scheduler</h3>
            </div>
            <p>
              Detects meetup schedule conflicts against Luma and Meetup.com,
              checks statutory Polish holidays, and flags risk dates.
            </p>
          </div>
          <div
            class="capability-card"
            style="--card-accent: var(--agent-agenda); --card-bg: var(--bg-agenda)"
          >
            <div class="capability-top">
              <div
                class="capability-icon-box"
                style="color: var(--agent-agenda);"
              >
                <Clock size={16} strokeWidth={1.75} />
              </div>
              <h3>Agenda Formatter</h3>
            </div>
            <p>
              Computes minute-by-minute meetup schedules with speaker talks,
              networking, and pizza breaks, formatted for copy-pasting.
            </p>
          </div>
          <div
            class="capability-card"
            style="--card-accent: var(--agent-office); --card-bg: var(--bg-office)"
          >
            <div class="capability-top">
              <div
                class="capability-icon-box"
                style="color: var(--agent-office);"
              >
                <Mail size={16} strokeWidth={1.75} />
              </div>
              <h3>Office Secretary</h3>
            </div>
            <p>
              Drafts polite visitor keys access card and Event Hub reservation
              request emails with mandatory date validation.
            </p>
          </div>
        </div>
      </div>

      <footer class="modal-actions">
        <button class="btn-primary" onclick={() => (showLegend = false)}
          >Close</button
        >
      </footer>
    </div>
  </div>
{/if}

<!-- Settings Modal -->
<SettingsModal
  show={showSettings}
  config={studioConfig}
  onSave={updateConfig}
  onClose={() => (showSettings = false)}
/>

<!-- Multi-Agent DAG Modal -->
{#if showAgentGraph}
  <AgentGraph
    {events}
    {currentExecutingAgent}
    {isLoading}
    {selectedApp}
    onSelectAgent={(agentId) => {
      selectedApp = agentId;
      selectedSessionId = "";
      loadSessions();
    }}
    onClose={() => (showAgentGraph = false)}
  />
{/if}

<style>
  .studio-layout {
    display: flex;
    flex-direction: column;
    height: 100vh;
    width: 100vw;
    background-color: var(--bg-app);
    color: var(--text-primary);
    overflow: hidden;
  }

  .studio-header {
    height: 56px;
    background: var(--bg-surface);
    border-bottom: 1px solid var(--border-subtle);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 16px;
    z-index: 50;
  }

  .header-left,
  .header-right {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .brand-badge {
    display: flex;
    align-items: center;
    padding: 4px 8px;
    user-select: none;
    background: transparent;
    border: 1px solid transparent;
    border-radius: var(--radius-md);
    cursor: pointer;
    text-align: left;
    transition: var(--transition-fast);
  }

  .brand-badge:hover {
    background: var(--bg-surface-elevated);
    border-color: var(--border-subtle);
  }

  .brand-text {
    display: flex;
    flex-direction: column;
  }

  .brand-name {
    font-size: 14px;
    font-weight: 700;
    letter-spacing: -0.01em;
    color: var(--text-primary);
    line-height: 1.2;
  }

  .brand-sub {
    font-size: 9.5px;
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
  }

  .header-btn-new-session {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    color: var(--text-primary);
    padding: 6px 12px;
    border-radius: var(--radius-pill);
    font-size: 12.5px;
    font-weight: 600;
    cursor: pointer;
    transition: var(--transition-fast);
  }

  .header-btn-new-session:hover:not(:disabled) {
    background: var(--primary-accent-container);
    border-color: var(--primary-accent);
    color: var(--primary-accent);
  }

  .header-btn-new-session:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .header-divider {
    width: 1px;
    height: 20px;
    background: var(--border-subtle);
    margin: 0 2px;
  }

  .app-picker {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .picker-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-tertiary);
  }

  .select-wrapper {
    position: relative;
    display: flex;
    align-items: center;
  }

  .select-wrapper select {
    appearance: none;
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    color: var(--text-primary);
    padding: 6px 30px 6px 14px;
    border-radius: var(--radius-pill);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    outline: none;
    transition: var(--transition-fast);
  }

  .select-wrapper.has-session select {
    padding-left: 24px;
  }

  .select-wrapper.is-main select {
    padding-left: 28px;
  }

  .select-wrapper select:hover {
    border-color: var(--primary-accent);
  }

  .main-badge-icon {
    position: absolute;
    left: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--primary-accent);
    pointer-events: none;
    z-index: 2;
  }

  .live-status-dot {
    position: absolute;
    left: 10px;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--accent-green, #34a853);
    box-shadow: 0 0 6px var(--accent-green, #34a853);
    pointer-events: none;
    z-index: 2;
    animation: pulseGlow 1.8s infinite ease-in-out;
  }

  :global(.select-chevron) {
    position: absolute;
    right: 10px;
    pointer-events: none;
    color: var(--text-tertiary);
  }

  /* More Options Menu */
  .more-menu-container {
    position: relative;
    display: flex;
    align-items: center;
  }

  .dropdown-menu {
    position: absolute;
    top: calc(100% + 8px);
    right: 0;
    min-width: 170px;
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-lg);
    padding: 6px;
    z-index: 100;
    display: flex;
    flex-direction: column;
    gap: 2px;
    animation: fadeInMenu 0.15s cubic-bezier(0.16, 1, 0.3, 1);
  }

  @keyframes fadeInMenu {
    from {
      opacity: 0;
      transform: translateY(-4px) scale(0.98);
    }
    to {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
  }

  .dropdown-item {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 8px 12px;
    border-radius: var(--radius-md);
    background: transparent;
    border: none;
    color: var(--text-primary);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    text-align: left;
    transition: var(--transition-fast);
  }

  .dropdown-item:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
  }

  :global(.dropdown-icon) {
    color: var(--text-secondary);
    flex-shrink: 0;
  }

  .dropdown-item:hover :global(.dropdown-icon) {
    color: var(--primary-accent);
  }

  .icon-btn {
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-pill);
    border: 1px solid transparent;
    background: transparent;
    color: var(--text-secondary);
    cursor: pointer;
    transition: var(--transition-fast);
  }

  .icon-btn:hover {
    background: var(--bg-surface-elevated);
    color: var(--text-primary);
  }

  .icon-btn.active {
    background: var(--primary-accent-container);
    color: var(--primary-accent);
    border-color: var(--primary-accent);
  }

  .studio-body {
    display: flex;
    flex: 1;
    overflow: hidden;
    position: relative;
  }

  .studio-main {
    flex: 1;
    display: flex;
    flex-direction: column;
    height: 100%;
    position: relative;
    overflow: hidden;
    background: var(--bg-app);
  }

  /* Drag & Drop */
  .drag-zone-overlay {
    position: absolute;
    inset: 0;
    background: rgba(11, 12, 14, 0.85);
    backdrop-filter: blur(6px);
    z-index: 100;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 32px;
  }

  .drag-zone-card {
    border: 2px dashed var(--primary-accent);
    background: var(--bg-surface);
    border-radius: var(--radius-xl);
    padding: 48px;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    max-width: 480px;
  }

  :global(.drag-icon) {
    color: var(--primary-accent);
    animation: bounce 1s infinite alternate ease-in-out;
  }

  @keyframes bounce {
    from {
      transform: translateY(0);
    }
    to {
      transform: translateY(-8px);
    }
  }

  /* Global error banner */
  .global-error-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: rgba(234, 67, 53, 0.12);
    border-bottom: 1px solid rgba(234, 67, 53, 0.3);
    padding: 10px 16px;
    color: var(--accent-red, #ea4335);
    font-size: 13px;
    z-index: 30;
  }

  .global-error-content {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .error-banner-close {
    background: none;
    border: none;
    color: var(--accent-red, #ea4335);
    cursor: pointer;
    padding: 2px;
  }

  /* Welcome Hub View / Main Agents Catalog */
  .hub-welcome-view {
    flex: 1;
    overflow-y: auto;
    padding: 32px;
    display: flex;
    flex-direction: column;
    align-items: center;
    max-width: 1060px;
    margin: 0 auto;
    width: 100%;
  }

  .hub-container {
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    margin: auto 0;
  }

  .hub-header {
    text-align: center;
    margin-bottom: 28px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
  }

  .hub-title {
    font-size: 24px;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: var(--text-primary);
    margin: 0;
  }

  .hub-subtitle {
    font-size: 13.5px;
    color: var(--text-secondary);
    max-width: 560px;
    line-height: 1.5;
    margin: 0;
  }

  .hub-subtitle strong {
    color: var(--text-primary);
  }

  .workflow-steps-strip {
    display: flex;
    align-items: center;
    gap: 12px;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    padding: 6px 16px;
    border-radius: var(--radius-full);
    margin-bottom: 24px;
  }

  .step-badge {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--text-secondary);
  }

  .step-num {
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-medium);
    color: var(--text-primary);
    font-size: 10.5px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .step-separator {
    width: 16px;
    height: 1px;
    background: var(--border-subtle);
  }

  .agents-catalog-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 16px;
    width: 100%;
  }

  .agent-catalog-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    padding: 18px;
    display: flex;
    flex-direction: column;
    text-align: left;
    cursor: pointer;
    transition: var(--transition-normal);
    color: inherit;
    position: relative;
  }

  .agent-catalog-card:hover {
    background: var(--bg-surface-elevated);
    border-color: var(--card-accent, var(--primary-accent));
    transform: translateY(-3px);
    box-shadow: 0 8px 24px -4px rgba(0, 0, 0, 0.35), var(--shadow-md);
  }

  .agent-card-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
  }

  .agent-icon-box {
    width: 36px;
    height: 36px;
    border-radius: var(--radius-md);
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--card-accent, var(--text-primary));
    flex-shrink: 0;
    transition: var(--transition-fast);
  }

  .agent-catalog-card:hover .agent-icon-box {
    border-color: var(--card-accent, var(--border-subtle));
    box-shadow: 0 0 12px var(--card-bg, transparent);
  }

  .agent-title-col {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .agent-title-col strong {
    font-size: 14px;
    font-weight: 700;
    color: var(--text-primary);
    line-height: 1.2;
  }

  .agent-type-tag {
    font-size: 10.5px;
    font-weight: 500;
    color: var(--text-tertiary);
    letter-spacing: 0.02em;
  }

  .agent-card-desc {
    font-size: 12.5px;
    color: var(--text-secondary);
    line-height: 1.55;
    margin-bottom: 18px;
    flex: 1;
  }

  .card-footer-action {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 11.5px;
    font-weight: 500;
    color: var(--text-secondary);
    border-top: 1px solid var(--border-subtle);
    padding-top: 12px;
    transition: var(--transition-fast);
  }

  .agent-catalog-card:hover .card-footer-action {
    color: var(--text-primary);
    border-color: var(--border-medium);
  }

  .agent-catalog-card:hover .card-footer-action :global(svg) {
    transform: translateX(3px);
    transition: transform 0.2s ease;
    color: var(--text-primary);
  }

  /* Chat Viewport */
  .chat-viewport {
    flex: 1;
    overflow-y: auto;
    padding: 24px 32px;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .chat-stream-container {
    width: 100%;
    max-width: 900px;
    display: flex;
    flex-direction: column;
  }

  /* Shimmer Generating Live Card */
  .generating-live-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    padding: 14px 18px;
    margin-bottom: 20px;
    width: fit-content;
    max-width: 88%;
    min-width: min(100%, 320px);
    align-self: flex-start;
    animation: fadeIn 0.3s ease-out;
  }

  .generating-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 14px;
  }

  .executing-agent-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 3px 10px;
    border-radius: var(--radius-full);
    font-size: 12px;
    font-weight: 600;
  }

  .live-pulse-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    animation: pulseGlow 1.5s infinite;
  }

  .generating-status {
    font-size: 12px;
    color: var(--text-secondary);
    font-style: italic;
  }

  .streaming-cursor {
    display: inline-block;
    width: 6px;
    height: 14px;
    background: var(--primary-accent);
    animation: blink 0.8s infinite;
  }

  .skeleton-shimmer-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .skeleton-line {
    height: 12px;
    border-radius: var(--radius-xs);
    background: linear-gradient(
      90deg,
      var(--bg-surface-elevated) 25%,
      var(--bg-hover) 50%,
      var(--bg-surface-elevated) 75%
    );
    background-size: 200% 100%;
    animation: shimmer 1.8s infinite;
  }

  @keyframes shimmer {
    0% {
      background-position: 200% 0;
    }
    100% {
      background-position: -200% 0;
    }
  }

  @keyframes blink {
    0%,
    100% {
      opacity: 1;
    }
    50% {
      opacity: 0;
    }
  }

  @keyframes pulseGlow {
    0%,
    100% {
      opacity: 1;
      transform: scale(1);
    }
    50% {
      opacity: 0.4;
      transform: scale(0.85);
    }
  }

  @keyframes fadeIn {
    from {
      opacity: 0;
      transform: translateY(2px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  /* Modals */
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(11, 12, 14, 0.8);
    backdrop-filter: blur(4px);
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
  }

  .modal-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-xl);
    max-width: 720px;
    width: 100%;
    max-height: 85vh;
    display: flex;
    flex-direction: column;
    box-shadow: var(--shadow-lg);
    overflow: hidden;
  }

  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 20px 24px;
    border-bottom: 1px solid var(--border-subtle);
  }

  .modal-title-group {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  :global(.modal-gemini-icon) {
    color: var(--primary-accent);
  }

  .modal-header h2 {
    font-size: 16px;
    font-weight: 700;
    color: var(--text-primary);
  }

  .modal-close-btn {
    background: none;
    border: none;
    color: var(--text-secondary);
    font-size: 20px;
    cursor: pointer;
  }

  .modal-body {
    padding: 24px;
    overflow-y: auto;
  }

  .modal-intro {
    font-size: 13px;
    color: var(--text-secondary);
    margin-bottom: 20px;
    line-height: 1.5;
  }

  .capabilities-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }

  .capability-card {
    background: var(--card-bg, var(--bg-surface-elevated));
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: 14px;
    transition: var(--transition-fast);
  }

  .capability-card:hover {
    border-color: var(--card-accent, var(--primary-accent));
  }

  .capability-top {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
  }

  .capability-icon-box {
    width: 28px;
    height: 28px;
    border-radius: var(--radius-sm);
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .capability-top h3 {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .capability-card p {
    font-size: 11px;
    color: var(--text-secondary);
    line-height: 1.4;
    margin: 0;
  }

  .modal-actions {
    padding: 16px 24px;
    border-top: 1px solid var(--border-subtle);
    display: flex;
    justify-content: flex-end;
  }

  .btn-primary {
    background: var(--primary-gradient, var(--primary-accent));
    color: #ffffff;
    border: none;
    padding: 8px 20px;
    border-radius: var(--radius-full);
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 2px 10px rgba(37, 99, 235, 0.3);
    transition: var(--transition-fast);
  }

  .btn-primary:hover {
    filter: brightness(1.1);
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4);
  }
</style>
