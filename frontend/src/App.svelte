<script>
  import { onMount } from 'svelte';
  import { marked } from 'marked';

  // Markdown rendering helper
  function renderMarkdown(text) {
    if (!text) return '';
    try {
      return marked.parse(text, { gfm: true, breaks: true });
    } catch (e) {
      console.error("Failed to parse markdown:", e);
      return text.replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }
  }

  // State Variables
  let apps = $state.raw([]);
  let selectedApp = $state('root_agent');
  let userId = $state('user');
  let sessions = $state.raw([]);
  let selectedSessionId = $state('');
  let events = $state.raw([]);
  let queryText = $state('');
  let isLoading = $state(false);
  let errorMsg = $state('');
  let isDarkMode = $state(true);
  
  // Custom interface toggles
  let showSessions = $state(false); // Hidden/collapsed by default
  let showLegend = $state(false);   // Color legend modal toggle
  
  // Staged files
  let isDragging = $state(false);
  let stagedFiles = $state([]); 
  let textareaElement = $state();

  // Intermediate status ticker variables
  let statusText = $state('Orchestrating agents...');
  let statusInterval;

  // Theme Toggler
  function toggleTheme() {
    isDarkMode = !isDarkMode;
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }

  // Load Apps from ADK backend
  async function loadApps() {
    try {
      errorMsg = '';
      const res = await fetch('/list-apps');
      if (!res.ok) throw new Error(`Failed to fetch apps: ${res.statusText}`);
      const data = await res.json();
      if (Array.isArray(data)) {
        const nonAgents = ['configs', 'docs', 'frontend'];
        const appNameMapping = {
          root_agent: 'Root Orchestrator',
          receipt_scanner: 'Receipt Scanner',
          video_editor: 'Live Video Editor',
          linkedin_post_generator: 'LinkedIn Planner',
          registration_manager: 'Registrations Manager',
          event_planner: 'Event Scheduler',
          agenda_generator: 'Agenda Formatter',
          office_secretary: 'Office Secretary'
        };
        apps = data
          .filter(name => !nonAgents.includes(name))
          .map(name => ({
            name,
            root_agent_name: appNameMapping[name] || name.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
          }));
      } else {
        apps = data.apps || [];
      }
      if (apps.length > 0) {
        const hasRoot = apps.some(a => a.name === 'root_agent');
        if (hasRoot) {
          selectedApp = 'root_agent';
        } else if (!apps.some(a => a.name === selectedApp)) {
          selectedApp = apps[0].name;
        }
      }
      await loadSessions();
    } catch (e) {
      console.error(e);
      errorMsg = `Backend Connection Error: Make sure your ADK server is running on port 8080! Details: ${e.message}`;
    }
  }

  // Load active sessions for selected App and User
  async function loadSessions() {
    if (!selectedApp) return;
    try {
      errorMsg = '';
      const res = await fetch(`/apps/${selectedApp}/users/${userId}/sessions`);
      if (!res.ok) {
        if (res.status === 404) {
          sessions = [];
          return;
        }
        throw new Error(`Failed to fetch sessions: ${res.statusText}`);
      }
      const data = await res.json();
      const rawSessions = Array.isArray(data) ? data : (data.sessions || []);
      sessions = rawSessions.map(s => ({
        id: s.id || s.session_id,
        session_id: s.id || s.session_id,
        state: s.state || {},
        events: s.events || []
      })).sort((a, b) => b.session_id.localeCompare(a.session_id));
      
      if (sessions.length > 0) {
        if (!selectedSessionId || !sessions.some(s => s.session_id === selectedSessionId)) {
          selectSession(sessions[0].session_id);
        }
      } else {
        selectedSessionId = '';
        events = [];
      }
    } catch (e) {
      console.error(e);
      errorMsg = `Failed to load sessions: ${e.message}`;
    }
  }

  // Start new Session
  async function startNewSession() {
    if (!selectedApp) return;
    const newSessionId = `session_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
    try {
      errorMsg = '';
      isLoading = true;
      const res = await fetch(`/apps/${selectedApp}/users/${userId}/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: newSessionId })
      });
      if (!res.ok) throw new Error(`Failed to create session: ${res.statusText}`);
      await loadSessions();
      selectSession(newSessionId);
      showSessions = false; // Keep sessions panel collapsed by default as requested
    } catch (e) {
      console.error(e);
      errorMsg = `Failed to start session: ${e.message}`;
    } finally {
      isLoading = false;
    }
  }

  // Select existing Session and fetch history
  async function selectSession(sessionId) {
    selectedSessionId = sessionId;
    if (!selectedSessionId) {
      events = [];
      return;
    }
    try {
      errorMsg = '';
      const res = await fetch(`/apps/${selectedApp}/users/${userId}/sessions/${selectedSessionId}`);
      if (!res.ok) throw new Error(`Failed to load session details: ${res.statusText}`);
      const data = await res.json();
      events = data.events || [];
      scrollToBottom();
    } catch (e) {
      console.error(e);
      errorMsg = `Failed to load session history: ${e.message}`;
    }
  }

  // Delete active session
  async function deleteSession(sessionId) {
    if (!confirm('Are you sure you want to delete this session and its history?')) return;
    try {
      errorMsg = '';
      const res = await fetch(`/apps/${selectedApp}/users/${userId}/sessions/${sessionId}`, {
        method: 'DELETE'
      });
      if (!res.ok) throw new Error(`Failed to delete session: ${res.statusText}`);
      if (selectedSessionId === sessionId) {
        selectedSessionId = '';
        events = [];
      }
      await loadSessions();
    } catch (e) {
      console.error(e);
      errorMsg = `Failed to delete session: ${e.message}`;
    }
  }

  // Handle Drag & Drop
  function handleDragOver(e) {
    e.preventDefault();
    isDragging = true;
  }

  function handleDragLeave() {
    isDragging = false;
  }

  function handleDrop(e) {
    e.preventDefault();
    isDragging = false;
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      Array.from(files).forEach(file => processFile(file));
    }
  }

  function handleFileSelect(e) {
    const files = e.target.files;
    if (files && files.length > 0) {
      Array.from(files).forEach(file => processFile(file));
    }
  }

  function processFile(file) {
    const reader = new FileReader();
    reader.onload = () => {
      const base64Data = reader.result.split(',')[1];
      stagedFiles = [...stagedFiles, {
        name: file.name,
        type: file.type || 'application/octet-stream',
        data: base64Data,
        preview: file.type.startsWith('image/') ? reader.result : null
      }];
    };
    reader.readAsDataURL(file);
  }

  function removeStagedFile(index) {
    stagedFiles = stagedFiles.filter((_, i) => i !== index);
  }

  // Cycle through intermediate agent status text while loading to show progress
  function startStatusTicker(app) {
    const statuses = {
      root_agent: [
        'Root Orchestrator coordinating request...',
        'Analyzing routing parameters...',
        'Invoking specialized sub-agents...',
        'Verifying execution prerequisites...'
      ],
      receipt_scanner: [
        'Fetching Pekao Bank exchange rates...',
        'Scanning attachment with Gemini Vision...',
        'Converting expenses to EUR/USD/PLN...',
        'Checking historical structures (Anti-re-processing)...',
        'Translating item details to English...',
        'Generating Google Docs Expense Report...'
      ],
      video_editor: [
        'Staging uploaded portrait in staged_media...',
        'Detecting face landmarks via Gemini...',
        'Executing smart Outpainting to 9:16 aspect ratio...',
        'Crafting cinematic Google Veo video prompt...',
        'Generating 8s video intro via Vertex AI Veo...',
        'Compiling high-fidelity 4K media cards...'
      ],
      registration_manager: [
        'Scanning participant registration list...',
        'Fetching organizers database...',
        'Performing phonetic fuzzy name matching...',
        'Filtering test and corrupt registrations...',
        'Sorting multilingual lists alphabetically...',
        'Compiling clean DOCX registration document...'
      ],
      event_planner: [
        'Searching Krakow Luma AI meetup calendar...',
        'Scanning Meetup.com for Krakow tech conflicts...',
        'Checking Polish statutory holidays...',
        'Identifying long holiday weekends...',
        'Recommending optimal mid-week dates (Tue-Thu)...'
      ],
      agenda_generator: [
        'Calculating timeline starting at 17:30...',
        'Formatting speaker session durations...',
        'Integrating coffee breaks and pizza pauses...',
        'Rounding timeline boundary finish times...',
        'Generating copy-pasteable English summary...'
      ],
      office_secretary: [
        'Checking request type...',
        'Validating mandatory date presence...',
        'Formulating polite visitor keys request...',
        'Composing Hub reservation email draft...'
      ]
    };
    
    const list = statuses[app] || ['Processing intermediate step...', 'Executing agent logic...', 'Invoking external API connectors...'];
    let idx = 0;
    statusText = list[0];
    
    clearInterval(statusInterval);
    statusInterval = setInterval(() => {
      idx = (idx + 1) % list.length;
      statusText = list[idx];
    }, 2200);
  }

  // Maps backend tool names to user-friendly log descriptions
  function getFriendlyToolCall(name, args) {
    const mappings = {
      verify_portrait_photo: () => "Running face detection on portrait photo...",
      stage_uploaded_media: () => "Staging uploaded media file to workspace...",
      animate_photo: () => "Generating background video intro via Google Veo...",
      update_composer: (a) => `Updating HTML template composition with details for ${a.name || 'speaker'}...`,
      render_composer: () => "Compiling card rendering pipelines (1080p, 4K, GIF, Poster PNG)...",
      validate_metadata: (a) => `Validating character limits for "${a.name || 'speaker'}"...`,
      
      // Receipt Scanner tools
      scan_receipt_with_vision: () => "Analyzing receipt scan via Gemini Vision OCR...",
      convert_currency: () => "Converting currency values using exchange rates...",
      export_to_google_docs: () => "Creating Google Docs expense report from template..."
    };

    if (mappings[name]) {
      return mappings[name](args || {});
    }
    // Fallback: convert snake_case to Title Case
    const formatted = name.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
    return `Executing ${formatted}...`;
  }

  function getFriendlyToolResponse(name, response, args) {
    const mappings = {
      verify_portrait_photo: () => "Face verification passed successfully! A clear face was detected.",
      stage_uploaded_media: (r) => `File successfully staged to workspace.`,
      animate_photo: () => "Google Veo video generation completed successfully.",
      update_composer: () => "Composition HTML updated with new layout parameters.",
      render_composer: () => "All requested files compiled and saved to renders/ folder.",
      validate_metadata: () => "Text validation passed successfully.",
      
      // Receipt Scanner tools
      scan_receipt_with_vision: () => "Receipt items and taxes extracted successfully.",
      convert_currency: () => "Exchange rates converted.",
      export_to_google_docs: (r) => `Google Doc generated successfully.`
    };

    if (mappings[name]) {
      return mappings[name](response || {}, args || {});
    }
    return "Completed successfully.";
  }

  // Helper to remove "Active Context: " prefix
  function cleanAuthorName(author) {
    if (!author) return '';
    return author.replace(/^Active Context:\s*/i, '').trim();
  }

  let copiedId = $state('');
  
  // Parse response into separate variants/options if they exist
  function parseResponseVariants(text, author) {
    if (!text) return [];
    const clean = cleanAuthorName(author).toLowerCase();
    
    // Only check for splits if it's from LinkedIn Planner or contains option/agenda/recap headings
    const isSpecialApp = clean.includes('linkedin') || clean.includes('post_generator') || clean.includes('agenda') || clean.includes('agenda_generator') || text.toLowerCase().includes('option 1') || text.toLowerCase().includes('variant 1') || text.toLowerCase().includes('option 2') || text.toLowerCase().includes('variant 2') || text.toLowerCase().includes('agenda') || text.toLowerCase().includes('recap');
    
    if (!isSpecialApp) {
      return [{ header: '', body: text }];
    }
    
    // Split by headers like Option X, Variant X, Agenda, Recap X (preceded by markdown, bold or plain text)
    const regex = /(?:^|\n)((?:###?\s*|##\s*|#\s*|\*\*|)\s*(?:Event Recap Post|Event Recap|Recap|Variant|Option|Agenda)\s*(?:Variant|Option)?\s*\d+[:\s\-\(]*[^\n]*)/iu;
    const parts = text.split(regex);
    
    if (parts.length < 3) {
      if (clean.includes('agenda') || clean.includes('agenda_generator') || text.toLowerCase().includes('agenda')) {
        const buildIndex = text.toLowerCase().indexOf('build with ai');
        if (buildIndex > 0) {
          const intro = text.substring(0, buildIndex).trim();
          const agendaBody = text.substring(buildIndex).trim();
          const fallbackVariants = [];
          if (intro) {
            fallbackVariants.push({ header: 'Introduction', body: intro });
          }
          fallbackVariants.push({ header: 'Agenda', body: agendaBody });
          return fallbackVariants;
        }
      }
      return [{ header: '', body: text }];
    }
    
    const variants = [];
    if (parts[0].trim()) {
      variants.push({ header: 'Introduction', body: parts[0].trim() });
    }
    
    for (let i = 1; i < parts.length; i += 2) {
      let header = parts[i] ? parts[i].trim() : '';
      // Clean up leading markdown markers and bold markers from the header for UI badge representation
      header = header.replace(/^(?:###?|##|#)\s*/, '').trim();
      header = header.replace(/^\*\*|\*\*$/g, '').trim();
      const body = parts[i + 1] ? parts[i + 1].trim() : '';
      
      // Look for lines introducing the next speaker or section
      // E.g., "Introducing Speaker:", "Speaker:", "Event Recap:" (or similar structures)
      const introRegex = /(?:\n|^)(Introducing Speaker:|Speaker:|Event Recap:|[^\n]*Introducing Speaker:[^\n]*|[^\n]*Event Recap:[^\n]*)/i;
      const match = body.match(introRegex);
      
      if (match && match.index !== undefined) {
        const actualBody = body.substring(0, match.index).trim();
        const nextIntro = body.substring(match.index).trim();
        
        if (actualBody) {
          variants.push({ header, body: actualBody });
        }
        if (nextIntro) {
          let nextHeader = 'Section';
          const lowerIntro = nextIntro.toLowerCase();
          if (lowerIntro.includes('introducing speaker') || lowerIntro.includes('speaker:')) {
            nextHeader = 'Speaker Intro';
          } else if (lowerIntro.includes('event recap') || lowerIntro.includes('recap:')) {
            nextHeader = 'Event Recap';
          }
          variants.push({ header: nextHeader, body: nextIntro });
        }
      } else {
        if (body.trim()) {
          variants.push({ header, body });
        }
      }
    }
    
    return variants;
  }

  // Copy plain text to clipboard safely
  function copyToClipboard(text, id) {
    if (!navigator.clipboard) return;
    navigator.clipboard.writeText(text).then(() => {
      copiedId = id;
      setTimeout(() => {
        if (copiedId === id) copiedId = '';
      }, 2000);
    }).catch(err => {
      console.error('Failed to copy to clipboard:', err);
    });
  }

  // Focus and pre-fill input with selected variant for free-mode refinements
  function refineVariant(bodyText) {
    queryText = `Refine this option:\n---\n${bodyText}\n---\nMy adjustments: `;
    setTimeout(() => {
      if (textareaElement) {
        textareaElement.style.height = 'auto';
        textareaElement.style.height = (textareaElement.scrollHeight) + 'px';
        textareaElement.focus();
      }
    }, 50);
  }

  // Check if an event is an intermediate event (no text, only function calls/responses)
  function isIntermediateEvent(event) {
    if (!event) return true;
    if (event.author === 'user') return false;
    if (!event.content || !event.content.parts) return true;
    // Show all events containing content parts (including tool calls and responses)
    return false;
  }

  let filteredEvents = $derived(events.filter(e => !isIntermediateEvent(e)));

  // Run orchestrator / Send message (using SSE stream with fallback)
  async function sendMessage() {
    if (!selectedSessionId) {
      errorMsg = 'Please select or create a session first!';
      return;
    }
    if (!queryText.trim() && stagedFiles.length === 0) return;

    const currentText = queryText;
    const currentFiles = [...stagedFiles];
    
    // Clear inputs and start loading
    queryText = '';
    if (textareaElement) {
      textareaElement.style.height = 'auto';
    }
    stagedFiles = [];
    errorMsg = '';
    isLoading = true;
    startStatusTicker(selectedApp);

    try {
      const parts = [];
      
      // Stage files
      currentFiles.forEach(f => {
        parts.push({
          inline_data: {
            mime_type: f.type,
            data: f.data
          }
        });
      });

      // Prompt
      if (currentText.trim()) {
        parts.push({ text: currentText });
      }

      const payload = {
        app_name: selectedApp,
        user_id: userId,
        session_id: selectedSessionId,
        new_message: {
          role: 'user',
          parts: parts
        },
        streaming: true
      };

      let res;
      let useSSE = true;

      try {
        res = await fetch('/run_sse', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!res.ok) {
          useSSE = false;
        }
      } catch (err) {
        useSSE = false;
      }

      if (!useSSE) {
        // Fallback to traditional /run
        payload.streaming = false;
        res = await fetch('/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!res.ok) {
          const errDetail = await res.text();
          throw new Error(errDetail || res.statusText);
        }
        await selectSession(selectedSessionId);
      } else {
        // Stream chunk parser for real-time progress tickers!
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop();

          for (const line of lines) {
            const trimmed = line.trim();
            if (trimmed.startsWith('data: ')) {
              const dataStr = trimmed.slice(6).trim();
              if (!dataStr) continue;
              try {
                const eventObj = JSON.parse(dataStr);
                if (eventObj.error) {
                  const errStr = typeof eventObj.error === 'object' ? (eventObj.error.message || JSON.stringify(eventObj.error)) : eventObj.error;
                  throw new Error(errStr);
                }

                // Dynamically update status text based on intermediate tool calls or active agent
                if (eventObj.content && eventObj.content.parts) {
                  for (const part of eventObj.content.parts) {
                    const fc = part.function_call || part.functionCall;
                    const fr = part.function_response || part.functionResponse;
                    if (fc) {
                      const agentLabel = getAgentTheme(eventObj.author).label || eventObj.author;
                      statusText = `Agent ${agentLabel} launching ${fc.name}...`;
                    } else if (fr) {
                      statusText = `Step completed: ${fr.name}`;
                    } else if (part.text) {
                      const agentLabel = getAgentTheme(eventObj.author).label || eventObj.author;
                      statusText = `${agentLabel} responding...`;
                    }
                  }
                }
              } catch (parseErr) {
                // Ignore parsing errors for partial/malformed data chunks
              }
            }
          }
        }
        // Finally, fetch clean completed session history
        await selectSession(selectedSessionId);
      }
    } catch (e) {
      console.error(e);
      let displayError = e.message;
      try {
        const parsed = JSON.parse(e.message);
        if (parsed.detail) {
          displayError = parsed.detail;
        } else if (parsed.errorMessage) {
          displayError = parsed.errorMessage;
          // Try to recursively find nested JSON messages or details to clean up API errors
          try {
            const innerMatch = displayError.match(/'message':\s*'({[\s\S]*?})'/);
            if (innerMatch) {
              const cleanJsonStr = innerMatch[1].replace(/\\n/g, '\n').replace(/\\"/g, '"');
              const innerJson = JSON.parse(cleanJsonStr);
              if (innerJson.error && innerJson.error.message) {
                displayError = innerJson.error.message;
              }
            } else {
              const jsonCandidates = displayError.match(/\{[\s\S]*\}/);
              if (jsonCandidates) {
                const normalizedStr = jsonCandidates[0].replace(/'/g, '"');
                const candidate = JSON.parse(normalizedStr);
                if (candidate.error && candidate.error.message) {
                  displayError = candidate.error.message;
                } else if (candidate.message) {
                  displayError = candidate.message;
                }
              }
            }
          } catch (innerErr) {
            console.error('Failed to parse nested error details:', innerErr);
          }
          if (parsed.errorCode && !displayError.includes(parsed.errorCode)) {
            displayError = `${parsed.errorCode}: ${displayError}`;
          }
        } else if (parsed.error) {
          displayError = typeof parsed.error === 'object' ? (parsed.error.message || JSON.stringify(parsed.error)) : parsed.error;
        } else if (parsed.message) {
          displayError = parsed.message;
        }
      } catch(_) {}
      errorMsg = `Execution Error: ${displayError}`;
    } finally {
      isLoading = false;
      clearInterval(statusInterval);
      scrollToBottom();
    }
  }

  // Scroll
  let chatBodyElement = $state();
  function scrollToBottom() {
    setTimeout(() => {
      if (chatBodyElement) {
        chatBodyElement.scrollTo({
          top: chatBodyElement.scrollHeight,
          behavior: 'smooth'
        });
      }
    }, 50);
  }

  function handleKeyPress(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  onMount(() => {
    document.documentElement.classList.add('dark');
    loadApps();
  });

  // Dynamic helper to identify agents style colors
  function getAgentTheme(author) {
    if (!author) return {};
    const clean = cleanAuthorName(author);
    const lower = clean.toLowerCase();
    if (lower.includes('root')) return { color: 'var(--agent-root)', bg: 'var(--bg-root)', label: 'Root Orchestrator' };
    if (lower.includes('receipt')) return { color: 'var(--agent-receipt)', bg: 'var(--bg-receipt)', label: 'Receipt Scanner' };
    if (lower.includes('video') || lower.includes('avatar')) return { color: 'var(--agent-video)', bg: 'var(--bg-video)', label: 'Live Video Editor' };
    if (lower.includes('linkedin')) return { color: 'var(--agent-linkedin)', bg: 'var(--bg-linkedin)', label: 'LinkedIn Planner' };
    if (lower.includes('registration')) return { color: 'var(--agent-registration)', bg: 'var(--bg-registration)', label: 'Registrations Manager' };
    if (lower.includes('planner')) return { color: 'var(--agent-planner)', bg: 'var(--bg-planner)', label: 'Event Scheduler' };
    if (lower.includes('agenda')) return { color: 'var(--agent-agenda)', bg: 'var(--bg-agenda)', label: 'Agenda Formatter' };
    if (lower.includes('office') || lower.includes('secretary')) return { color: 'var(--agent-office)', bg: 'var(--bg-office)', label: 'Office Secretary' };
    
    // Format other names beautifully
    const formatted = clean.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
    return { color: 'var(--text-secondary)', bg: 'var(--panel-border)', label: formatted };
  }
</script>

<div class="app-layout" class:thinking-active={isLoading} style="--active-agent-color: {getAgentTheme(selectedApp).color}">
  <!-- Top premium navigation bar -->
  <header class="app-header">
    <div class="header-logo">
      <!-- Sidebar Drawer Toggle Button (Hamburger style) -->
      <button class="sidebar-toggle-btn" class:active={showSessions} onclick={() => showSessions = !showSessions} aria-label="Toggle Sessions">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <line x1="3" y1="12" x2="21" y2="12"></line>
          <line x1="3" y1="6" x2="21" y2="6"></line>
          <line x1="3" y1="18" x2="21" y2="18"></line>
        </svg>
      </button>

      <div class="logo-title">
        <h1>GDG Kraków</h1>
        <p>Advanced Agentic Workspace</p>
      </div>
      {#if selectedSessionId}
        <div class="active-session-indicator" title="Active Session">
          <span class="pulse-indicator-dot"></span>
          <span>Active</span>
        </div>
      {/if}
    </div>

    <!-- Main Navigation Actions -->
    <div class="header-actions">
      <!-- Active App selector -->
      <div class="app-selector-wrapper">
        <span class="selector-label">agent:</span>
        <select id="appSelect" bind:value={selectedApp} onchange={() => { selectedSessionId = ''; loadSessions(); }}>
          {#each apps as app}
            <option value={app.name}>{app.root_agent_name || app.name}</option>
          {/each}
        </select>
      </div>

      <!-- Legend of colors toggle -->
      <button class="legend-trigger-btn" onclick={() => showLegend = true} aria-label="Show capabilities">
        <span class="btn-text">Capabilities</span>
      </button>

      <!-- Theme Switcher -->
      <button class="theme-toggle-btn" onclick={toggleTheme} aria-label="Toggle theme">
        {#if isDarkMode}☀️{:else}🌙{/if}
      </button>
    </div>
  </header>

  <!-- Error display box -->
  {#if errorMsg}
    <div class="error-banner">
      <span class="error-icon">⚠️</span>
      <div class="error-content">
        <p>{errorMsg}</p>
      </div>
      <button class="error-close" onclick={() => errorMsg = ''}>&times;</button>
    </div>
  {/if}

  <div class="main-body">
    <!-- Collapsible Sidebar (Drawer panel) -->
    {#if showSessions}
      <aside class="sidebar">
        <div class="sidebar-section">
          <div class="section-header">
            <h2>Sessions</h2>
            <button class="new-session-btn" onclick={startNewSession} disabled={isLoading}>
              + New
            </button>
          </div>
          
          <div class="sessions-list">
            {#if sessions.length === 0}
              <p class="empty-list-text">No sessions yet. Create a new one.</p>
            {:else}
              {#each sessions as session, idx}
                <div class="session-card" class:active={selectedSessionId === session.session_id}>
                  <button class="session-select-btn" onclick={() => selectSession(session.session_id)}>
                    <div class="session-info">
                      <span class="session-name">Chat {sessions.length - idx}</span>
                      <span class="session-date">{selectedSessionId === session.session_id ? 'Active' : 'Past Chat'}</span>
                    </div>
                  </button>
                  <button class="session-delete-btn" onclick={() => deleteSession(session.session_id)} aria-label="Delete Session">
                    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <polyline points="3 6 5 6 21 6"></polyline>
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                    </svg>
                  </button>
                </div>
              {/each}
            {/if}
          </div>
        </div>
      </aside>
    {/if}

    <!-- Right Workspace: Interactive Chat Window -->
    <main class="chat-workspace" 
          ondragover={handleDragOver}
          ondragleave={handleDragLeave}
          ondrop={handleDrop}>
      
      <!-- Drag & Drop overlay indicator -->
      {#if isDragging}
        <div class="drag-overlay">
          <div class="drag-message">
            <span class="drag-emoji">📥</span>
            <h3>Drag & Drop Files Here</h3>
            <p>Accepts receipt scans, PDFs, and participant spreadsheets</p>
          </div>
        </div>
      {/if}

      {#if !selectedSessionId}
        <!-- Welcome empty state screen -->
        <div class="welcome-container">
          <h2>GDG Kraków AI Agents Portal</h2>
          <p>To get started, start a new session. This will allow you to interact with agents, upload files, and view generated reports.</p>
          <div class="welcome-action-box">
            <button class="start-btn" onclick={startNewSession}>🚀 Start a New Session</button>
          </div>
        </div>
      {:else}
        <!-- Session chat container -->
        <div class="chat-container">
          {#if isLoading}
            <div class="loading-progress-bar"></div>
          {/if}
          <!-- Chat Messages Body -->
          <div class="chat-body" bind:this={chatBodyElement}>
            <div class="chat-feed-wrapper">
              {#if events.length === 0}
                <div class="chat-empty-state">
                  <p>Session is active. Send a request or drag documents (receipt scans, participant lists) directly into this window.</p>
                </div>
              {/if}

              {#each filteredEvents as event, idx}
                {#if event.author === 'user'}
                  <!-- User Message -->
                  <div class="message-wrapper user-msg">
                    <div class="message-bubble">
                      {#if event.content && event.content.parts}
                        {#each event.content.parts as part}
                          {#if part.text}
                            <div class="msg-text markdown-body">{@html renderMarkdown(part.text)}</div>
                          {/if}
                          {#if part.inline_data}
                            <div class="uploaded-part-preview">
                              <span class="file-icon">📎</span>
                              <span class="file-name">Attachment ({part.inline_data.mime_type})</span>
                            </div>
                          {/if}
                        {/each}
                      {/if}
                    </div>
                    <span class="avatar-lbl">You</span>
                  </div>
                {:else}
                  <!-- Agent / Tool / Orchestrator Message -->
                  {@const theme = getAgentTheme(event.author)}
                  <div class="message-wrapper agent-msg" style="--agent-color: {theme.color}; --agent-bg: {theme.bg}">
                    
                    <!-- Flow Visualization Indicator (Simplified) -->
                    {#if idx === 0 || filteredEvents[idx - 1].author !== event.author}
                      <div class="delegation-badge" style="background: {theme.bg}; color: {theme.color}">
                        <span class="badge-dot" style="background: {theme.color}"></span>
                        <span class="badge-label">{theme.label}</span>
                      </div>
                    {/if}

                    <div class="message-bubble" class:thinking={event.author && event.author.toLowerCase().includes('thinking')}>
                      {#if event.content && event.content.parts}
                        {#each event.content.parts as part}
                          {#if part.text}
                            {@const variants = parseResponseVariants(part.text, event.author)}
                            {#if variants.length === 1}
                              <div class="msg-text markdown-body">{@html renderMarkdown(part.text)}</div>
                            {:else}
                              <div class="variants-container">
                                {#each variants as variant, vIdx}
                                  <div class="variant-card">
                                    <div class="variant-card-header">
                                      <span class="variant-badge">{variant.header}</span>
                                      <div class="card-header-actions">
                                        {#if variant.header.toLowerCase() !== 'introduction'}
                                          <button class="action-card-btn copy-btn" title="Copy text only" onclick={() => copyToClipboard(variant.body, 'v_' + idx + '_' + vIdx)}>
                                            {copiedId === 'v_' + idx + '_' + vIdx ? 'Copied!' : 'Copy'}
                                          </button>
                                          <button class="action-card-btn refine-btn" title="Refine option in free mode" onclick={() => refineVariant(variant.body)}>
                                            Refine
                                          </button>
                                        {/if}
                                      </div>
                                    </div>
                                    <div class="variant-card-body markdown-body">
                                      {@html renderMarkdown(variant.body)}
                                    </div>
                                  </div>
                                {/each}
                              </div>
                            {/if}
                          {/if}
                          
                          <!-- Tool Call Formatting -->
                          {#if part.function_call || part.functionCall}
                            {@const fc = part.function_call || part.functionCall}
                            <div class="tool-call-box">
                              <details class="tool-details">
                                <summary class="tool-header">
                                  <span class="tool-badge">Step</span>
                                  <span class="tool-title">{getFriendlyToolCall(fc.name, fc.args)}</span>
                                  <span class="details-toggle-icon">▼</span>
                                </summary>
                                <pre class="tool-args">{JSON.stringify(fc.args || {}, null, 2)}</pre>
                              </details>
                            </div>
                          {/if}

                          <!-- Tool Response Formatting -->
                          {#if part.function_response || part.functionResponse}
                            {@const fr = part.function_response || part.functionResponse}
                            <div class="tool-response-box">
                              <details class="tool-details">
                                <summary class="tool-header">
                                  <span class="tool-response-badge">Done</span>
                                  <span class="tool-title">{getFriendlyToolResponse(fr.name, fr.response)}</span>
                                  <span class="details-toggle-icon">▼</span>
                                </summary>
                                <pre class="tool-output">{JSON.stringify(fr.response || {}, null, 2)}</pre>
                              </details>
                            </div>
                          {/if}
                        {/each}
                      {/if}
                    </div>
                  </div>
                {/if}
              {/each}

              {#if isLoading}
                <!-- Blinking/flickering intermediate status ticker -->
                <div class="pulsing-loading-state">
                  <span class="pulse-dot-indicator"></span>
                  <p class="pulse-status-text">{statusText}</p>
                </div>
              {/if}
            </div>
          </div>

          <!-- Floating Chat Input Controls -->
          <footer class="chat-input-bar">
            {#if stagedFiles.length > 0}
              <div class="staged-files-bar">
                {#each stagedFiles as file, index}
                  <div class="staged-file-card">
                    {#if file.preview}
                      <img class="staged-preview-img" src={file.preview} alt="staged img" />
                    {:else}
                      <span class="staged-preview-doc">📄</span>
                    {/if}
                    <div class="staged-info">
                      <span class="staged-name">{file.name}</span>
                    </div>
                    <button class="staged-remove-btn" onclick={() => removeStagedFile(index)}>&times;</button>
                  </div>
                {/each}
              </div>
            {/if}

            <div class="chat-input-row">
              <div class="input-actions">
                <label class="attach-btn" title="Attach files">
                  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
                  </svg>
                  <input type="file" multiple onchange={handleFileSelect} style="display: none;" />
                </label>
              </div>
              
              <textarea 
                bind:this={textareaElement}
                bind:value={queryText}
                onkeydown={handleKeyPress}
                oninput={(e) => {
                  const target = /** @type {HTMLTextAreaElement} */ (e.target);
                  target.style.height = 'auto';
                  target.style.height = (target.scrollHeight) + 'px';
                }}
                placeholder=""
                rows="1"
                disabled={isLoading}
              ></textarea>
              
              <button class="send-btn-large" aria-label="Send Message" onclick={sendMessage} disabled={isLoading || (!queryText.trim() && stagedFiles.length === 0)}>
                <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
                  <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
                </svg>
              </button>
            </div>
          </footer>
        </div>
      {/if}
    </main>
  </div>
</div>

<!-- Premium capabilities modal legend -->
{#if showLegend}
  <div class="modal-backdrop" role="button" tabindex="-1" aria-label="Close legend" onclick={(e) => { if (e.target === e.currentTarget) showLegend = false; }} onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') showLegend = false; }}>
    <div class="modal-card">
      <header class="modal-header">
        <h2>GDG Kraków AI Agents Capabilities</h2>
        <button class="modal-close-btn" onclick={() => showLegend = false}>&times;</button>
      </header>
      
      <div class="modal-body-content">
        <p class="legend-intro">Each AI agent is assigned a unique color marker. During task execution, you will see how they seamlessly coordinate and delegate context to each other:</p>
        
        <div class="legend-grid">
          <!-- Root Orchestrator -->
          <div class="legend-item" style="--border-color: var(--agent-root); --bg-tint: var(--bg-root)">
            <div class="legend-agent-header">
              <span class="legend-color-dot" style="background: var(--agent-root)"></span>
              <h3>Root Orchestrator</h3>
            </div>
            <p class="legend-description">Main agent coordinator. Receives user requests, analyzes user intent, and delegates tasks to specialized sub-agents. Handles general orchestration and instant error processing.</p>
          </div>

          <!-- Receipt Scanner -->
          <div class="legend-item" style="--border-color: var(--agent-receipt); --bg-tint: var(--bg-receipt)">
            <div class="legend-agent-header">
              <span class="legend-color-dot" style="background: var(--agent-receipt)"></span>
              <h3>Receipt Scanner</h3>
            </div>
            <p class="legend-description">Receipt and invoice parser. Natively analyzes images and PDFs, identifies line items, calculates taxes, queries Pekao/NBP exchange rates, and exports clean expense reports directly to Google Docs using official templates.</p>
          </div>

          <!-- Video Editor -->
          <div class="legend-item" style="--border-color: var(--agent-video); --bg-tint: var(--bg-video)">
            <div class="legend-agent-header">
              <span class="legend-color-dot" style="background: var(--agent-video)"></span>
              <h3>Live Video Editor</h3>
            </div>
            <p class="legend-description">Media engineer for speaker card intros. Detects faces in portraits, executes intelligent outpainting to 9:16 ratio, and generates high-fidelity, premium animated video intros using Google Veo.</p>
          </div>

          <!-- LinkedIn Planner -->
          <div class="legend-item" style="--border-color: var(--agent-linkedin); --bg-tint: var(--bg-linkedin)">
            <div class="legend-agent-header">
              <span class="legend-color-dot" style="background: var(--agent-linkedin)"></span>
              <h3>LinkedIn Planner</h3>
            </div>
            <p class="legend-description">Viral social media post generator. Drafts engaging individual speaker announcements (excluding company/position details to preserve anticipation) and comprehensive multi-speaker event recap posts.</p>
          </div>

          <!-- Registrations Manager -->
          <div class="legend-item" style="--border-color: var(--agent-registration); --bg-tint: var(--bg-registration)">
            <div class="legend-agent-header">
              <span class="legend-color-dot" style="background: var(--agent-registration)"></span>
              <h3>Registrations Manager</h3>
            </div>
            <p class="legend-description">Participant list manager. Cleans participant lists, filters duplicates, sorts names across multilingual scripts, and performs phonetic fuzzy matching for organizer directories.</p>
          </div>

          <!-- Event Scheduler -->
          <div class="legend-item" style="--border-color: var(--agent-planner); --bg-tint: var(--bg-planner)">
            <div class="legend-agent-header">
              <span class="legend-color-dot" style="background: var(--agent-planner)"></span>
              <h3>Event Scheduler</h3>
            </div>
            <p class="legend-description">Date planner and conflict detector. Scans Krakow tech schedules on Luma and Meetup.com to avoid scheduling overlaps, cross-references Polish statutory holidays, and highlights potential summer vacation lower attendance risks.</p>
          </div>

          <!-- Agenda Formatter -->
          <div class="legend-item" style="--border-color: var(--agent-agenda); --bg-tint: var(--bg-agenda)">
            <div class="legend-agent-header">
              <span class="legend-color-dot" style="background: var(--agent-agenda)"></span>
              <h3>Agenda Formatter</h3>
            </div>
            <p class="legend-description">Timeline scheduler and visual formatter. Computes precise, minute-by-minute meetup schedules based on speaker slots, coffee breaks, and pizza pauses, automatically rounds finish times, and outputs copy-pasteable summaries.</p>
          </div>

          <!-- Office Secretary -->
          <div class="legend-item" style="--border-color: var(--agent-office); --bg-tint: var(--bg-office)">
            <div class="legend-agent-header">
              <span class="legend-color-dot" style="background: var(--agent-office)"></span>
              <h3>Office Secretary</h3>
            </div>
            <p class="legend-description">Administrative assistant. Drafts polite, template-based email requests to the office team for visitor key access cards and Event Hub space reservations, enforcing mandatory date checks.</p>
          </div>
        </div>
      </div>
      
      <footer class="modal-footer">
        <button class="legend-close-btn" onclick={() => showLegend = false}>Got it</button>
      </footer>
    </div>
  </div>
{/if}

<style>
  /* Premium layout structure */
  .app-layout {
    display: flex;
    flex-direction: column;
    height: 100vh;
    background-color: var(--bg-color);
    color: var(--text-primary);
    transition: background-color var(--transition-normal);
    position: relative;
    overflow: hidden;
  }

  /* Animated aurora mesh gradient that activates when agent is thinking */
  .app-layout::before {
    content: "";
    position: fixed;
    inset: 0;
    background: radial-gradient(circle at 10% 20%, var(--active-agent-color, transparent) 0%, transparent 40%),
                radial-gradient(circle at 90% 80%, var(--accent-color) 0%, transparent 45%),
                radial-gradient(circle at 50% 50%, var(--active-agent-color, transparent) 0%, transparent 35%);
    background-size: 200% 200%;
    filter: blur(120px);
    opacity: 0;
    pointer-events: none;
    z-index: 0;
    transition: opacity 1.8s ease-in-out;
  }

  .app-layout.thinking-active::before {
    opacity: 0.16;
    animation: aurora-mesh 14s ease-in-out infinite alternate;
  }

  @keyframes aurora-mesh {
    0% {
      transform: translate(0, 0) scale(1) rotate(0deg);
      background-position: 0% 0%;
    }
    50% {
      transform: translate(3%, 4%) scale(1.06) rotate(3deg);
      background-position: 50% 100%;
    }
    100% {
      transform: translate(-2%, 2%) scale(0.96) rotate(-2deg);
      background-position: 100% 0%;
    }
  }

  .app-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 24px;
    background-color: var(--panel-bg);
    border-bottom: 1px solid var(--panel-border);
    backdrop-filter: blur(10px);
    z-index: 10;
  }

  .header-logo {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .logo-title h1 {
    font-size: 22px;
    font-weight: 700;
    margin: 0;
    line-height: 1.1;
    letter-spacing: -0.02em;
  }

  .logo-title p {
    font-size: 11px;
    color: var(--text-secondary);
    margin: 4px 0 0;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .active-session-indicator {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    background: var(--bg-root);
    border: 1px solid var(--agent-root);
    color: var(--agent-root);
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    animation: fadeIn var(--transition-normal);
  }

  .pulse-indicator-dot {
    width: 6.5px;
    height: 6.5px;
    border-radius: 50%;
    background-color: var(--agent-root);
    box-shadow: 0 0 0 0 rgba(5, 150, 105, 0.4);
    animation: pulseCircleDot 1.6s infinite ease-in-out;
  }

  @keyframes pulseCircleDot {
    0% {
      transform: scale(0.95);
      box-shadow: 0 0 0 0 rgba(5, 150, 105, 0.7);
    }
    70% {
      transform: scale(1.1);
      box-shadow: 0 0 0 6px rgba(5, 150, 105, 0);
    }
    100% {
      transform: scale(0.95);
      box-shadow: 0 0 0 0 rgba(5, 150, 105, 0);
    }
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .sidebar-toggle-btn {
    background: transparent;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 8px;
    border-radius: 50%;
    transition: background var(--transition-fast), color var(--transition-fast);
    margin-right: 8px;
  }

  .sidebar-toggle-btn:hover, .sidebar-toggle-btn.active {
    background: var(--panel-border);
    color: var(--text-primary);
  }

  .legend-trigger-btn {
    padding: 6px 12px;
    background: transparent;
    color: var(--text-secondary);
    border: 1px solid var(--panel-border);
    border-radius: 20px;
    font-weight: 500;
    font-size: 12px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: background var(--transition-fast), border-color var(--transition-fast), color var(--transition-fast);
  }

  .legend-trigger-btn:hover {
    background: var(--panel-border);
    border-color: var(--text-muted);
    color: var(--text-primary);
  }

  .app-selector-wrapper {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 11.5px;
    color: var(--text-muted);
    background: transparent;
    padding: 5px 12px;
    border-radius: 20px;
    border: 1px solid var(--panel-border);
  }

  .selector-label {
    opacity: 0.7;
    font-weight: 500;
  }

  .app-selector-wrapper select {
    background: transparent;
    color: var(--text-secondary);
    border: none;
    font-weight: 600;
    font-size: 11.5px;
    outline: none;
    cursor: pointer;
    padding: 0 4px;
    margin: 0;
    appearance: none;
    -webkit-appearance: none;
    transition: color var(--transition-fast);
  }

  .app-selector-wrapper select:hover {
    color: var(--text-primary);
  }

  .theme-toggle-btn {
    width: 30px;
    height: 30px;
    background: transparent;
    color: var(--text-secondary);
    border: 1px solid var(--panel-border);
    border-radius: 50%;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background var(--transition-fast), border-color var(--transition-fast), color var(--transition-fast);
  }

  .theme-toggle-btn:hover {
    background: var(--panel-border);
    border-color: var(--text-muted);
    color: var(--text-primary);
  }

  .main-body {
    display: flex;
    flex: 1;
    overflow: hidden;
  }

  /* Sidebar */
  .sidebar {
    width: 300px;
    background-color: var(--panel-bg);
    border-right: 1px solid var(--panel-border);
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    padding: 20px;
    gap: 24px;
    animation: slideInSidebar var(--transition-normal);
  }

  @keyframes slideInSidebar {
    from { width: 0; opacity: 0; }
    to { width: 300px; opacity: 1; }
  }

  .sidebar-section h2 {
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-secondary);
    margin: 0;
  }

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
  }

  .new-session-btn {
    padding: 6px 12px;
    background-color: var(--accent-color);
    color: white;
    border: none;
    border-radius: 6px;
    font-weight: 600;
    font-size: 12px;
    cursor: pointer;
    transition: background var(--transition-fast);
  }

  .new-session-btn:hover {
    background-color: var(--accent-hover);
  }

  .sessions-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .session-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: var(--bg-color);
    border: 1px solid var(--panel-border);
    border-radius: 10px;
    padding: 2px;
    transition: border-color var(--transition-fast);
  }

  .session-card.active {
    border-color: var(--accent-color);
  }

  .session-select-btn {
    flex: 1;
    background: transparent;
    border: none;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px;
    cursor: pointer;
    text-align: left;
    color: var(--text-primary);
  }



  .session-info {
    display: flex;
    flex-direction: column;
  }

  .session-name {
    font-weight: 500;
    font-size: 13px;
  }

  .session-date {
    font-size: 10px;
    color: var(--text-secondary);
  }

  .session-delete-btn {
    background: transparent;
    border: none;
    padding: 6px;
    cursor: pointer;
    opacity: 0.5;
    transition: opacity var(--transition-fast);
  }

  .session-delete-btn:hover {
    opacity: 1;
  }

  .empty-list-text {
    font-size: 12px;
    color: var(--text-secondary);
    text-align: center;
    margin: 16px 0;
  }

  /* Chat workspace main styling */
  .chat-workspace {
    flex: 1;
    background-color: var(--bg-color);
    position: relative;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .drag-overlay {
    position: absolute;
    inset: 0;
    background: var(--accent-glow);
    backdrop-filter: blur(4px);
    z-index: 100;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 3px dashed var(--accent-color);
    margin: 12px;
    border-radius: 16px;
    pointer-events: none;
  }

  .drag-message {
    text-align: center;
    color: var(--accent-color);
  }

  .drag-emoji {
    font-size: 48px;
  }

  .drag-message h3 {
    margin: 12px 0 4px;
    font-size: 20px;
    font-weight: 600;
  }

  .welcome-container {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 40px;
    text-align: center;
    max-width: 600px;
    margin: 0 auto;
  }

  .welcome-container h2 {
    font-size: 32px;
    font-weight: 700;
    margin: 0 0 12px;
    letter-spacing: -0.02em;
  }

  .welcome-container p {
    color: var(--text-secondary);
    margin-bottom: 32px;
    line-height: 1.5;
    font-size: 15px;
  }

  .start-btn {
    padding: 12px 28px;
    background-color: var(--accent-color);
    color: white;
    border: none;
    border-radius: 10px;
    font-weight: 600;
    cursor: pointer;
    font-size: 15px;
    box-shadow: 0 4px 12px var(--accent-glow);
    transition: background var(--transition-fast);
  }

  .start-btn:hover {
    background-color: var(--accent-hover);
  }

  /* Chat workspace scroll */
  .chat-container {
    flex: 1;
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
    position: relative;
  }

  .loading-progress-bar {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3.5px;
    background: linear-gradient(90deg, transparent 0%, var(--active-agent-color, var(--accent-color)) 50%, transparent 100%);
    background-size: 200% 100%;
    animation: progressMove 1.8s infinite linear;
    z-index: 5;
  }

  @keyframes progressMove {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }

  .chat-body {
    flex: 1;
    overflow-y: auto;
    padding: 32px 32px 140px 32px;
    display: flex;
    flex-direction: column;
    gap: 24px;
  }

  .chat-feed-wrapper {
    max-width: 720px;
    width: 100%;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: 24px;
    position: relative;
    z-index: 1;
  }

  .chat-empty-state {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-secondary);
    font-size: 14px;
    text-align: center;
    max-width: 420px;
    margin: auto;
    line-height: 1.5;
  }

  .message-wrapper {
    display: flex;
    flex-direction: column;
    max-width: 90%;
    animation: fadeIn var(--transition-normal);
  }

  .user-msg {
    align-self: flex-end;
    align-items: flex-end;
  }

  .agent-msg {
    align-self: flex-start;
    align-items: flex-start;
  }

  .message-bubble {
    font-size: 14.5px;
    line-height: 1.6;
  }

  .user-msg .message-bubble {
    background-color: var(--chat-bubble-user);
    color: var(--chat-bubble-user-text);
    border-radius: 20px;
    padding: 12px 18px;
    box-shadow: var(--shadow-sm);
  }

  .agent-msg .message-bubble {
    background-color: var(--panel-bg);
    color: var(--text-primary);
    border: 1px solid var(--panel-border);
    border-radius: 18px;
    padding: 16px 20px;
    box-shadow: var(--shadow-sm);
    width: 100%;
    transition: border-color var(--transition-normal), box-shadow var(--transition-normal);
  }

  .agent-msg .message-bubble:hover {
    border-color: var(--agent-color);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
  }

  .avatar-lbl {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 4px;
  }

  /* Simplified delegation badge */
  .delegation-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 5px 12px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 500;
    margin-bottom: 8px;
    text-transform: uppercase;
    letter-spacing: 0.02em;
    border: 1px solid rgba(0,0,0,0.03);
    animation: slideIn var(--transition-fast);
  }

  .badge-label {
    font-weight: 500;
  }

  .badge-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    display: inline-block;
    animation: pulseGlow 1.5s infinite ease-in-out;
  }

  /* Tool blocks */
  .tool-call-box, .tool-response-box {
    margin-top: 10px;
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid var(--panel-border);
    font-size: 13px;
    width: 100%;
  }

  .tool-details {
    width: 100%;
  }

  .tool-header {
    cursor: pointer;
    user-select: none;
    list-style: none;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background: var(--bg-color);
  }

  .tool-header::-webkit-details-marker {
    display: none;
  }

  .tool-details[open] .tool-header {
    border-bottom: 1px solid var(--panel-border);
  }

  .tool-title {
    flex: 1;
    font-weight: 500;
    color: var(--text-primary);
  }

  .details-toggle-icon {
    font-size: 10px;
    color: var(--text-muted);
    transition: transform var(--transition-fast);
  }

  .tool-details[open] .details-toggle-icon {
    transform: rotate(180deg);
  }

  .tool-badge, .tool-response-badge {
    font-size: 10px;
    font-weight: 600;
    padding: 2px 6px;
    border-radius: 4px;
    color: white;
  }

  .tool-badge {
    background: #4b5563;
  }

  .tool-response-badge {
    background: #059669;
  }

  .tool-args, .tool-output {
    margin: 0;
    padding: 10px;
    overflow-x: auto;
    background: var(--bg-color);
    color: var(--text-secondary);
    max-height: 200px;
  }

  /* Staged Files Bar styling */
  .staged-files-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    padding: 8px 12px;
    border-bottom: 1px solid var(--panel-border);
    margin-bottom: 8px;
    width: 100%;
  }

  .staged-file-card {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 8px;
    border: 1px solid var(--panel-border);
    background: rgba(255, 255, 255, 0.03);
    border-radius: 8px;
    font-size: 11px;
  }

  .staged-preview-img {
    width: 20px;
    height: 20px;
    object-fit: cover;
    border-radius: 4px;
  }

  .staged-preview-doc {
    font-size: 14px;
  }

  .staged-info {
    max-width: 120px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .staged-remove-btn {
    background: transparent;
    border: none;
    cursor: pointer;
    font-size: 12px;
    opacity: 0.6;
    padding: 0 2px;
  }

  .staged-remove-btn:hover {
    opacity: 1;
  }

  /* Chat Input footer styling (Floating glass pill) */
  .chat-input-bar {
    display: flex;
    flex-direction: column;
    position: absolute;
    bottom: 28px;
    left: 50%;
    transform: translateX(-50%);
    width: calc(100% - 48px);
    max-width: 720px;
    background-color: var(--input-bg);
    border: 1px solid var(--panel-border);
    border-radius: 24px;
    padding: 8px 12px;
    box-shadow: var(--shadow-lg);
    backdrop-filter: blur(20px);
    z-index: 10;
    transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
  }

  .chat-input-bar:focus-within {
    border-color: var(--accent-color);
    box-shadow: 0 12px 30px -10px var(--accent-glow), var(--shadow-lg);
  }

  .chat-input-row {
    display: flex;
    align-items: center;
    width: 100%;
    gap: 8px;
  }

  .attach-btn {
    font-size: 20px;
    cursor: pointer;
    opacity: 0.6;
    transition: opacity var(--transition-fast);
    padding: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .attach-btn:hover {
    opacity: 1;
  }

  .chat-input-bar textarea {
    flex: 1;
    background: transparent;
    color: var(--text-primary);
    border: none;
    padding: 8px 12px;
    resize: none;
    outline: none;
    font-size: 14.5px;
    line-height: 1.5;
    max-height: 160px;
    font-family: inherit;
  }

  .send-btn-large {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background-color: var(--accent-color);
    border: none;
    color: white;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background var(--transition-fast), transform var(--transition-fast);
    flex-shrink: 0;
  }

  .send-btn-large:hover:not(:disabled) {
    background-color: var(--accent-hover);
    transform: scale(1.05);
  }

  .send-btn-large:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  /* Errors Banner styling */
  .error-banner {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 24px;
    background-color: var(--danger-bg);
    border-bottom: 1px solid var(--danger-color);
    color: var(--danger-color);
    font-size: 14px;
    animation: fadeIn var(--transition-fast);
  }

  .error-close {
    background: transparent;
    border: none;
    color: var(--danger-color);
    font-size: 20px;
    cursor: pointer;
    margin-left: auto;
  }

  /* Pulsating Intermediate status tracker ("some activity is in progress") */
  .pulsing-loading-state {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 12px 18px;
    background: var(--panel-bg);
    border: 1px solid var(--panel-border);
    border-radius: 12px;
    max-width: max-content;
    animation: fadeIn var(--transition-fast);
    box-shadow: var(--shadow-sm);
  }

  .pulse-dot-indicator {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: var(--active-agent-color, var(--accent-color));
    animation: pulseCircle 1.2s infinite ease-in-out;
  }

  .pulse-status-text {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-secondary);
    margin: 0;
    animation: statusBlink 1.8s infinite ease-in-out;
  }

  /* Modal Capabilities Legend styles */
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.4);
    backdrop-filter: blur(8px);
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
    animation: fadeIn var(--transition-fast);
    padding: 24px;
  }

  .modal-card {
    background: var(--panel-bg);
    border: 1px solid var(--panel-border);
    border-radius: 20px;
    width: 840px;
    max-width: 100%;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: var(--shadow-lg);
    animation: modalSlideIn var(--transition-normal);
  }

  @keyframes modalSlideIn {
    from { transform: scale(0.95) translateY(12px); opacity: 0; }
    to { transform: scale(1) translateY(0); opacity: 1; }
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 24px;
    border-bottom: 1px solid var(--panel-border);
  }

  .modal-header h2 {
    font-size: 20px;
    font-weight: 700;
    margin: 0;
  }

  .modal-close-btn {
    background: transparent;
    border: none;
    font-size: 28px;
    cursor: pointer;
    color: var(--text-secondary);
    line-height: 0.8;
  }

  .modal-body-content {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
  }

  .legend-intro {
    font-size: 14.5px;
    color: var(--text-secondary);
    margin: 0 0 24px;
    line-height: 1.5;
  }

  .legend-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    @media (max-width: 768px) {
      grid-template-columns: 1fr;
    }
  }

  .legend-item {
    padding: 16px;
    border-radius: 12px;
    border: 1px solid var(--panel-border);
    border-left: 5px solid var(--border-color);
    background: var(--bg-tint);
  }

  .legend-agent-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
  }

  .legend-color-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }

  .legend-agent-header h3 {
    font-size: 15px;
    font-weight: 600;
    margin: 0;
  }

  .legend-description {
    font-size: 13px;
    color: var(--text-secondary);
    margin: 0;
    line-height: 1.45;
  }

  .modal-footer {
    padding: 16px 24px;
    border-top: 1px solid var(--panel-border);
    display: flex;
    justify-content: flex-end;
  }

  .legend-close-btn {
    padding: 10px 24px;
    background-color: var(--accent-color);
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    cursor: pointer;
    font-size: 14.5px;
    transition: background var(--transition-fast);
  }

  .legend-close-btn:hover {
    background-color: var(--accent-hover);
  }

  /* Keyframe animations */
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
  }

  @keyframes pulseGlow {
    0%, 100% { opacity: 0.6; transform: scale(1); }
    50% { opacity: 1; transform: scale(1.15); }
  }

  @keyframes slideIn {
    from { transform: scale(0.9) translateY(2px); opacity: 0; }
    to { transform: scale(1) translateY(0); opacity: 1; }
  }

  @keyframes pulseCircle {
    0%, 100% { transform: scale(0.95); opacity: 0.65; }
    50% { transform: scale(1.15); opacity: 1; }
  }

  @keyframes statusBlink {
    0%, 100% { opacity: 0.6; }
    50% { opacity: 1; }
  }

  /* Premium Markdown Body Styles inside Chat Bubbles */
  .markdown-body {
    font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 14.5px;
    line-height: 1.625;
    color: var(--text-primary);
  }
  .markdown-body :global(p) {
    margin: 0 0 10px 0;
    line-height: 1.625;
    font-weight: 400;
  }
  .markdown-body :global(p:last-child) {
    margin-bottom: 0;
  }
  .markdown-body :global(strong) {
    font-weight: 600;
  }
  .markdown-body :global(em) {
    font-style: italic;
  }
  .markdown-body :global(ul), .markdown-body :global(ol) {
    margin: 8px 0;
    padding-left: 20px;
    line-height: 1.45;
  }
  .markdown-body :global(li) {
    margin-bottom: 4px;
  }
  .markdown-body :global(h1), .markdown-body :global(h2), .markdown-body :global(h3),
  .markdown-body :global(h4), .markdown-body :global(h5), .markdown-body :global(h6) {
    margin: 16px 0 8px 0;
    font-weight: 600;
    line-height: 1.25;
    color: var(--text-primary);
  }
  .markdown-body :global(h1) { font-size: 1.4em; }
  .markdown-body :global(h2) { font-size: 1.25em; }
  .markdown-body :global(h3) { font-size: 1.15em; }
  .markdown-body :global(h4) { font-size: 1em; }
  
  .markdown-body :global(code) {
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.9em;
    padding: 3px 6px;
    background-color: var(--panel-border);
    border-radius: 6px;
    color: var(--accent-color);
  }
  .markdown-body :global(pre) {
    margin: 12px 0;
    padding: 14px;
    background-color: var(--bg-color);
    border: 1px solid var(--panel-border);
    border-radius: 8px;
    overflow-x: auto;
  }
  .markdown-body :global(pre code) {
    padding: 0;
    background-color: transparent;
    border-radius: 0;
    color: var(--text-primary);
    font-size: 13.5px;
  }
  .markdown-body :global(blockquote) {
    margin: 12px 0;
    padding-left: 14px;
    border-left: 4px solid var(--accent-color);
    color: var(--text-secondary);
    font-style: italic;
  }
  .markdown-body :global(a) {
    color: var(--accent-color);
    text-decoration: none;
    font-weight: 500;
  }
  .markdown-body :global(a:hover) {
    text-decoration: underline;
  }
  .markdown-body :global(table) {
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0;
    font-size: 13.5px;
  }
  .markdown-body :global(th), .markdown-body :global(td) {
    border: 1px solid var(--panel-border);
    padding: 8px 12px;
    text-align: left;
  }
  .markdown-body :global(th) {
    background-color: var(--panel-bg);
    font-weight: 600;
  }

  /* Variant Card Styles inside Chat Bubbles */
  .variants-container {
    display: flex;
    flex-direction: column;
    gap: 16px;
    width: 100%;
    margin-top: 8px;
  }

  .variant-card {
    background: var(--panel-bg);
    border: 1px solid var(--panel-border);
    border-radius: 12px;
    padding: 16px 20px;
    box-shadow: var(--shadow-sm);
    transition: transform var(--transition-fast), border-color var(--transition-fast), box-shadow var(--transition-fast);
  }

  .variant-card:hover {
    transform: translateY(-2px);
    border-color: var(--accent-color);
    box-shadow: var(--shadow-md);
  }

  .variant-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid var(--panel-border);
    padding-bottom: 10px;
    margin-bottom: 12px;
  }

  .variant-badge {
    font-size: 11px;
    font-weight: 500;
    color: var(--agent-color, var(--accent-color));
    background: var(--agent-bg, var(--accent-glow));
    padding: 4px 10px;
    border-radius: 12px;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .card-header-actions {
    display: flex;
    gap: 8px;
  }

  .action-card-btn {
    background: var(--bg-color);
    border: 1px solid var(--panel-border);
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 12px;
    font-weight: 500;
    color: var(--text-primary);
    cursor: pointer;
    transition: all var(--transition-fast);
  }

  .action-card-btn:hover {
    background: var(--panel-border);
    border-color: var(--accent-color);
    color: var(--accent-hover);
  }

</style>
