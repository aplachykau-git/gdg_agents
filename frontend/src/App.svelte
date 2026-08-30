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
    FileText,
    Image as ImageIcon,
    FilePenLine,
    ClipboardList,
    MapPin,
    Building2,
    Megaphone,
  } from "@lucide/svelte";

  import AgentGraph from "./lib/AgentGraph.svelte";
  import Sidebar from "./lib/Sidebar.svelte";
  import ChatMessage from "./lib/ChatMessage.svelte";
  import ChatInput from "./lib/ChatInput.svelte";
  import SettingsModal from "./lib/SettingsModal.svelte";
  import CapabilitiesModal from "./lib/CapabilitiesModal.svelte";
  import studioLogo from "./assets/community-ai-studio.png";
  import squareLogo from "./assets/community-ai-studio-logo.png";

  import {
    DEFAULT_APPS,
    STATUS_TICKERS,
    cleanAuthorName,
    getAgentTheme,
    getAgentHeading,
    getAgentDescription,
    getAgentStarterPrompts,
    getAgentIconName,
    isIntermediateEvent,
    getAppConfig,
    saveAppConfig,
    resolveAgentId,
    getActiveAgentFromEvents,
    getEventAgent,
  } from "./lib/constants.js";

  const ICON_MAP = {
    receipt: Receipt,
    video: Video,
    share: Share2,
    users: Users,
    calendar: Calendar,
    clock: Clock,
    mail: Mail,
    layers: Layers,
    megaphone: Megaphone,
    "file-text": FileText,
    image: ImageIcon,
    "file-pen-line": FilePenLine,
    "clipboard-list": ClipboardList,
    "map-pin": MapPin,
    building: Building2,
    sparkles: Sparkles,
  };

  const CATALOG_AGENTS = [
    {
      id: "root_agent",
      name: "Main",
      tag: "Multi-Agent Hub",
      desc: "Coordinates tasks across agents and answers questions for your community events.",
      actionText: "Start workflow",
      icon: Layers,
      accent: "var(--agent-root)",
      bg: "var(--bg-root)",
    },
    {
      id: "receipt_scanner",
      name: "Receipt Scanner",
      tag: "Expenses & Finance",
      desc: "Scans receipts, checks live bank exchange rates, and creates expense reports in Google Drive.",
      actionText: "Scan receipts",
      icon: Receipt,
      accent: "var(--agent-receipt)",
      bg: "var(--bg-receipt)",
    },
    {
      id: "video_editor",
      name: "Live Video Editor",
      tag: "Speaker Video & Media",
      desc: "Turns speaker portrait photos into animated video intros and speaker cards.",
      actionText: "Generate video",
      icon: Video,
      accent: "var(--agent-video)",
      bg: "var(--bg-video)",
    },
    {
      id: "linkedin_post_generator",
      name: "LinkedIn Planner",
      tag: "Social Media & Posts",
      desc: "Writes engaging speaker announcements, event invitations, and post-event recaps with hashtags.",
      actionText: "Draft post",
      icon: Share2,
      accent: "var(--agent-linkedin)",
      bg: "var(--bg-linkedin)",
    },
    {
      id: "registration_manager",
      name: "Registrations Manager",
      tag: "Attendee Rosters",
      desc: "Cleans attendee lists, removes duplicates, and organizes confirmed and waitlisted guests.",
      actionText: "Process roster",
      icon: Users,
      accent: "var(--agent-registration)",
      bg: "var(--bg-registration)",
    },
    {
      id: "event_planner",
      name: "Event Scheduler",
      tag: "Dates & Holidays",
      desc: "Scans meetup calendars and holidays to find the best dates for community events.",
      actionText: "Plan dates",
      icon: Calendar,
      accent: "var(--agent-planner)",
      bg: "var(--bg-planner)",
    },
    {
      id: "agenda_generator",
      name: "Agenda Formatter",
      tag: "Event Agendas",
      desc: "Creates structured event schedules with talks, networking sessions, and break times.",
      actionText: "Format agenda",
      icon: Clock,
      accent: "var(--agent-agenda)",
      bg: "var(--bg-agenda)",
    },
    {
      id: "office_secretary",
      name: "Office Secretary",
      tag: "Office & Access",
      desc: "Prepares building visitor access requests and meeting room reservation emails.",
      actionText: "Draft email",
      icon: Mail,
      accent: "var(--agent-office)",
      bg: "var(--bg-office)",
    },
  ];

  function getAgentIcon(agentId) {
    if (!agentId) return Layers;
    const clean = cleanAuthorName(agentId).toLowerCase();
    const found = CATALOG_AGENTS.find(
      (a) => a.id === agentId || a.id.toLowerCase() === clean
    );
    if (found) return found.icon;
    if (clean.includes("receipt")) return Receipt;
    if (clean.includes("video") || clean.includes("avatar")) return Video;
    if (clean.includes("linkedin")) return Share2;
    if (clean.includes("registration")) return Users;
    if (clean.includes("planner")) return Calendar;
    if (clean.includes("agenda")) return Clock;
    if (clean.includes("office") || clean.includes("secretary")) return Mail;
    return Layers;
  }

  import {
    fetchApps,
    fetchSessions,
    createSession,
    fetchSessionHistory,
    deleteSessionRequest,
    runSSEStream,
  } from "./lib/api.js";
  import {
    auth,
    loginWithGoogle,
    logoutUser,
    onAuthStateChanged,
  } from "./lib/firebase.js";
  import LoginScreen from "./lib/LoginScreen.svelte";
  import { LogOut } from "@lucide/svelte";

  function getOrCreateUserId() {
    if (typeof window === "undefined") return "user";
    let stored = localStorage.getItem("community_studio_user_id");
    if (!stored) {
      stored = "user_" + (typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID().slice(0, 8) : Math.random().toString(36).slice(2, 10));
      localStorage.setItem("community_studio_user_id", stored);
    }
    return stored;
  }

  // State Variables
  let apps = $state.raw(DEFAULT_APPS);
  let selectedApp = $state("root_agent"); // The app namespace currently being browsed
  let sessionOwnerApp = $state("root_agent"); // The top-level agent app hosting the session
  let userId = $state(getOrCreateUserId());
  let sessions = $state.raw([]);
  let selectedSessionId = $state("");
  let events = $state.raw([]);
  let queryText = $state("");
  let isLoading = $state(false);
  let isSubmitting = $state(false);
  let errorMsg = $state("");
  let isDarkMode = $state(true);
  let studioConfig = $state(getAppConfig());
  let currentUser = $state(null);
  let isAuthLoading = $state(true);
  let isLoggingIn = $state(false);
  let authError = $state("");
  let showUserMenu = $state(false);

  // Layout Panels & Drawers
  let showSessions = $state(false);
  let showLegend = $state(false);
  let showAgentGraph = $state(false);
  let showSettings = $state(false);

  // Staged files & Drag State
  let isDragging = $state(false);
  let stagedFiles = $state([]);
  let textareaElement = $state();

  let statusText = $state("Orchestrating agents...");
  let statusInterval;
  let currentExecutingAgent = $state("root_agent");
  let chatBodyElement = $state();
  let dragCounter = 0;

  // Dynamically resolve active agent currently handling the conversation
  const activeAgent = $derived.by(() => {
    if (isLoading && currentExecutingAgent) {
      const resolved = resolveAgentId(currentExecutingAgent, apps);
      if (resolved) return resolved;
    }
    return getActiveAgentFromEvents(
      events,
      currentExecutingAgent || sessionOwnerApp || selectedApp || "root_agent",
      apps,
    );
  });

  const activeAgentTheme = $derived(getAgentTheme(activeAgent));
  const filteredEvents = $derived(
    events.filter((e) => !isIntermediateEvent(e)),
  );

  // Agent selector manual switch
  async function handleAgentChange(newApp) {
    selectedApp = newApp;
    sessionOwnerApp = newApp;
    currentExecutingAgent = newApp;
    errorMsg = "";
    try {
      sessions = await fetchSessions(newApp, userId);
      if (sessions.length > 0) {
        await selectSession(sessions[0].session_id);
      } else {
        await startNewSession(newApp);
      }
    } catch (e) {
      console.warn("Error switching agent:", e);
      await startNewSession(newApp);
    }
  }

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

  // Load Sessions (fetch history for sidebar without navigating away from Home)
  async function loadSessions() {
    if (!selectedApp) return;
    try {
      errorMsg = "";
      sessions = await fetchSessions(selectedApp, userId);
    } catch (e) {
      console.error(e);
      errorMsg = `Failed to load sessions: ${e.message}`;
    }
  }

  // Start New Session
  function getSessionStatePayload() {
    let localSaved = {};
    if (typeof window !== "undefined") {
      try {
        localSaved = JSON.parse(localStorage.getItem("community_studio_config") || "{}");
      } catch (e) {}
    }
    const folderId = studioConfig?.googleDriveFolderId || localSaved.googleDriveFolderId || "";
    const templateId = studioConfig?.googleDocsTemplateId || localSaved.googleDocsTemplateId || "";
    const driveToken = typeof sessionStorage !== "undefined" ? sessionStorage.getItem("google_drive_token") || "" : "";

    return {
      community_name: studioConfig?.communityName || localSaved.communityName || "GDG Krakow",
      google_drive_folder_id: folderId,
      google_docs_template_id: templateId,
      google_drive_access_token: driveToken,
      google_drive_token: driveToken,
      render_4k: studioConfig?.render4k ?? localSaved.render4k ?? true,
      render_gif: studioConfig?.renderGif ?? localSaved.renderGif ?? true,
      generate_avatar: studioConfig?.generateAvatar ?? localSaved.generateAvatar ?? true,
      enable_video_generation: studioConfig?.enableVideoGeneration ?? localSaved.enableVideoGeneration ?? false,
      render4k: studioConfig?.render4k ?? localSaved.render4k ?? true,
      renderGif: studioConfig?.renderGif ?? localSaved.renderGif ?? true,
      generateAvatar: studioConfig?.generateAvatar ?? localSaved.generateAvatar ?? true,
      enableVideoGeneration: studioConfig?.enableVideoGeneration ?? localSaved.enableVideoGeneration ?? false,
    };
  }

  async function startNewSession(agentId = null) {
    const appToUse = agentId || selectedApp || "root_agent";
    selectedApp = appToUse;
    sessionOwnerApp = appToUse;
    currentExecutingAgent = appToUse;
    const newSessionId = `session_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
    selectedSessionId = newSessionId;
    events = [];
    queryText = "";
    stagedFiles = [];
    errorMsg = "";

    try {
      isLoading = true;
      const statePayload = getSessionStatePayload();
      await createSession(appToUse, userId, newSessionId, statePayload);
      const fetched = await fetchSessions(appToUse, userId);
      if (fetched && fetched.length > 0) {
        sessions = fetched;
      } else {
        sessions = [{ id: newSessionId, session_id: newSessionId, state: statePayload, events: [] }];
      }
    } catch (e) {
      console.warn("Session creation notice:", e.message);
      sessions = [{ id: newSessionId, session_id: newSessionId, state: getSessionStatePayload(), events: [] }];
    } finally {
      isLoading = false;
      setTimeout(() => {
        if (textareaElement) textareaElement.focus();
      }, 50);
    }
  }

  function selectStarterPrompt(prompt) {
    const text = typeof prompt === "string" ? prompt : (prompt?.prompt || prompt?.text || "");
    queryText = text;
    setTimeout(() => {
      if (textareaElement) {
        textareaElement.style.height = "auto";
        textareaElement.style.height = textareaElement.scrollHeight + "px";
        textareaElement.focus();
      }
    }, 50);
  }

  async function startNewSessionWithPrompt(targetApp, prompt) {
    await startNewSession(targetApp);
    if (prompt) {
      selectStarterPrompt(prompt);
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
      sessionOwnerApp = selectedApp;
      events = await fetchSessionHistory(
        sessionOwnerApp || selectedApp,
        userId,
        selectedSessionId,
      );
      currentExecutingAgent = getActiveAgentFromEvents(
        events,
        sessionOwnerApp || selectedApp,
        apps,
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
      await deleteSessionRequest(sessionOwnerApp || selectedApp, userId, sessionId);
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

  let currentAbortController = null;

  function stopGeneration() {
    if (currentAbortController) {
      try {
        currentAbortController.abort();
      } catch (e) {
        console.warn("Abort error:", e);
      }
      currentAbortController = null;
    }
    isLoading = false;
    isSubmitting = false;
    clearInterval(statusInterval);
  }

  // Send Message / Run Agent
  async function sendMessage() {
    if (isLoading || isSubmitting) return;
    if (!queryText.trim() && stagedFiles.length === 0) return;

    if (currentAbortController) {
      try {
        currentAbortController.abort();
      } catch (e) {
        // ignore
      }
    }
    currentAbortController = new AbortController();

    isSubmitting = true;
    isLoading = true;

    if (!selectedSessionId) {
      const appToCreate = sessionOwnerApp || selectedApp || "root_agent";
      const newSessionId = `session_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
      try {
        const statePayload = getSessionStatePayload();
        await createSession(appToCreate, userId, newSessionId, statePayload);
        selectedSessionId = newSessionId;
        sessionOwnerApp = appToCreate;
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
    currentExecutingAgent = activeAgent || sessionOwnerApp || selectedApp || "root_agent";
    startStatusTicker(currentExecutingAgent);

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

      const statePayload = getSessionStatePayload();
      let metadataHeader = "";
      if (statePayload.google_drive_folder_id) {
        metadataHeader += `[Target Drive Folder: ${statePayload.google_drive_folder_id}] `;
      }
      if (statePayload.google_docs_template_id) {
        metadataHeader += `[Target Template: ${statePayload.google_docs_template_id}] `;
      }
      if (statePayload.google_drive_access_token) {
        metadataHeader += `[Google Drive Token: ${statePayload.google_drive_access_token}] `;
      }

      const streamParts = [...parts];
      if (metadataHeader) {
        streamParts.push({ text: metadataHeader.trim() });
      }

      await runSSEStream({
        appName: sessionOwnerApp || selectedApp || "root_agent",
        userId,
        sessionId: selectedSessionId,
        parts: streamParts,
        state: statePayload,
        signal: currentAbortController.signal,
        onEvent: (eventObj) => {
          if (!eventObj) return;

          const detected =
            getEventAgent(eventObj, apps) ||
            (eventObj.author && eventObj.author !== "user"
              ? resolveAgentId(eventObj.author, apps) || cleanAuthorName(eventObj.author)
              : null);

          if (
            detected &&
            detected !== "user" &&
            (!currentExecutingAgent ||
              currentExecutingAgent === "root_agent" ||
              detected !== "root_agent")
          ) {
            if (detected !== currentExecutingAgent) {
              currentExecutingAgent = detected;
              startStatusTicker(currentExecutingAgent);
            }
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
      if (e.name === "AbortError" || currentAbortController?.signal?.aborted) {
        console.info("Generation cancelled by user.");
      } else {
        console.error(e);
        errorMsg = e.message || "Execution failed";
      }
    } finally {
      isLoading = false;
      isSubmitting = false;
      currentAbortController = null;
      clearInterval(statusInterval);
      scrollToBottom();
    }
  }

  function updateConfig(newConfig) {
    studioConfig = newConfig;
    saveAppConfig(newConfig);
  }

  async function handleGoogleLogin() {
    isLoggingIn = true;
    authError = "";
    try {
      const res = await loginWithGoogle();
      currentUser = res.user;
      selectedSessionId = "";
      events = [];
      queryText = "";
      stagedFiles = [];
    } catch (err) {
      console.error("Google Auth failed:", err);
      if (err.code === "auth/popup-closed-by-user") {
        authError = "Sign-in popup was closed. Please try again.";
      } else if (err.code === "auth/unauthorized-domain") {
        authError = "Domain is not authorized in Firebase Authentication.";
      } else {
        authError = err.message || "Failed to sign in with Google.";
      }
    } finally {
      isLoggingIn = false;
    }
  }

  async function handleGoogleLogout() {
    await logoutUser();
    currentUser = null;
    showUserMenu = false;
  }

  onMount(() => {
    document.documentElement.classList.add("dark");
    document.documentElement.setAttribute("data-theme", "dark");
    loadApps();

    const unsubscribeAuth = onAuthStateChanged(auth, (user) => {
      currentUser = user;
      isAuthLoading = false;
      if (user && user.uid) {
        userId = `user_${user.uid.slice(0, 10)}`;
      }
    });

    return () => {
      if (unsubscribeAuth) unsubscribeAuth();
    };
  });
</script>

<svelte:window
  onkeydown={(e) => {
    if (e.key === "Escape") {
      showUserMenu = false;
    }
  }}
  onclick={(e) => {
    if (showUserMenu && !e.target.closest?.(".user-menu-container"))
      showUserMenu = false;
  }}
/>

{#if isAuthLoading}
  <div class="auth-loading-screen">
    <div class="auth-loading-spinner"></div>
    <span class="auth-loading-text">Connecting to Community AI Studio...</span>
  </div>
{:else if !currentUser}
  <LoginScreen 
    onLogin={handleGoogleLogin} 
    {isLoggingIn} 
    errorMessage={authError} 
  />
{:else}
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
      <!-- Community AI Studio Brand Badge (Leftmost) -->
      <button
        class="brand-badge"
        onclick={() => {
          selectedSessionId = "";
          events = [];
        }}
        data-tooltip="Home"
        aria-label="Home"
      >
        <img
          src={squareLogo}
          alt="Community AI Studio"
          class="brand-icon-img"
        />
        <div class="brand-text">
          <span class="brand-name">Community AI Studio</span>
          <span class="brand-sub">{studioConfig.communityName || "GDG Krakow"}</span>
        </div>
      </button>

      <div class="header-divider"></div>

      <!-- New Session Button (With label) -->
      <button
        class="header-btn-new-session"
        onclick={() => startNewSession()}
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
        data-tooltip="Session History"
        aria-label="Session History"
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
          class:is-main={activeAgent === "root_agent"}
        >
          {#if selectedSessionId}
            <span
              class="live-status-dot"
              style="background: {activeAgentTheme.color}; box-shadow: 0 0 8px {activeAgentTheme.color}80;"
              data-tooltip="Session Active • Connected ({activeAgentTheme.label})"
              aria-label="Session Active • Connected ({activeAgentTheme.label})"
            ></span>
          {:else if activeAgent === "root_agent"}
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
            value={activeAgent}
            onchange={(e) => handleAgentChange(e.target.value)}
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

      <!-- Multi-Agent Architecture -->
      <button
        class="icon-btn"
        class:active={showAgentGraph}
        onclick={() => (showAgentGraph = true)}
        data-tooltip="Multi-Agent Architecture"
        aria-label="Multi-Agent Architecture"
      >
        <Workflow size={18} strokeWidth={1.75} />
      </button>

      <!-- User Profile & Workspace Options Dropdown (Combined) -->
      {#if currentUser}
        <div class="user-menu-container">
          <button 
            class="user-header-profile" 
            class:active={showUserMenu}
            onclick={(e) => {
              e.stopPropagation();
              showUserMenu = !showUserMenu;
            }} 
            title="Account & Options ({currentUser.displayName || 'Google Account'})"
            aria-label="Account and options"
          >
            <div class="user-avatar-wrap">
              {#if currentUser.photoURL}
                <img src={currentUser.photoURL} alt="User avatar" class="header-avatar-img" />
              {:else}
                <span class="header-avatar-fallback">
                  {(currentUser.displayName || 'U').charAt(0).toUpperCase()}
                </span>
              {/if}
            </div>
            <ChevronDown size={11} strokeWidth={2.2} class="profile-dropdown-arrow" />
          </button>

          {#if showUserMenu}
            <div class="dropdown-menu user-dropdown">
              <!-- Account info header -->
              <div class="user-dropdown-header">
                <div class="user-dropdown-top">
                  {#if currentUser.photoURL}
                    <img src={currentUser.photoURL} alt="Avatar" class="dropdown-avatar-img" />
                  {:else}
                    <span class="dropdown-avatar-fallback">
                      {(currentUser.displayName || 'U').charAt(0).toUpperCase()}
                    </span>
                  {/if}
                  <div class="user-dropdown-info">
                    <div class="user-dropdown-name">{currentUser.displayName || 'Google Account'}</div>
                  </div>
                </div>
              </div>

              <div class="dropdown-divider"></div>

              <!-- Workspace Theme / Capabilities / Settings -->
              <button
                class="dropdown-item"
                onclick={() => {
                  toggleTheme();
                  showUserMenu = false;
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
                  showUserMenu = false;
                }}
              >
                <HelpCircle size={15} strokeWidth={1.75} class="dropdown-icon" />
                <span>Capabilities</span>
              </button>

              <button
                class="dropdown-item"
                onclick={() => {
                  showSettings = true;
                  showUserMenu = false;
                }}
              >
                <Settings size={15} strokeWidth={1.75} class="dropdown-icon" />
                <span>Settings</span>
              </button>

              <div class="dropdown-divider"></div>

              <!-- Logout -->
              <button
                class="dropdown-item dropdown-item-danger"
                onclick={() => {
                  handleGoogleLogout();
                  showUserMenu = false;
                }}
              >
                <LogOut size={15} strokeWidth={1.75} class="dropdown-icon" />
                <span>Sign out</span>
              </button>
            </div>
          {/if}
        </div>
      {/if}
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
      <!-- Drag & Drop Overlay (Expansive) -->
      {#if isDragging}
        <div class="drag-zone-overlay">
          <div class="drag-zone-card">
            <div class="drag-icon-circle">
              <Paperclip size={36} class="drag-icon" />
            </div>
            <h3>Drop Files Anywhere to Attach</h3>
            <p>
              Receipts, invoices, portraits, spreadsheets, or attendee rosters will be attached directly to your active session.
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
              {#each CATALOG_AGENTS as agent}
                {@const AgentIcon = agent.icon}
                <button
                  class="agent-catalog-card"
                  style="--card-accent: {agent.accent}; --card-bg: {agent.bg};"
                  onclick={() => {
                    startNewSession(agent.id);
                  }}
                >
                  <div class="agent-card-header">
                    <div class="agent-icon-box">
                      <AgentIcon size={18} strokeWidth={1.75} />
                    </div>
                    <div class="agent-title-col">
                      <strong>{agent.name}</strong>
                      <span class="agent-type-tag">{agent.tag}</span>
                    </div>
                  </div>
                  <p class="agent-card-desc">
                    {agent.desc}
                  </p>
                  <div class="card-footer-action">
                    <span>{agent.actionText}</span>
                    <ArrowRight size={14} />
                  </div>
                </button>
              {/each}
            </div>
          </div>
        </div>
      {:else}
        <!-- Active Chat Message Stream -->
        <div class="chat-viewport" bind:this={chatBodyElement}>
          <div class="chat-stream-container">
            {#if filteredEvents.length === 0}
              {@const CurrentAgentIcon = getAgentIcon(activeAgent)}
              <div
                class="agent-welcome-card"
                style="--agent-accent: {activeAgentTheme.color}; --agent-bg: {activeAgentTheme.bg};"
              >
                <div class="agent-welcome-header">
                  <div
                    class="agent-welcome-avatar"
                    style="background: {activeAgentTheme.bg}; color: {activeAgentTheme.color}; border: 1px solid {activeAgentTheme.color}40;"
                  >
                    <CurrentAgentIcon size={22} strokeWidth={1.75} />
                  </div>
                  <div class="agent-welcome-meta">
                    <div
                      class="agent-welcome-badge"
                      style="color: {activeAgentTheme.color}; background: {activeAgentTheme.bg}; border: 1px solid {activeAgentTheme.color}30;"
                    >
                      {activeAgentTheme.label}
                    </div>
                    <h2>{getAgentHeading(activeAgent)}</h2>
                    <p>{getAgentDescription(activeAgent)}</p>
                  </div>
                </div>

                <div class="starter-prompts-section">
                  <span class="starter-label">Suggested actions:</span>
                  <div class="starter-chips">
                    {#each getAgentStarterPrompts(activeAgent) as item}
                      {@const promptText = typeof item === "string" ? item : item.prompt}
                      {@const displayText = typeof item === "string" ? item : item.text}
                      {@const iconName = typeof item === "object" ? item.icon : null}
                      <button
                        class="starter-chip"
                        onclick={() => selectStarterPrompt(promptText)}
                      >
                        {#if iconName && ICON_MAP[iconName]}
                          {@const IconComp = ICON_MAP[iconName]}
                          <IconComp size={13} class="starter-chip-icon" />
                        {/if}
                        <span>{displayText}</span>
                        <ArrowRight size={12} class="starter-arrow" />
                      </button>
                    {/each}
                  </div>
                </div>
              </div>
            {/if}

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
          onStop={stopGeneration}
        />
      {/if}
    </main>
  </div>
</div>

<!-- Capabilities Modal -->
<CapabilitiesModal
  show={showLegend}
  communityName={studioConfig.communityName || "GDG Krakow"}
  onClose={() => (showLegend = false)}
/>

<!-- Settings Modal -->
<SettingsModal
  show={showSettings}
  config={studioConfig}
  onSave={updateConfig}
  onClose={() => (showSettings = false)}
/>

<!-- Multi-Agent Architecture Modal -->
{#if showAgentGraph}
  <AgentGraph
    {events}
    currentExecutingAgent={activeAgent}
    {isLoading}
    selectedApp={sessionOwnerApp || selectedApp}
    onSelectAgent={(agentId) => {
      handleAgentChange(agentId);
      showAgentGraph = false;
    }}
    onClose={() => (showAgentGraph = false)}
  />
{/if}
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
    gap: 9px;
    padding: 0;
    user-select: none;
    background: transparent;
    border: none;
    cursor: pointer;
    text-align: left;
    outline: none;
    transition: opacity 0.15s ease;
  }

  .brand-badge:hover,
  .brand-badge:focus,
  .brand-badge:active {
    background: transparent;
    border: none;
    box-shadow: none;
    outline: none;
    opacity: 0.88;
  }

  .brand-icon-img {
    width: 28px;
    height: 28px;
    border-radius: 7px;
    object-fit: cover;
    flex-shrink: 0;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.18);
  }

  .brand-text {
    display: flex;
    flex-direction: column;
    line-height: 1.15;
  }

  .brand-name {
    font-size: 13px;
    font-weight: 700;
    letter-spacing: -0.015em;
    color: var(--text-primary);
  }

  .brand-sub {
    font-size: 10.5px;
    font-weight: 500;
    color: var(--text-secondary);
    letter-spacing: 0.01em;
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

  .dropdown-item-danger {
    color: #ef4444 !important;
  }

  .dropdown-item-danger :global(.dropdown-icon) {
    color: #ef4444 !important;
  }

  .dropdown-item-danger:hover {
    background: rgba(239, 68, 68, 0.12) !important;
    color: #ef4444 !important;
  }

  .dropdown-item-danger:hover :global(.dropdown-icon) {
    color: #ef4444 !important;
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

  /* Drag & Drop Overlay - Expansive & Immersive */
  .drag-zone-overlay {
    position: absolute;
    inset: 0;
    background: rgba(8, 11, 18, 0.88);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    z-index: 100;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
    box-sizing: border-box;
    pointer-events: none;
    animation: fadeIn 0.2s ease-out;
  }

  .drag-zone-card {
    width: 100%;
    height: 100%;
    max-width: none;
    border: 2.5px dashed var(--primary-accent);
    background: rgba(66, 133, 244, 0.04);
    box-shadow: 
      0 0 40px rgba(66, 133, 244, 0.15),
      inset 0 0 60px rgba(66, 133, 244, 0.06);
    border-radius: var(--radius-2xl, 24px);
    padding: 32px;
    box-sizing: border-box;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 14px;
    transition: all 0.2s ease;
  }

  .drag-icon-circle {
    width: 68px;
    height: 68px;
    border-radius: 50%;
    background: rgba(66, 133, 244, 0.15);
    border: 1px solid rgba(66, 133, 244, 0.35);
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 2px;
    box-shadow: 0 8px 24px rgba(66, 133, 244, 0.25);
  }

  .drag-zone-card h3 {
    font-size: 22px;
    font-weight: 700;
    color: #ffffff;
    margin: 0;
    letter-spacing: -0.02em;
  }

  .drag-zone-card p {
    font-size: 14px;
    color: var(--text-secondary, #94a3b8);
    max-width: 520px;
    line-height: 1.5;
    margin: 0;
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
    margin-bottom: 24px;
    display: flex;
    flex-direction: column;
    align-items: center;
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

  /* Agent Welcome Card (Chat Empty State) */
  .agent-welcome-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-xl);
    padding: 24px;
    margin: 24px 0 20px;
    display: flex;
    flex-direction: column;
    gap: 18px;
    animation: fadeIn 0.3s ease-out;
  }

  .agent-welcome-header {
    display: flex;
    align-items: flex-start;
    gap: 14px;
  }

  .agent-welcome-avatar {
    width: 44px;
    height: 44px;
    border-radius: var(--radius-md);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .agent-welcome-meta {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .agent-welcome-badge {
    align-self: flex-start;
    font-size: 10.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 2px 8px;
    border-radius: var(--radius-pill);
    margin-bottom: 2px;
  }

  .agent-welcome-meta h2 {
    font-size: 18px;
    font-weight: 700;
    color: var(--text-primary);
    margin: 0;
    letter-spacing: -0.01em;
  }

  .agent-welcome-meta p {
    font-size: 13px;
    color: var(--text-secondary);
    line-height: 1.5;
    margin: 0;
  }

  .starter-prompts-section {
    display: flex;
    flex-direction: column;
    gap: 10px;
    border-top: 1px solid var(--border-subtle);
    padding-top: 14px;
  }

  .starter-label {
    font-size: 11px;
    font-weight: 700;
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .starter-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .starter-chip {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-pill);
    padding: 6px 12px;
    font-size: 12px;
    color: var(--text-primary);
    cursor: pointer;
    text-align: left;
    transition: var(--transition-fast);
  }

  .starter-chip:hover {
    background: var(--bg-hover);
    border-color: var(--agent-accent, var(--primary-accent));
    transform: translateY(-1px);
    box-shadow: var(--shadow-sm);
  }

  :global(.starter-chip-icon) {
    color: var(--agent-accent, var(--primary-accent));
    flex-shrink: 0;
    opacity: 0.85;
    transition: var(--transition-fast);
  }

  .starter-chip:hover :global(.starter-chip-icon) {
    opacity: 1;
    transform: scale(1.1);
  }

  :global(.starter-arrow) {
    color: var(--text-tertiary);
    transition: var(--transition-fast);
    flex-shrink: 0;
  }

  .starter-chip:hover :global(.starter-arrow) {
    color: var(--agent-accent, var(--primary-accent));
    transform: translateX(2px);
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

  /* Auth Initial Loading Screen */
  .auth-loading-screen {
    position: fixed;
    inset: 0;
    width: 100vw;
    height: 100vh;
    background: #080b11;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 16px;
    z-index: 9999;
  }

  .auth-loading-spinner {
    width: 32px;
    height: 32px;
    border: 3px solid rgba(255, 255, 255, 0.1);
    border-top-color: #4285F4;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }

  .auth-loading-text {
    font-size: 13px;
    font-weight: 500;
    color: #94a3b8;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  /* User Menu & Avatar */
  .user-menu-container {
    position: relative;
    display: inline-flex;
    align-items: center;
  }

  .user-header-profile {
    background: var(--bg-surface-elevated, rgba(255, 255, 255, 0.04));
    border: 1px solid var(--border-subtle);
    padding: 2px 6px 2px 2px;
    border-radius: 16px;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    cursor: pointer;
    transition: var(--transition-fast);
    height: 30px;
    box-sizing: border-box;
  }

  .user-header-profile:hover,
  .user-header-profile.active {
    background: var(--bg-surface-variant);
    border-color: var(--primary-accent);
  }

  .user-header-profile.active :global(.profile-dropdown-arrow) {
    transform: rotate(180deg);
  }

  :global(.profile-dropdown-arrow) {
    color: var(--text-tertiary);
    transition: transform var(--transition-fast), color var(--transition-fast);
    flex-shrink: 0;
  }

  .user-header-profile:hover :global(.profile-dropdown-arrow) {
    color: var(--text-primary);
  }

  .user-avatar-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
  }

  .header-avatar-img {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    object-fit: cover;
  }

  .header-avatar-fallback {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    background: var(--primary-accent);
    color: #ffffff;
    font-size: 11.5px;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  .user-dropdown {
    right: 0;
    top: calc(100% + 8px);
    width: 220px;
    padding: 8px;
    z-index: 1000;
  }

  .user-dropdown-header {
    padding: 6px 6px 8px;
  }

  .user-dropdown-top {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .dropdown-avatar-img {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    object-fit: cover;
    flex-shrink: 0;
  }

  .dropdown-avatar-fallback {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: var(--primary-accent);
    color: #ffffff;
    font-size: 13px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .user-dropdown-info {
    flex: 1;
    min-width: 0;
  }

  .user-dropdown-name {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }


</style>
