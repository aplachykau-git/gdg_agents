<script>
  import { onMount } from 'svelte';
  import { marked } from 'marked';
  import { 
    Sparkles, 
    History, 
    Plus, 
    Trash2, 
    Paperclip, 
    Sun, 
    Moon, 
    Check, 
    Copy, 
    ChevronDown, 
    ChevronRight, 
    Bot, 
    User, 
    CornerDownLeft, 
    FileText, 
    Image as ImageIcon, 
    RefreshCw, 
    X, 
    Sparkle, 
    Braces, 
    Layers,
    HelpCircle,
    Play,
    Terminal,
    ArrowRight,
    Receipt,
    Video,
    Share2,
    Users,
    Calendar,
    Clock,
    Mail,
    Workflow,
    ArrowUpRight,
    AlertCircle
  } from '@lucide/svelte';
  import AgendaTimeline from './lib/AgendaTimeline.svelte';
  import AgentGraph from './lib/AgentGraph.svelte';

  // Markdown rendering helper
  function renderMarkdown(text) {
    if (!text) return '';
    try {
      return marked.parse(text);
    } catch (e) {
      console.error("Failed to parse markdown:", e);
      return text.replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }
  }

  // Default GDG Agents
  const DEFAULT_APPS = [
    { name: 'root_agent', root_agent_name: 'Root Orchestrator' },
    { name: 'receipt_scanner', root_agent_name: 'Receipt Scanner' },
    { name: 'video_editor', root_agent_name: 'Live Video Editor' },
    { name: 'linkedin_post_generator', root_agent_name: 'LinkedIn Planner' },
    { name: 'registration_manager', root_agent_name: 'Registrations Manager' },
    { name: 'event_planner', root_agent_name: 'Event Scheduler' },
    { name: 'agenda_generator', root_agent_name: 'Agenda Formatter' },
    { name: 'office_secretary', root_agent_name: 'Office Secretary' }
  ];

  // State Variables
  let apps = $state.raw(DEFAULT_APPS);
  let selectedApp = $state('root_agent');
  let userId = $state('user');
  let sessions = $state.raw([]);
  let selectedSessionId = $state('');
  let events = $state.raw([]);
  let queryText = $state('');
  let isLoading = $state(false);
  let errorMsg = $state('');
  let isDarkMode = $state(true);
  
  // Layout Panels & Drawers
  let showSessions = $state(true); // Left panel
  let showLegend = $state(false);   // Capabilities modal
  let showAgentGraph = $state(false); // Multi-agent DAG modal
  
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
      document.documentElement.setAttribute('data-theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      document.documentElement.setAttribute('data-theme', 'light');
    }
  }

  // Load Apps from ADK backend
  async function loadApps() {
    try {
      const res = await fetch('/list-apps');
      if (!res.ok) throw new Error(`Status ${res.status}`);
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
      } else if (data.apps) {
        apps = data.apps;
      }
      await loadSessions();
    } catch (e) {
      console.warn("Backend not active on port 8080. Loaded default agent catalog.");
      apps = DEFAULT_APPS;
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
      const lastErrEvent = events.slice().reverse().find(e => getEventError(e));
      if (lastErrEvent) {
        const err = getEventError(lastErrEvent);
        errorMsg = err.message;
      }
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

  // Handle Drag & Drop with counter to prevent child-element flicker
  let dragCounter = 0;

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

  // Cycle through intermediate agent status text while loading
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
        'Scanning attachment with Vision OCR...',
        'Converting expenses to EUR/USD/PLN...',
        'Checking historical structures (Anti-re-processing)...',
        'Translating item details to English...',
        'Generating Docs Expense Report...'
      ],
      video_editor: [
        'Staging uploaded portrait in staged_media...',
        'Detecting face landmarks...',
        'Executing smart Outpainting to 9:16 aspect ratio...',
        'Crafting cinematic Veo video prompt...',
        'Generating 8s video intro via Veo...',
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
        'Searching local Luma AI meetup calendar...',
        'Scanning Meetup.com for local tech conflicts...',
        'Checking statutory public holidays...',
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
    
    const list = statuses[app] || ['Processing request...', 'Executing agent logic...', 'Invoking external tool pipeline...'];
    let idx = 0;
    statusText = list[0];
    
    clearInterval(statusInterval);
    statusInterval = setInterval(() => {
      idx = (idx + 1) % list.length;
      statusText = list[idx];
    }, 2200);
  }

  let currentExecutingAgent = $state('root_agent');

  function getSubAgentForTool(toolName) {
    if (!toolName) return null;
    const t = toolName.toLowerCase();
    if (t.includes('video') || t.includes('portrait') || t.includes('composer') || t.includes('animate') || t.includes('stage_uploaded_media')) return 'video_editor';
    if (t.includes('receipt') || t.includes('invoice') || t.includes('rate') || t.includes('pekao') || t.includes('read_receipt_file') || t.includes('export_summary')) return 'receipt_scanner';
    if (t.includes('linkedin') || t.includes('post')) return 'linkedin_post_generator';
    if (t.includes('registration') || t.includes('organizer')) return 'registration_manager';
    if (t.includes('planner') || t.includes('meetup') || t.includes('holiday')) return 'event_planner';
    if (t.includes('agenda') || t.includes('timeline')) return 'agenda_generator';
    if (t.includes('office') || t.includes('secretary') || t.includes('email')) return 'office_secretary';
    return null;
  }

  function shouldShowDelegationHandoff(event, idx, allEvents) {
    if (!event || event.author === 'user') return false;
    const currentAuthor = cleanAuthorName(event.author).toLowerCase();
    if (!currentAuthor || currentAuthor === 'root_agent' || currentAuthor === 'root') return false;
    
    // Find the previous non-user event
    for (let i = idx - 1; i >= 0; i--) {
      const prev = allEvents[i];
      if (prev && prev.author !== 'user') {
        const prevAuthor = cleanAuthorName(prev.author).toLowerCase();
        return prevAuthor !== currentAuthor;
      }
    }
    return true;
  }

  // Maps backend tool names to user-friendly log descriptions
  function getFriendlyToolCall(name, args) {
    const mappings = {
      // Sub-agent transfers
      transfer_to_video_editor: () => "🔄 Delegating task to Live Video Editor (A2A)...",
      transfer_to_receipt_scanner: () => "🔄 Delegating task to Receipt Scanner (A2A)...",
      transfer_to_linkedin_post_generator: () => "🔄 Delegating task to LinkedIn Planner...",
      transfer_to_event_planner: () => "🔄 Delegating task to Event Scheduler...",
      transfer_to_registration_manager: () => "🔄 Delegating task to Registrations Manager...",
      transfer_to_agenda_generator: () => "🔄 Delegating task to Agenda Formatter...",
      transfer_to_office_secretary: () => "🔄 Delegating task to Office Secretary...",

      // Video Editor tools
      verify_portrait_photo: () => "🔍 Running facial detection on portrait photo...",
      stage_uploaded_media: () => "📦 Staging uploaded media to workspace assets...",
      animate_photo: () => "🎬 Outpainting to 9:16 & generating Veo video intro...",
      update_composer: (a) => `🎨 Updating HTML5 composition layout for "${a.name || 'speaker'}"...`,
      render_composer: () => "🚀 HyperFrames compiler rendering final video (MP4, GIF, 4K)...",
      validate_metadata: (a) => `📐 Validating text character limits for "${a.name || 'speaker'}"...`,

      // Receipt Scanner tools
      get_usd_pln_rate: () => "💱 Fetching live Pekao Bank & NBP exchange rates (USD/PLN)...",
      read_receipt_file: () => "🧾 Analyzing receipt image via Gemini 2.5 Pro Vision OCR...",
      export_summary_to_google_doc: () => "📄 Exporting approved expense report to Google Docs...",
      scan_receipt_with_vision: () => "🧾 Extracting items and taxes via Vision OCR...",
      convert_currency: () => "💱 Converting currencies to PLN using exchange rates...",
      export_to_google_docs: () => "📄 Exporting expense report to Google Docs template...",

      // Other tools
      filter_and_clean_registrations: () => "👥 Cleaning, deduplicating, and partitioning registrations...",
      find_optimal_meetup_date: () => "📅 Scanning Kraków calendars, holidays, and meetup conflicts...",
      generate_agenda: () => "⏱️ Formatting structured timeline and speaker agenda...",
      generate_office_email: () => "✉️ Drafting office access and event reservation email..."
    };

    if (mappings[name]) {
      return mappings[name](args || {});
    }
    const formatted = name.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
    return `Executing ${formatted}...`;
  }

  function getEventError(event) {
    if (!event) return null;
    const errMsg = event.errorMessage || event.error_message || (typeof event.error === 'object' ? (event.error?.message || event.error?.detail || event.error?.error || JSON.stringify(event.error)) : event.error);
    const errCode = event.errorCode || event.error_code || (typeof event.error === 'object' ? event.error?.code : null);
    if (errMsg || errCode) {
      return {
        message: errMsg || 'An error occurred during execution.',
        code: errCode || ''
      };
    }
    if (event.status === 'error') {
      return {
        message: event.status_message || event.statusMessage || event.detail || 'Execution failed with error status.',
        code: 'ERROR_STATUS'
      };
    }
    return null;
  }

  function isToolResponseError(response) {
    if (!response) return false;
    if (typeof response === 'object') {
      if (response.error || response.error_message || response.errorMessage || response.exception) {
        return true;
      }
      if (response.status === 'error' || response.success === false) {
        return true;
      }
    }
    if (typeof response === 'string') {
      const lower = response.toLowerCase();
      if (lower.startsWith('error:') || lower.startsWith('exception:') || lower.includes('traceback (most recent call last)')) {
        return true;
      }
    }
    return false;
  }

  function getToolErrorMessage(response) {
    if (!response) return 'Tool execution failed';
    if (typeof response === 'object') {
      return response.error || response.error_message || response.errorMessage || response.exception || response.detail || JSON.stringify(response);
    }
    return String(response);
  }

  function getFriendlyToolResponse(name, response, args) {
    if (isToolResponseError(response)) {
      return `❌ Tool error: ${getToolErrorMessage(response)}`;
    }
    const mappings = {
      transfer_to_video_editor: () => "Workflow handed off to Live Video Editor (A2A).",
      transfer_to_receipt_scanner: () => "Workflow handed off to Receipt Scanner (A2A).",
      transfer_to_linkedin_post_generator: () => "Workflow handed off to LinkedIn Planner.",
      transfer_to_event_planner: () => "Workflow handed off to Event Scheduler.",
      transfer_to_registration_manager: () => "Workflow handed off to Registrations Manager.",
      transfer_to_agenda_generator: () => "Workflow handed off to Agenda Formatter.",
      transfer_to_office_secretary: () => "Workflow handed off to Office Secretary.",

      verify_portrait_photo: () => "Face verification passed successfully.",
      stage_uploaded_media: () => "Media asset staged to workspace.",
      animate_photo: () => "Veo video generation and outpainting completed.",
      update_composer: () => "Composition HTML canvas updated with new parameters.",
      render_composer: () => "All requested files compiled and saved to renders/ folder.",
      validate_metadata: () => "Text length validation passed.",
      get_usd_pln_rate: () => "Pekao bank rate successfully retrieved.",
      read_receipt_file: () => "Receipt items and amounts extracted successfully.",
      export_summary_to_google_doc: () => "Google Doc expense report created.",
      scan_receipt_with_vision: () => "Receipt items and taxes extracted successfully.",
      convert_currency: () => "Exchange rates converted.",
      export_to_google_docs: () => "Document created in Google Docs folder.",
      filter_and_clean_registrations: () => "Registrations verified and partitioned.",
      find_optimal_meetup_date: () => "Calendar dates analyzed.",
      generate_agenda: () => "Agenda timeline created.",
      generate_office_email: () => "Email template generated."
    };

    if (mappings[name]) {
      return mappings[name](response || {}, args || {});
    }
    return "Step completed successfully.";
  }

  function cleanAuthorName(author) {
    if (!author) return '';
    return author.replace(/^Active Context:\s*/i, '').trim();
  }

  let copiedId = $state('');
  
  // Detect if text output is an agenda timeline from agenda_generator or root_agent delegation
  function isAgendaOutput(text, author) {
    if (!text) return false;
    const clean = cleanAuthorName(author).toLowerCase();
    const hasAgendaKeyword = text.toUpperCase().includes('AGENDA');
    const hasTimePattern = /\d{1,2}:\d{2}\s*[-–—]/.test(text);
    const hasAgendaEmojis = text.includes('🎟️') || text.includes('🚀') || text.includes('🎤') || text.includes('🍕');
    
    if (clean.includes('agenda') && (hasTimePattern || hasAgendaKeyword)) return true;
    if (hasAgendaKeyword && hasTimePattern && hasAgendaEmojis) return true;
    return false;
  }

  // Parse response into separate variants/options if they exist
  function parseResponseVariants(text, author) {
    if (!text) return [];
    const clean = cleanAuthorName(author).toLowerCase();
    
    const isSpecialApp = clean.includes('linkedin') || clean.includes('post_generator') || clean.includes('agenda') || clean.includes('agenda_generator') || /variant\s*\d+/i.test(text) || /option\s*\d+/i.test(text) || text.toLowerCase().includes('recap');
    
    if (!isSpecialApp) {
      return [{ header: '', body: text }];
    }
    
    const regex = /(?:^|\n)((?:###?\s*|##\s*|#\s*|\*\*|)\s*(?:Event Recap Post|Event Recap|Recap|Variant|Option|Agenda)\s*(?:Variant|Option)?\s*\d*[:\s\-\(]*[^\n]*)/iu;
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
      header = header.replace(/^(?:###?|##|#)\s*/, '').trim();
      header = header.replace(/^\*\*|\*\*$/g, '').trim();
      const body = parts[i + 1] ? parts[i + 1].trim() : '';
      
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
    
    return variants.length > 0 ? variants : [{ header: '', body: text }];
  }

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

  function refineVariant(bodyText) {
    const cleanBody = bodyText.trim();
    // Quote lines with markdown blockquote to prevent accidental Setext header parsing
    const quoted = cleanBody.split('\n').map(l => `> ${l}`).join('\n');
    queryText = `Please refine the following option:\n\n${quoted}\n\nMy adjustments:\n`;
    setTimeout(() => {
      if (textareaElement) {
        textareaElement.style.height = 'auto';
        textareaElement.style.height = (textareaElement.scrollHeight) + 'px';
        textareaElement.focus();
      }
    }, 50);
  }

  function isIntermediateEvent(event) {
    if (!event) return true;
    if (event.author === 'user') return false;
    if (getEventError(event)) return false;
    if (!event.content || !event.content.parts) return true;
    return false;
  }

  let filteredEvents = $derived(events.filter(e => !isIntermediateEvent(e)));

  // Run orchestrator / Send message
  async function sendMessage() {
    if (!queryText.trim() && stagedFiles.length === 0) return;

    if (!selectedSessionId) {
      const newSessionId = `session_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
      try {
        await fetch(`/apps/${selectedApp}/users/${userId}/sessions`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: newSessionId })
        });
        selectedSessionId = newSessionId;
        loadSessions();
      } catch (err) {
        selectedSessionId = newSessionId;
      }
    }

    const currentText = queryText;
    const currentFiles = [...stagedFiles];
    
    queryText = '';
    if (textareaElement) {
      textareaElement.style.height = 'auto';
    }
    stagedFiles = [];
    errorMsg = '';
    currentExecutingAgent = selectedApp || 'root_agent';
    isLoading = true;
    startStatusTicker(selectedApp);

    try {
      const parts = [];
      
      currentFiles.forEach(f => {
        parts.push({
          inline_data: {
            mime_type: f.type,
            data: f.data
          }
        });
      });

      if (currentText.trim()) {
        parts.push({ text: currentText });
      }

      // Immediately display user message & attachments in the chat stream
      events = [
        ...events,
        {
          author: 'user',
          content: { parts: parts },
          timestamp: Date.now() / 1000
        }
      ];
      scrollToBottom();

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
          if (res.status === 404) {
            useSSE = false;
          } else {
            let errDetail = '';
            try {
              const errJson = await res.json();
              errDetail = errJson.detail || errJson.message || errJson.errorMessage || errJson.error_message || JSON.stringify(errJson);
            } catch (_) {
              errDetail = await res.text().catch(() => '');
            }
            throw new Error(errDetail || `Backend server error (${res.status} ${res.statusText})`);
          }
        }
      } catch (err) {
        if (!useSSE) {
          // fallback to non-streaming /run
        } else {
          throw err;
        }
      }

      if (!useSSE) {
        payload.streaming = false;
        res = await fetch('/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!res.ok) {
          let errDetail = '';
          try {
            const errJson = await res.json();
            errDetail = errJson.detail || errJson.message || errJson.errorMessage || errJson.error_message || JSON.stringify(errJson);
          } catch (_) {
            errDetail = await res.text().catch(() => '');
          }
          throw new Error(errDetail || `Backend server error (${res.status} ${res.statusText})`);
        }
        await selectSession(selectedSessionId);
      } else {
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
                const eventErr = getEventError(eventObj);
                if (eventErr) {
                  eventObj.errorMessage = eventErr.message;
                  eventObj.errorCode = eventErr.code;
                  errorMsg = `Execution Error (${eventObj.author || 'Agent'}): ${eventErr.message}`;
                  events = [...events, eventObj];
                  scrollToBottom();
                  continue;
                }

                if (eventObj.author && eventObj.author !== 'user') {
                  currentExecutingAgent = eventObj.author;
                }

                // Progressive real-time update in chat UI
                if (eventObj.author === 'user') {
                  const lastUserIdx = events.findLastIndex(e => e.author === 'user' && !e.id);
                  if (lastUserIdx !== -1) {
                    events[lastUserIdx] = eventObj;
                    events = [...events];
                  }
                } else if (eventObj.id) {
                  const existingIdx = events.findIndex(e => e.id === eventObj.id);
                  if (existingIdx !== -1) {
                    events[existingIdx] = eventObj;
                    events = [...events];
                  } else {
                    events = [...events, eventObj];
                  }
                  scrollToBottom();
                } else if (eventObj.content || getEventError(eventObj)) {
                  events = [...events, eventObj];
                  scrollToBottom();
                }

                if (eventObj.content && eventObj.content.parts) {
                  for (const part of eventObj.content.parts) {
                    const fc = part.function_call || part.functionCall;
                    const fr = part.function_response || part.functionResponse;
                    if (fc) {
                      const delegated = getSubAgentForTool(fc.name);
                      if (delegated) {
                        currentExecutingAgent = delegated;
                      }
                      const agentLabel = getAgentTheme(currentExecutingAgent || eventObj.author).label || eventObj.author;
                      statusText = `${agentLabel}: ${getFriendlyToolCall(fc.name, fc.args)}`;
                    } else if (fr) {
                      const delegated = getSubAgentForTool(fr.name);
                      if (delegated) {
                        currentExecutingAgent = delegated;
                      }
                      const agentLabel = getAgentTheme(currentExecutingAgent || eventObj.author).label || eventObj.author;
                      statusText = `${agentLabel}: ${getFriendlyToolResponse(fr.name, fr.response)}`;
                      if (isToolResponseError(fr.response)) {
                        errorMsg = `Tool Error (${fr.name}): ${getToolErrorMessage(fr.response)}`;
                      }
                    } else if (part.text) {
                      const agentLabel = getAgentTheme(eventObj.author || currentExecutingAgent).label || eventObj.author;
                      statusText = `${agentLabel} generating response...`;
                    }
                  }
                }
              } catch (parseErr) {
                console.warn('SSE event parse warning:', parseErr);
              }
            }
          }
        }
      }
    } catch (e) {
      console.error(e);
      let displayError = e.message || 'An unexpected execution error occurred.';
      try {
        const parsed = JSON.parse(e.message);
        if (parsed.detail) {
          displayError = parsed.detail;
        } else if (parsed.errorMessage) {
          displayError = parsed.errorMessage;
        } else if (parsed.error_message) {
          displayError = parsed.error_message;
        }
      } catch(_) {}
      
      errorMsg = displayError.startsWith('Execution Error:') ? displayError : `Execution Error: ${displayError}`;
      
      // Append an error card to chat thread if not already there
      const lastEvt = events[events.length - 1];
      const lastErr = getEventError(lastEvt);
      if (!lastErr || lastErr.message !== displayError) {
        const errorEvent = {
          author: currentExecutingAgent || selectedApp || 'system',
          errorMessage: displayError,
          errorCode: 'EXECUTION_ERROR',
          timestamp: Date.now() / 1000
        };
        events = [...events, errorEvent];
      }
    } finally {
      isLoading = false;
      clearInterval(statusInterval);
      scrollToBottom();
    }
  }

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
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey || !e.shiftKey)) {
      e.preventDefault();
      sendMessage();
    }
  }

  onMount(() => {
    document.documentElement.classList.add('dark');
    document.documentElement.setAttribute('data-theme', 'dark');
    loadApps();
  });

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
    
    const formatted = clean.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
    return { color: 'var(--primary-accent)', bg: 'rgba(138, 180, 248, 0.1)', label: formatted };
  }

  const activeAgentTheme = $derived(getAgentTheme(selectedApp));
</script>

<div class="studio-layout" class:thinking-active={isLoading} style="--active-agent-color: {activeAgentTheme.color}">
  
  <!-- =========================================================================
   * TOP APP BAR (Google AI Studio Header)
   * ========================================================================= -->
  <header class="studio-header">
    <div class="header-left">
      <!-- Left sidebar toggle -->
      <button 
        class="icon-btn" 
        class:active={showSessions} 
        onclick={() => showSessions = !showSessions} 
        title="Toggle History Drawer"
      >
        <History size={18} strokeWidth={1.75} />
      </button>

      <!-- GDG Agents Logo -->
      <div class="brand-badge">
        <div class="brand-gemini-icon">
          <Sparkles size={16} strokeWidth={2} class={isLoading ? 'generating-sparkle' : ''} />
        </div>
        <div class="brand-text">
          <span class="brand-name">GDG Agents</span>
          <span class="brand-sub">Autonomous Platform</span>
        </div>
      </div>

      <div class="header-divider"></div>

      <!-- Breadcrumbs & Active App -->
      <div class="app-picker">
        <span class="picker-label">Agent:</span>
        <div class="select-wrapper">
          <select id="appSelect" bind:value={selectedApp} onchange={() => { selectedSessionId = ''; loadSessions(); }}>
            {#each apps as app}
              <option value={app.name}>{app.root_agent_name || app.name}</option>
            {/each}
          </select>
          <ChevronDown size={14} class="select-chevron" />
        </div>
      </div>

      {#if selectedSessionId}
        <div class="session-chip">
          <span class="pulse-dot"></span>
          <span>Online</span>
        </div>
      {/if}
    </div>

    <!-- Header Actions -->
    <div class="header-right">
      <button class="header-pill-btn" onclick={() => showAgentGraph = true} title="View Multi-Agent DAG Architecture & Protocol Graph">
        <Workflow size={15} strokeWidth={1.75} />
        <span>Agent Graph</span>
      </button>

      <button class="header-pill-btn" onclick={() => showLegend = true} title="View Agent System Architecture">
        <HelpCircle size={15} strokeWidth={1.75} />
        <span>Capabilities</span>
      </button>

      <button class="icon-btn" onclick={toggleTheme} title="Toggle Theme">
        {#if isDarkMode}
          <Sun size={18} strokeWidth={1.75} />
        {:else}
          <Moon size={18} strokeWidth={1.75} />
        {/if}
      </button>
    </div>
  </header>

  <div class="studio-body">
    <!-- =========================================================================
     * LEFT PANEL: Sessions & Prompt History
     * ========================================================================= -->
    {#if showSessions}
      <aside class="studio-sidebar">
        <div class="sidebar-top">
          <button class="btn-new-prompt" onclick={startNewSession} disabled={isLoading}>
            <Plus size={18} strokeWidth={2} />
            <span>New Session</span>
          </button>
        </div>

        <div class="sidebar-section-title">
          <History size={13} strokeWidth={1.75} />
          <span>SESSION HISTORY</span>
        </div>

        <div class="sessions-stream">
          {#if sessions.length === 0}
            <div class="empty-sessions">
              <p>No recent chats.</p>
              <span>Click "+ New Session" to begin.</span>
            </div>
          {:else}
            {#each sessions as session, idx}
              <div class="session-item" class:active={selectedSessionId === session.session_id}>
                <button class="session-nav-btn" onclick={() => selectSession(session.session_id)}>
                  <span class="session-dot" class:active-dot={selectedSessionId === session.session_id}></span>
                  <div class="session-text-group">
                    <span class="session-title">Chat Session #{sessions.length - idx}</span>
                    <span class="session-meta">{selectedSessionId === session.session_id ? 'Current session' : 'Previous history'}</span>
                  </div>
                </button>
                <button 
                  class="session-del-btn" 
                  onclick={() => deleteSession(session.session_id)} 
                  title="Delete Session"
                >
                  <Trash2 size={14} strokeWidth={1.75} />
                </button>
              </div>
            {/each}
          {/if}
        </div>

        <div class="sidebar-footer">
          <div class="quota-pill">
            <span class="quota-dot"></span>
            <span>Agents Runtime Active</span>
          </div>
        </div>
      </aside>
    {/if}

    <!-- =========================================================================
     * CENTRAL WORKSPACE: Prompt Stream & Floating Input
     * ========================================================================= -->
    <main class="studio-main" 
          ondragenter={handleDragEnter}
          ondragover={handleDragOver}
          ondragleave={handleDragLeave}
          ondrop={handleDrop}>
      
      <!-- Drag & Drop Overlay -->
      {#if isDragging}
        <div class="drag-zone-overlay">
          <div class="drag-zone-card">
            <Paperclip size={36} class="drag-icon" />
            <h3>Drop Files for Multimodal Inference</h3>
            <p>Accepts receipts, invoice images, portrait photos, spreadsheets, and PDFs</p>
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
          <button class="error-banner-close" onclick={() => errorMsg = ''} title="Dismiss error">
            <X size={15} />
          </button>
        </div>
      {/if}

      {#if !selectedSessionId}
        <!-- Informative Agent Hub Dashboard -->
        <div class="hub-welcome-view">
          <div class="hub-hero">
            <div class="hub-pill">
              <span class="hub-pill-dot"></span>
              <span>GDG Krakow Operations & Event Platform</span>
            </div>
            <h2>Autonomous Agent Orchestration</h2>
            <p>Select a specialized agent below or use the <strong>Root Orchestrator</strong> to automatically analyze your prompt and dispatch tasks across pipelines.</p>
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
            <!-- Root Orchestrator -->
            <button 
              class="agent-catalog-card" 
              style="--card-border: var(--agent-root);"
              onclick={() => { selectedApp = 'root_agent'; startNewSession(); queryText = "Analyze current task requirements and coordinate suitable agents."; }}
            >
              <div class="agent-card-header">
                <div class="agent-icon-box">
                  <Workflow size={18} strokeWidth={1.75} />
                </div>
                <div class="agent-title-col">
                  <strong>Root Orchestrator</strong>
                  <span class="agent-type-tag">Router & Coordinator</span>
                </div>
              </div>
              <p class="agent-card-desc">Parses complex multi-step requests, verifies prerequisites, and delegates tasks to sub-agents.</p>
              <div class="card-footer-action">
                <span>Start workflow</span>
                <ArrowRight size={14} />
              </div>
            </button>

            <!-- Receipt Scanner -->
            <button 
              class="agent-catalog-card" 
              style="--card-border: var(--agent-receipt);"
              onclick={() => { selectedApp = 'receipt_scanner'; startNewSession(); queryText = "Scan attached receipt, extract VAT & line items, convert currency and create expense report."; }}
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
              <p class="agent-card-desc">Extracts line items, queries NBP/Pekao exchange rates, and exports formatted expense reports.</p>
              <div class="card-footer-action">
                <span>Scan receipts</span>
                <ArrowRight size={14} />
              </div>
            </button>

            <!-- Live Video Editor -->
            <button 
              class="agent-catalog-card" 
              style="--card-border: var(--agent-video);"
              onclick={() => { selectedApp = 'video_editor'; startNewSession(); queryText = "Outpaint speaker portrait to 9:16 aspect ratio and generate animated intro via Veo."; }}
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
              <p class="agent-card-desc">Detects face landmarks, executes 9:16 outpainting, and generates cinematic speaker intro videos.</p>
              <div class="card-footer-action">
                <span>Generate video</span>
                <ArrowRight size={14} />
              </div>
            </button>

            <!-- LinkedIn Planner -->
            <button 
              class="agent-catalog-card" 
              style="--card-border: var(--agent-linkedin);"
              onclick={() => { selectedApp = 'linkedin_post_generator'; startNewSession(); queryText = "Draft 3 engaging LinkedIn post variants for upcoming speaker session and event recap."; }}
            >
              <div class="agent-card-header">
                <div class="agent-icon-box">
                  <Share2 size={18} strokeWidth={1.75} />
                </div>
                <div class="agent-title-col">
                  <strong>LinkedIn Planner</strong>
                  <span class="agent-type-tag">Social Copy</span>
                </div>
              </div>
              <p class="agent-card-desc">Drafts speaker announcements and structured multi-option event recap posts ready for copy-pasting.</p>
              <div class="card-footer-action">
                <span>Draft posts</span>
                <ArrowRight size={14} />
              </div>
            </button>

            <!-- Registrations Manager -->
            <button 
              class="agent-catalog-card" 
              style="--card-border: var(--agent-registration);"
              onclick={() => { selectedApp = 'registration_manager'; startNewSession(); queryText = "Deduplicate attendee registrations, clean multilingual names and cross-reference organizer list."; }}
            >
              <div class="agent-card-header">
                <div class="agent-icon-box">
                  <Users size={18} strokeWidth={1.75} />
                </div>
                <div class="agent-title-col">
                  <strong>Registrations Manager</strong>
                  <span class="agent-type-tag">Data Cleaning</span>
                </div>
              </div>
              <p class="agent-card-desc">Filters test entries, performs phonetic fuzzy name matching, and compiles verified registration lists.</p>
              <div class="card-footer-action">
                <span>Process list</span>
                <ArrowRight size={14} />
              </div>
            </button>

            <!-- Event Scheduler -->
            <button 
              class="agent-catalog-card" 
              style="--card-border: var(--agent-planner);"
              onclick={() => { selectedApp = 'event_planner'; startNewSession(); queryText = "Check local meetup conflicts and public holiday risks for our next GDG event date."; }}
            >
              <div class="agent-card-header">
                <div class="agent-icon-box">
                  <Calendar size={18} strokeWidth={1.75} />
                </div>
                <div class="agent-title-col">
                  <strong>Event Scheduler</strong>
                  <span class="agent-type-tag">Calendar Intelligence</span>
                </div>
              </div>
              <p class="agent-card-desc">Scans Meetup.com and Luma for tech clashes, cross-references Polish public holidays and vacations.</p>
              <div class="card-footer-action">
                <span>Check dates</span>
                <ArrowRight size={14} />
              </div>
            </button>

            <!-- Agenda Formatter -->
            <button 
              class="agent-catalog-card" 
              style="--card-border: var(--agent-agenda);"
              onclick={() => { selectedApp = 'agenda_generator'; startNewSession(); queryText = "Format meetup timeline starting at 17:30 with 2 speaker slots (35min each) and pizza pause."; }}
            >
              <div class="agent-card-header">
                <div class="agent-icon-box">
                  <Clock size={18} strokeWidth={1.75} />
                </div>
                <div class="agent-title-col">
                  <strong>Agenda Formatter</strong>
                  <span class="agent-type-tag">Timeline Logistics</span>
                </div>
              </div>
              <p class="agent-card-desc">Calculates minute-by-minute schedules with talks, coffee breaks, and pizza pauses with clean time rounding.</p>
              <div class="card-footer-action">
                <span>Build agenda</span>
                <ArrowRight size={14} />
              </div>
            </button>

            <!-- Office Secretary -->
            <button 
              class="agent-catalog-card" 
              style="--card-border: var(--agent-office);"
              onclick={() => { selectedApp = 'office_secretary'; startNewSession(); queryText = "Draft polite email request for visitor key access cards and Event Hub space reservation."; }}
            >
              <div class="agent-card-header">
                <div class="agent-icon-box">
                  <Mail size={18} strokeWidth={1.75} />
                </div>
                <div class="agent-title-col">
                  <strong>Office Secretary</strong>
                  <span class="agent-type-tag">Venue Administration</span>
                </div>
              </div>
              <p class="agent-card-desc">Composes formal reservation and visitor keycard request emails with mandatory date verification.</p>
              <div class="card-footer-action">
                <span>Compose email</span>
                <ArrowRight size={14} />
              </div>
            </button>
          </div>
        </div>
      {:else}
        <!-- Chat & Output Stream -->
        <div class="chat-viewport">
          {#if isLoading}
            <div class="studio-progress-line"></div>
          {/if}

          <!-- Messages Body -->
          <div class="messages-container" bind:this={chatBodyElement}>
            {#if events.length === 0}
              <div class="empty-conversation-state">
                <Sparkle size={32} class="empty-sparkle" />
                <h3>Prompt Session Initialized</h3>
                <p>Type your query or drag media files into the floating bar below to start.</p>
              </div>
            {/if}

            {#each filteredEvents as event, idx}
              {@const errInfo = getEventError(event)}
              {#if errInfo}
                {@const theme = getAgentTheme(event.author)}
                <!-- Error Event Card -->
                <div class="message-row error-row">
                  <div class="message-card error-card">
                    <div class="error-card-header">
                      <div class="error-badge-pill">
                        <AlertCircle size={14} />
                        <span>Execution Error ({theme.label || event.author || 'Agent'})</span>
                      </div>
                    </div>
                    <div class="error-body">
                      <p class="error-text-main">{errInfo.message}</p>
                      {#if errInfo.code}
                        <div class="error-code-chip">{errInfo.code}</div>
                      {/if}
                    </div>
                  </div>
                </div>
              {:else if event.author === 'user'}
                <!-- User Prompt Bubble -->
                <div class="message-row user-row">
                  <div class="message-card user-card">
                    <div class="card-author">
                      <User size={14} />
                      <span>You</span>
                    </div>
                    {#if event.content && event.content.parts}
                      {#each event.content.parts as part}
                        {#if part.text}
                          <div class="markdown-body">{@html renderMarkdown(part.text)}</div>
                        {/if}
                        {#if part.inline_data || part.inlineData}
                          {@const inline = part.inline_data || part.inlineData}
                          {@const mime = inline.mime_type || inline.mimeType || ''}
                          <div class="user-attached-file-badge">
                            <Paperclip size={13} class="badge-paperclip" />
                            <span class="badge-filename">Attached Media ({mime.replace('image/', 'img:').replace('video/', 'video:').replace('application/', '') || 'file'})</span>
                            <span class="badge-status-dot"></span>
                            <span class="badge-status-label">Transferred</span>
                          </div>
                        {/if}
                      {/each}
                    {/if}
                  </div>
                </div>
              {:else}
                <!-- Explicit Sub-Agent Delegation Handoff Divider -->
                {#if shouldShowDelegationHandoff(event, idx, filteredEvents)}
                  {@const targetTheme = getAgentTheme(event.author)}
                  <div class="agent-delegation-divider">
                    <div class="delegation-line"></div>
                    <div class="delegation-badge" style="--pill-color: {targetTheme.color}; --pill-bg: {targetTheme.bg};">
                      <Workflow size={13} class="delegation-icon" />
                      <span>Task routed to <strong>{targetTheme.label}</strong></span>
                      <ArrowRight size={12} class="delegation-arrow" />
                    </div>
                    <div class="delegation-line"></div>
                  </div>
                {/if}

                <!-- Model Response Card -->
                {@const theme = getAgentTheme(event.author)}
                <div class="message-row model-row" style="--agent-color: {theme.color}; --agent-bg: {theme.bg}">
                  <div class="message-card model-card">
                    <div class="model-author-header">
                      <div class="agent-badge-pill" style="background: {theme.bg}; color: {theme.color}; border: 1px solid {theme.color}40;">
                        <span class="badge-dot" style="background: {theme.color}"></span>
                        <span>{theme.label}</span>
                      </div>
                    </div>

                    {#if event.content && event.content.parts}
                      {#each event.content.parts as part}
                        {#if part.text}
                          {#if isAgendaOutput(part.text, event.author)}
                            <AgendaTimeline 
                              rawText={part.text} 
                              author={event.author} 
                              onRefine={(refinedText) => refineVariant(refinedText)} 
                            />
                          {:else}
                            {@const variants = parseResponseVariants(part.text, event.author)}
                            {#if variants.length === 1}
                              <div class="markdown-body">{@html renderMarkdown(part.text)}</div>
                            {:else}
                            <div class="variants-deck">
                              {#each variants as variant, vIdx}
                                <div class="variant-item-card">
                                  <div class="variant-top-bar">
                                    <span class="variant-tag">{variant.header || 'Option'}</span>
                                    <div class="variant-actions">
                                      {#if variant.header.toLowerCase() !== 'introduction'}
                                        <button class="variant-btn" onclick={() => copyToClipboard(variant.body, 'v_' + idx + '_' + vIdx)}>
                                          {#if copiedId === 'v_' + idx + '_' + vIdx}
                                            <Check size={13} />
                                            <span>Copied</span>
                                          {:else}
                                            <Copy size={13} />
                                            <span>Copy</span>
                                          {/if}
                                        </button>
                                        <button class="variant-btn refine-btn" onclick={() => refineVariant(variant.body)}>
                                          <RefreshCw size={13} />
                                          <span>Refine</span>
                                        </button>
                                      {/if}
                                    </div>
                                  </div>
                                  <div class="variant-markdown markdown-body">
                                    {@html renderMarkdown(variant.body)}
                                  </div>
                                </div>
                              {/each}
                            </div>
                          {/if}
                        {/if}
                      {/if}

                        <!-- Tool Call Activity Step (Clean, No Raw JSON) -->
                        {#if part.function_call || part.functionCall}
                          {@const fc = part.function_call || part.functionCall}
                          <div class="activity-step-chip">
                            <div class="activity-pulse-dot"></div>
                            <span class="activity-label">{getFriendlyToolCall(fc.name, fc.args)}</span>
                          </div>
                        {/if}

                        <!-- Tool Response Activity Step (Clean, No Raw JSON) -->
                        {#if part.function_response || part.functionResponse}
                          {@const fr = part.function_response || part.functionResponse}
                          {@const isErr = isToolResponseError(fr.response)}
                          <div class="activity-step-chip {isErr ? 'activity-error' : 'activity-done'}">
                            {#if isErr}
                              <AlertCircle size={13} class="activity-error-icon" />
                            {:else}
                              <Check size={13} class="activity-check-icon" />
                            {/if}
                            <span class="activity-label">{getFriendlyToolResponse(fr.name, fr.response)}</span>
                          </div>
                        {/if}
                      {/each}
                    {/if}
                  </div>
                </div>
              {/if}
            {/each}

            {#if isLoading}
              <!-- Real-time Gemini Generation Stream Shimmer with Active Agent Badge -->
              {@const execTheme = getAgentTheme(currentExecutingAgent || selectedApp)}
              <div class="generating-live-card" style="--exec-color: {execTheme.color}; --exec-bg: {execTheme.bg};">
                <div class="generating-header">
                  <div class="executing-agent-badge" style="background: {execTheme.bg}; color: {execTheme.color}; border: 1px solid {execTheme.color}40;">
                    <span class="live-pulse-dot" style="background: {execTheme.color};"></span>
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
      {/if}

      <!-- =========================================================================
       * FLOATING PROMPT INPUT BAR (Google AI Studio Standard)
       * ========================================================================= -->
      <div class="floating-prompt-wrapper">
        <div class="floating-prompt-box">
          <!-- Top Attachment & Context Strip -->
          <div class="prompt-meta-top">
            <label class="chip-action-btn" title="Add Multimodal Attachments">
              <Plus size={15} strokeWidth={2} />
              <span>Add files</span>
              <input type="file" multiple onchange={handleFileSelect} style="display: none;" />
            </label>

            <div class="token-telemetry">
              <span class="token-val">{(queryText.length * 0.25).toFixed(0)}</span>
              <span class="token-max">/ 1,048,576 tokens</span>
            </div>
          </div>

          <!-- Staged Attachments Carousel -->
          {#if stagedFiles.length > 0}
            <div class="staged-media-row">
              {#each stagedFiles as file, index}
                <div class="staged-card">
                  {#if file.preview}
                    <img class="staged-img" src={file.preview} alt="staged upload" />
                  {:else}
                    <FileText size={20} class="staged-doc-icon" />
                  {/if}
                  <span class="staged-filename">{file.name}</span>
                  <button class="staged-del-btn" onclick={() => removeStagedFile(index)}>&times;</button>
                </div>
              {/each}
            </div>
          {/if}

          <!-- Textarea Field -->
          <textarea 
            bind:this={textareaElement}
            bind:value={queryText}
            onkeydown={handleKeyPress}
            oninput={(e) => {
              const target = /** @type {HTMLTextAreaElement} */ (e.target);
              target.style.height = 'auto';
              target.style.height = (target.scrollHeight) + 'px';
            }}
            placeholder="Type your prompt here, or press Ctrl+Enter to execute..."
            rows="1"
            disabled={isLoading}
          ></textarea>

          <!-- Bottom Action Toolbar -->
          <div class="prompt-meta-bottom">
            <div class="prompt-quick-tags">
              <span class="tag-hint">Ctrl + ↵ to Run</span>
            </div>

            <button 
              class="btn-run-gemini" 
              onclick={sendMessage} 
              disabled={isLoading || (!queryText.trim() && stagedFiles.length === 0)}
            >
              <Sparkles size={16} strokeWidth={2} class={isLoading ? 'generating-sparkle' : ''} />
              <span>Run</span>
              <CornerDownLeft size={14} />
            </button>
          </div>
        </div>
      </div>
    </main>
  </div>
</div>

<!-- =========================================================================
 * CAPABILITIES MODAL (M3 Dialog & Theme Specs)
 * ========================================================================= -->
{#if showLegend}
  <div class="modal-backdrop" role="button" tabindex="-1" onclick={(e) => { if (e.target === e.currentTarget) showLegend = false; }} onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') showLegend = false; }}>
    <div class="modal-card">
      <header class="modal-header">
        <div class="modal-title-group">
          <Sparkles size={20} class="modal-gemini-icon" />
          <h2>GDG Agent System Architecture</h2>
        </div>
        <button class="icon-btn" onclick={() => showLegend = false}>
          <X size={18} />
        </button>
      </header>
      
      <div class="modal-content">
        <p class="modal-intro">Each specialized agent operates autonomously or in coordination with the Root Orchestrator using dedicated toolkits and verified outputs:</p>
        
        <div class="capabilities-grid">
          <!-- Root Orchestrator -->
          <div class="capability-card" style="--card-accent: var(--agent-root); --card-bg: var(--bg-root)">
            <div class="capability-top">
              <span class="cap-indicator" style="background: var(--agent-root)"></span>
              <h3>Root Orchestrator</h3>
            </div>
            <p>Main agent coordinator. Parses user intent, plans workflow execution, and delegates execution steps to sub-agents.</p>
          </div>

          <!-- Receipt Scanner -->
          <div class="capability-card" style="--card-accent: var(--agent-receipt); --card-bg: var(--bg-receipt)">
            <div class="capability-top">
              <span class="cap-indicator" style="background: var(--agent-receipt)"></span>
              <h3>Receipt Scanner</h3>
            </div>
            <p>Vision OCR analyzer. Extracts line items, VAT, fetches Pekao/NBP exchange rates, and exports formatted expense reports.</p>
          </div>

          <!-- Video Editor -->
          <div class="capability-card" style="--card-accent: var(--agent-video); --card-bg: var(--bg-video)">
            <div class="capability-top">
              <span class="cap-indicator" style="background: var(--agent-video)"></span>
              <h3>Live Video Editor</h3>
            </div>
            <p>Speaker portrait outpainting and cinematic video animation generation using Veo models.</p>
          </div>

          <!-- LinkedIn Planner -->
          <div class="capability-card" style="--card-accent: var(--agent-linkedin); --card-bg: var(--bg-linkedin)">
            <div class="capability-top">
              <span class="cap-indicator" style="background: var(--agent-linkedin)"></span>
              <h3>LinkedIn Planner</h3>
            </div>
            <p>Generates high-engagement speaker announcements and structured multi-option event recap posts.</p>
          </div>

          <!-- Registrations Manager -->
          <div class="capability-card" style="--card-accent: var(--agent-registration); --card-bg: var(--bg-registration)">
            <div class="capability-top">
              <span class="cap-indicator" style="background: var(--agent-registration)"></span>
              <h3>Registrations Manager</h3>
            </div>
            <p>Cleans participant datasets, filters duplicates, normalizes names across scripts, and generates clean DOCX files.</p>
          </div>

          <!-- Event Scheduler -->
          <div class="capability-card" style="--card-accent: var(--agent-planner); --card-bg: var(--bg-planner)">
            <div class="capability-top">
              <span class="cap-indicator" style="background: var(--agent-planner)"></span>
              <h3>Event Scheduler</h3>
            </div>
            <p>Detects meetup schedule conflicts against Luma and Meetup.com, checks statutory Polish holidays, and flags risk dates.</p>
          </div>

          <!-- Agenda Formatter -->
          <div class="capability-card" style="--card-accent: var(--agent-agenda); --card-bg: var(--bg-agenda)">
            <div class="capability-top">
              <span class="cap-indicator" style="background: var(--agent-agenda)"></span>
              <h3>Agenda Formatter</h3>
            </div>
            <p>Computes minute-by-minute meetup schedules with speaker talks, networking, and pizza breaks, formatted for copy-pasting.</p>
          </div>

          <!-- Office Secretary -->
          <div class="capability-card" style="--card-accent: var(--agent-office); --card-bg: var(--bg-office)">
            <div class="capability-top">
              <span class="cap-indicator" style="background: var(--agent-office)"></span>
              <h3>Office Secretary</h3>
            </div>
            <p>Drafts polite visitor keys access card and Event Hub reservation request emails with mandatory date validation.</p>
          </div>
        </div>
      </div>
      
      <footer class="modal-actions">
        <button class="btn-primary" onclick={() => showLegend = false}>Close</button>
      </footer>
    </div>
  </div>
{/if}

<!-- =========================================================================
 * MULTI-AGENT DAG GRAPH MODAL (A2A Architecture Canvas)
 * ========================================================================= -->
{#if showAgentGraph}
  <AgentGraph 
    {currentExecutingAgent} 
    {isLoading} 
    {selectedApp} 
    onSelectAgent={(agentId) => {
      selectedApp = agentId;
      selectedSessionId = '';
      loadSessions();
    }}
    onClose={() => showAgentGraph = false}
  />
{/if}

<style>
  /* =========================================================================
   * GOOGLE AI STUDIO 3-COLUMN LAYOUT
   * ========================================================================= */
  .studio-layout {
    display: flex;
    flex-direction: column;
    height: 100vh;
    width: 100vw;
    background-color: var(--bg-app);
    color: var(--text-primary);
    overflow: hidden;
  }

  /* Header / Top App Bar */
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

  .header-left, .header-right {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .brand-badge {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .brand-gemini-icon {
    width: 32px;
    height: 32px;
    border-radius: var(--radius-sm);
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--primary-accent);
  }

  .brand-text {
    display: flex;
    flex-direction: column;
  }

  .brand-name {
    font-weight: 600;
    font-size: var(--font-size-body-md);
    color: var(--text-primary);
  }

  .brand-sub {
    font-size: var(--font-size-label);
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .header-divider {
    width: 1px;
    height: 24px;
    background: var(--border-subtle);
  }

  .app-picker {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .picker-label {
    font-size: var(--font-size-body-sm);
    color: var(--text-tertiary);
  }

  .select-wrapper {
    position: relative;
    display: flex;
    align-items: center;
  }

  .select-wrapper select {
    background: var(--bg-surface-elevated);
    color: var(--text-primary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-pill);
    padding: 6px 30px 6px 14px;
    font-size: var(--font-size-body-sm);
    font-weight: 500;
    cursor: pointer;
    outline: none;
    appearance: none;
  }

  .select-wrapper select:focus {
    border-color: var(--border-focus);
  }

  :global(.select-chevron) {
    position: absolute;
    right: 10px;
    pointer-events: none;
    color: var(--text-secondary);
  }

  .session-chip {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    background: rgba(129, 201, 149, 0.12);
    border: 1px solid rgba(129, 201, 149, 0.3);
    border-radius: var(--radius-pill);
    font-size: var(--font-size-body-sm);
    color: var(--status-success);
  }

  .pulse-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--status-success);
    box-shadow: 0 0 8px var(--status-success);
  }

  .icon-btn {
    width: 36px;
    height: 36px;
    border-radius: var(--radius-pill);
    background: transparent;
    border: 1px solid transparent;
    color: var(--text-secondary);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .icon-btn:hover {
    background: var(--bg-surface-elevated);
    color: var(--text-primary);
    border-color: var(--border-subtle);
  }

  .icon-btn.active {
    background: var(--primary-accent-container);
    color: var(--primary-accent-text);
  }

  .header-pill-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-pill);
    color: var(--text-secondary);
    font-size: var(--font-size-body-sm);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .header-pill-btn:hover {
    background: var(--bg-surface-variant);
    color: var(--text-primary);
  }

  /* Body 3-column container */
  .studio-body {
    display: flex;
    flex: 1;
    overflow: hidden;
  }

  /* =========================================================================
   * LEFT SIDEBAR
   * ========================================================================= */
  .studio-sidebar {
    width: 270px;
    background: var(--bg-surface);
    border-right: 1px solid var(--border-subtle);
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
  }

  .sidebar-top {
    padding: 16px;
  }

  .btn-new-prompt {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 10px 16px;
    border-radius: var(--radius-pill);
    background: var(--primary-accent);
    color: var(--text-inverse);
    border: none;
    font-weight: 500;
    font-size: var(--font-size-body-sm);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .btn-new-prompt:hover {
    background: var(--primary-accent-hover);
    box-shadow: var(--shadow-elevation-1);
  }

  .sidebar-section-title {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    font-size: var(--font-size-label);
    font-weight: 600;
    color: var(--text-tertiary);
    letter-spacing: 0.6px;
  }

  .sessions-stream {
    flex: 1;
    overflow-y: auto;
    padding: 0 8px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .session-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    border-radius: var(--radius-md);
    transition: all 0.15s ease;
  }

  .session-item:hover {
    background: var(--bg-surface-elevated);
  }

  .session-item.active {
    background: var(--bg-surface-variant);
    border-left: 3px solid var(--primary-accent);
  }

  .session-nav-btn {
    display: flex;
    align-items: center;
    gap: 10px;
    background: none;
    border: none;
    color: inherit;
    text-align: left;
    cursor: pointer;
    flex: 1;
    overflow: hidden;
  }

  .session-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--border-medium);
    flex-shrink: 0;
  }

  .session-dot.active-dot {
    background: var(--primary-accent);
    box-shadow: 0 0 6px var(--primary-accent);
  }

  .session-text-group {
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .session-title {
    font-size: var(--font-size-body-sm);
    font-weight: 500;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .session-meta {
    font-size: var(--font-size-label);
    color: var(--text-tertiary);
  }

  .session-del-btn {
    background: none;
    border: none;
    color: var(--text-tertiary);
    cursor: pointer;
    opacity: 0;
    padding: 4px;
    border-radius: var(--radius-xs);
    transition: all 0.15s ease;
  }

  .session-item:hover .session-del-btn {
    opacity: 1;
  }

  .session-del-btn:hover {
    color: var(--status-error);
    background: rgba(242, 139, 130, 0.12);
  }

  .empty-sessions {
    padding: 24px 16px;
    text-align: center;
    color: var(--text-tertiary);
    font-size: var(--font-size-body-sm);
  }

  .sidebar-footer {
    padding: 12px 16px;
    border-top: 1px solid var(--border-subtle);
  }

  .quota-pill {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: var(--font-size-label);
    color: var(--text-tertiary);
  }

  .quota-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--status-info);
  }

  /* =========================================================================
   * CENTRAL MAIN WORKSPACE
   * ========================================================================= */
  .studio-main {
    flex: 1;
    display: flex;
    flex-direction: column;
    position: relative;
    background: var(--bg-app);
    overflow: hidden;
  }

  .studio-progress-line {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: var(--primary-accent);
    z-index: 20;
  }

  /* =========================================================================
   * INFORMATIVE AGENTS HUB (Welcome View)
   * ========================================================================= */
  .hub-welcome-view {
    flex: 1;
    overflow-y: auto;
    padding: 24px 28px 10px;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .hub-hero {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
    max-width: 800px;
  }

  .hub-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 4px 12px;
    border-radius: var(--radius-pill);
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    font-size: var(--font-size-label);
    font-weight: 500;
    color: var(--primary-accent);
    letter-spacing: 0.3px;
  }

  .hub-pill-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--primary-accent);
  }

  .hub-hero h2 {
    font-size: 1.5rem;
    font-weight: 600;
    color: var(--text-primary);
    line-height: 1.3;
  }

  .hub-hero p {
    font-size: var(--font-size-body-md);
    color: var(--text-secondary);
    line-height: 1.5;
  }

  .hub-hero p strong {
    color: var(--primary-accent);
  }

  /* Workflow Steps */
  .workflow-steps-strip {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 16px;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    font-size: var(--font-size-body-sm);
    color: var(--text-secondary);
  }

  .step-badge {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .step-num {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: var(--bg-surface-variant);
    color: var(--text-primary);
    font-weight: 600;
    font-size: 11px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .step-separator {
    flex: 1;
    height: 1px;
    background: var(--border-subtle);
  }

  /* Agents Catalog Grid (4 cols on desktop) */
  .agents-catalog-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
  }

  @media (max-width: 1300px) {
    .agents-catalog-grid {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  .agent-catalog-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-top: 2px solid var(--card-border, var(--border-medium));
    border-radius: var(--radius-md);
    padding: 14px;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    text-align: left;
    cursor: pointer;
    transition: all 0.15s ease;
    position: relative;
  }

  .agent-catalog-card:hover {
    background: var(--bg-surface-elevated);
    border-color: var(--card-border, var(--border-medium));
    transform: translateY(-2px);
    box-shadow: var(--shadow-elevation-1);
  }

  .agent-card-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
    width: 100%;
  }

  .agent-icon-box {
    width: 32px;
    height: 32px;
    border-radius: var(--radius-sm);
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    color: var(--text-secondary);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: color 0.15s ease;
  }

  .agent-catalog-card:hover .agent-icon-box {
    color: var(--text-primary);
  }

  .agent-title-col {
    display: flex;
    flex-direction: column;
    overflow: hidden;
    gap: 2px;
  }

  .agent-title-col strong {
    font-size: var(--font-size-body-sm);
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .agent-type-tag {
    font-size: 10px;
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.4px;
  }

  .agent-card-desc {
    font-size: 12px;
    color: var(--text-secondary);
    line-height: 1.45;
    flex: 1;
    margin-bottom: 12px;
  }

  .card-footer-action {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    font-weight: 500;
    color: var(--text-tertiary);
    transition: all 0.15s ease;
  }

  .agent-catalog-card:hover .card-footer-action {
    color: var(--primary-accent);
    gap: 8px;
  }

  /* Chat Viewport */
  .chat-viewport {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    position: relative;
    width: 100%;
  }

  /* Messages Area - Constrained to comfortable reading width */
  .messages-container {
    flex: 1;
    overflow-y: auto;
    padding: 24px 20px 120px;
    display: flex;
    flex-direction: column;
    gap: 20px;
    max-width: 920px;
    width: 100%;
    margin: 0 auto;
    box-sizing: border-box;
  }

  .empty-conversation-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px 20px;
    color: var(--text-tertiary);
    text-align: center;
  }

  :global(.empty-sparkle) {
    color: var(--primary-accent);
    margin-bottom: 12px;
  }

  /* Agent Delegation / Handoff Transition Divider */
  .agent-delegation-divider {
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 10px 0;
    width: 100%;
    animation: fadeIn 0.3s ease-out;
  }

  .delegation-line {
    flex: 1;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--border-medium), transparent);
  }

  .delegation-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    border-radius: var(--radius-pill);
    background: var(--pill-bg, rgba(138, 180, 248, 0.1));
    border: 1px solid var(--pill-color, var(--primary-accent));
    color: var(--pill-color, var(--primary-accent));
    font-size: var(--font-size-label);
    font-weight: 500;
    box-shadow: var(--shadow-elevation-1);
  }

  :global(.delegation-icon) {
    color: inherit;
    animation: spinSlow 8s linear infinite;
  }

  @keyframes spinSlow {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  :global(.delegation-arrow) {
    opacity: 0.7;
    margin-left: 2px;
  }

  .message-row {
    display: flex;
    width: 100%;
  }

  .user-row {
    justify-content: flex-end;
  }

  .model-row {
    justify-content: flex-start;
  }

  .message-card {
    max-width: 88%;
    border-radius: var(--radius-xl);
    padding: 16px 20px;
    position: relative;
    box-sizing: border-box;
  }

  .user-card {
    background: var(--bg-surface-variant);
    border: 1px solid var(--border-subtle);
    border-bottom-right-radius: 4px;
  }

  .model-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-bottom-left-radius: 4px;
    box-shadow: var(--shadow-elevation-1);
  }

  .model-card::before {
    content: '';
    position: absolute;
    left: -1px;
    top: 16px;
    bottom: 16px;
    width: 3px;
    border-radius: 2px;
    background: var(--agent-color, var(--primary-accent));
  }

  .card-author {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: var(--font-size-label);
    color: var(--text-tertiary);
    margin-bottom: 8px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  /* Global Error Banner */
  .global-error-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 10px 16px;
    margin: 12px 24px 0 24px;
    background: rgba(242, 139, 130, 0.15);
    border: 1px solid rgba(242, 139, 130, 0.4);
    border-radius: var(--radius-md);
    color: var(--text-primary);
    animation: fadeIn 0.2s ease-in-out;
  }

  .global-error-content {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: var(--font-size-body-sm);
  }

  :global(.error-banner-icon) {
    color: var(--status-error);
    flex-shrink: 0;
  }

  .error-banner-text {
    font-weight: 500;
    word-break: break-word;
  }

  .error-banner-close {
    background: transparent;
    border: none;
    cursor: pointer;
    color: var(--text-secondary);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 4px;
    border-radius: var(--radius-xs);
    transition: background 0.15s ease, color 0.15s ease;
  }

  .error-banner-close:hover {
    background: rgba(242, 139, 130, 0.2);
    color: var(--text-primary);
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(-4px); }
    to { opacity: 1; transform: translateY(0); }
  }

  /* Error Card In Message Stream */
  .error-row {
    justify-content: flex-start;
  }

  .error-card {
    background: rgba(242, 139, 130, 0.08);
    border: 1px solid rgba(242, 139, 130, 0.35);
    border-radius: var(--radius-xl);
    padding: 16px 20px;
    max-width: 80%;
  }

  .error-card-header {
    margin-bottom: 8px;
  }

  .error-badge-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 3px 10px;
    border-radius: var(--radius-pill);
    background: rgba(242, 139, 130, 0.2);
    color: var(--status-error);
    font-size: var(--font-size-label);
    font-weight: 600;
  }

  .error-body {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .error-text-main {
    font-size: var(--font-size-body-sm);
    color: var(--text-primary);
    line-height: 1.5;
    word-break: break-word;
    font-family: var(--font-mono);
  }

  .error-code-chip {
    display: inline-block;
    align-self: flex-start;
    padding: 2px 8px;
    background: rgba(242, 139, 130, 0.15);
    border-radius: var(--radius-xs);
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--status-error);
  }

  .model-author-header {
    margin-bottom: 10px;
  }

  .agent-badge-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: var(--radius-pill);
    font-size: var(--font-size-label);
    font-weight: 600;
  }

  .badge-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
  }

  .user-attached-file-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    margin-top: 8px;
    padding: 4px 10px;
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-pill);
    font-size: var(--font-size-body-xs);
    color: var(--text-secondary);
  }

  :global(.badge-paperclip) {
    color: var(--primary-accent);
  }

  .badge-filename {
    font-weight: 500;
  }

  .badge-status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--status-success);
  }

  .badge-status-label {
    color: var(--status-success);
    font-size: 11px;
    font-weight: 500;
  }

  /* Variants Card Grid */
  .variants-deck {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-top: 12px;
  }

  .variant-item-card {
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    padding: 14px 16px;
  }

  .variant-top-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
  }

  .variant-tag {
    font-size: var(--font-size-label);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--primary-accent);
    background: rgba(138, 180, 248, 0.12);
    padding: 3px 8px;
    border-radius: var(--radius-xs);
  }

  .variant-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .variant-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 10px;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-pill);
    font-size: var(--font-size-label);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .variant-btn:hover {
    background: var(--bg-surface-variant);
    color: var(--text-primary);
  }

  .refine-btn {
    color: var(--primary-accent);
  }

  /* Loading Live Agent Card */
  .generating-live-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-left: 3px solid var(--exec-color, var(--primary-accent));
    border-radius: var(--radius-xl);
    padding: 16px 20px;
    max-width: 85%;
    box-shadow: var(--shadow-elevation-1);
    box-sizing: border-box;
  }

  .generating-header {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 12px;
    font-size: var(--font-size-body-sm);
    color: var(--primary-accent);
  }

  .executing-agent-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 3px 10px;
    border-radius: var(--radius-pill);
    font-size: var(--font-size-label);
    font-weight: 600;
  }

  .live-pulse-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    animation: livePulse 1.4s ease-in-out infinite;
  }

  @keyframes livePulse {
    0% { transform: scale(0.9); opacity: 0.6; }
    50% { transform: scale(1.3); opacity: 1; }
    100% { transform: scale(0.9); opacity: 0.6; }
  }

  .generating-status {
    color: var(--text-primary);
    font-weight: 500;
  }

  .streaming-cursor {
    display: inline-block;
    width: 6px;
    height: 15px;
    background: var(--primary-accent);
    border-radius: 1px;
    animation: cursor-blink 0.8s infinite;
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
      var(--bg-surface-variant) 25%,
      var(--bg-surface-elevated) 50%,
      var(--bg-surface-variant) 75%
    );
    background-size: 200% 100%;
    animation: shimmer 1.8s infinite ease-in-out;
  }

  /* =========================================================================
   * FLOATING PROMPT BAR (Google AI Studio)
   * ========================================================================= */
  .floating-prompt-wrapper {
    padding: 12px 20px 24px;
    background: linear-gradient(180deg, transparent 0%, var(--bg-app) 35%);
    position: sticky;
    bottom: 0;
    z-index: 30;
    width: 100%;
    box-sizing: border-box;
  }

  .floating-prompt-box {
    max-width: 920px;
    width: 100%;
    margin: 0 auto;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-2xl);
    padding: 12px 18px;
    box-shadow: var(--shadow-elevation-2);
    transition: all 0.2s cubic-bezier(0.2, 0, 0, 1);
    box-sizing: border-box;
  }

  .floating-prompt-box:focus-within {
    border-color: rgba(138, 180, 248, 0.6);
    box-shadow: var(--shadow-elevation-3), var(--shadow-glow);
    background: var(--bg-surface-elevated);
  }

  .prompt-meta-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
  }

  .chip-action-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 10px;
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-pill);
    font-size: var(--font-size-label);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .chip-action-btn:hover {
    background: var(--bg-surface-variant);
    color: var(--text-primary);
  }

  .token-telemetry {
    font-size: var(--font-size-label);
    color: var(--text-tertiary);
  }

  .token-val {
    color: var(--primary-accent);
    font-weight: 500;
  }

  .staged-media-row {
    display: flex;
    gap: 8px;
    margin-bottom: 8px;
    overflow-x: auto;
    padding-bottom: 4px;
  }

  .staged-card {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 8px;
    background: var(--bg-surface-variant);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    font-size: var(--font-size-label);
  }

  .staged-img {
    width: 24px;
    height: 24px;
    border-radius: 4px;
    object-fit: cover;
  }

  .staged-filename {
    max-width: 120px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .staged-del-btn {
    background: none;
    border: none;
    color: var(--text-tertiary);
    cursor: pointer;
    font-size: 14px;
  }

  .staged-del-btn:hover {
    color: var(--status-error);
  }

  .floating-prompt-box textarea {
    width: 100%;
    min-height: 48px;
    max-height: 260px;
    background: transparent;
    border: none;
    outline: none;
    color: var(--text-primary);
    font-family: var(--font-family-base);
    font-size: var(--font-size-body-lg);
    line-height: 1.5;
    resize: none;
  }

  .prompt-meta-bottom {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 8px;
  }

  .tag-hint {
    font-size: var(--font-size-label);
    color: var(--text-tertiary);
  }

  .btn-run-gemini {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: var(--primary-accent);
    color: var(--text-inverse);
    font-weight: 500;
    font-size: var(--font-size-body-sm);
    border: none;
    border-radius: var(--radius-pill);
    padding: 8px 18px;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .btn-run-gemini:hover:not(:disabled) {
    background: var(--primary-accent-hover);
    box-shadow: var(--shadow-elevation-1);
  }

  .btn-run-gemini:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  /* =========================================================================
   * MODALS & OVERLAYS
   * ========================================================================= */
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.65);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
  }

  .modal-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-xl);
    width: 90%;
    max-width: 820px;
    max-height: 85vh;
    display: flex;
    flex-direction: column;
    box-shadow: var(--shadow-elevation-3);
  }

  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    border-bottom: 1px solid var(--border-subtle);
  }

  .modal-title-group {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  :global(.modal-gemini-icon) {
    color: var(--primary-accent);
  }

  .modal-header h2 {
    font-size: var(--font-size-title-lg);
    font-weight: 600;
  }

  .modal-content {
    padding: 20px;
    overflow-y: auto;
  }

  .modal-intro {
    font-size: var(--font-size-body-md);
    color: var(--text-secondary);
    margin-bottom: 16px;
    line-height: 1.5;
  }

  .capabilities-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }

  .capability-card {
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: 14px;
    border-left: 3px solid var(--card-accent);
  }

  .capability-top {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
  }

  .cap-indicator {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }

  .capability-top h3 {
    font-size: var(--font-size-body-sm);
    font-weight: 600;
  }

  .capability-card p {
    font-size: var(--font-size-label);
    color: var(--text-secondary);
    line-height: 1.4;
  }

  .modal-actions {
    padding: 14px 20px;
    border-top: 1px solid var(--border-subtle);
    display: flex;
    justify-content: flex-end;
  }

  .btn-primary {
    background: var(--primary-accent);
    color: var(--text-inverse);
    border: none;
    border-radius: var(--radius-pill);
    padding: 8px 20px;
    font-weight: 500;
    cursor: pointer;
  }

  /* Drag overlay */
  .drag-zone-overlay {
    position: absolute;
    inset: 0;
    background: rgba(19, 19, 20, 0.85);
    backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 80;
    pointer-events: none;
  }

  .drag-zone-card {
    background: var(--bg-surface);
    border: 2px dashed var(--primary-accent);
    border-radius: var(--radius-2xl);
    padding: 40px;
    text-align: center;
    pointer-events: none;
  }

  :global(.drag-icon) {
    color: var(--primary-accent);
    margin-bottom: 12px;
  }

  /* Activity Step Chips (Clean Execution Logs) */
  .activity-step-chip {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    margin: 4px 0;
    background: var(--bg-surface-variant);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-pill);
    font-size: var(--font-size-body-xs);
    color: var(--text-secondary);
  }

  .activity-pulse-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--primary-accent);
  }

  .activity-step-chip.activity-done {
    background: rgba(129, 201, 149, 0.08);
    border-color: rgba(129, 201, 149, 0.25);
    color: var(--text-primary);
  }

  .activity-step-chip.activity-error {
    background: rgba(242, 139, 130, 0.12);
    border-color: rgba(242, 139, 130, 0.35);
    color: var(--status-error);
  }

  :global(.activity-check-icon) {
    color: var(--status-success);
    flex-shrink: 0;
  }

  :global(.activity-error-icon) {
    color: var(--status-error);
    flex-shrink: 0;
  }

  /* Markdown prose styling */
  :global(.markdown-body) {
    font-size: var(--font-size-body-md);
    line-height: 1.6;
    color: var(--text-primary);
  }

  :global(.markdown-body p) {
    margin-bottom: 8px;
  }

  :global(.markdown-body h1, .markdown-body h2, .markdown-body h3) {
    margin-top: 12px;
    margin-bottom: 6px;
    font-size: 1.15rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  :global(.markdown-body blockquote) {
    margin: 8px 0;
    padding: 8px 14px;
    border-left: 3px solid var(--accent-primary);
    background: var(--bg-surface-variant);
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
    color: var(--text-secondary);
    font-style: normal;
  }

  :global(.markdown-body blockquote p) {
    margin-bottom: 4px;
  }

  :global(.markdown-body blockquote p:last-child) {
    margin-bottom: 0;
  }

  :global(.markdown-body hr) {
    border: none;
    border-top: 1px solid var(--border-subtle);
    margin: 12px 0;
  }

  :global(.markdown-body ul, .markdown-body ol) {
    margin-left: 20px;
    margin-bottom: 8px;
  }

  :global(.markdown-body code) {
    background: var(--bg-surface-variant);
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.9em;
  }

  :global(.markdown-body pre) {
    background: #0d0d0e;
    padding: 12px;
    border-radius: var(--radius-md);
    overflow-x: auto;
    margin: 8px 0;
    border: 1px solid var(--border-subtle);
  }

  :global(.markdown-body pre code) {
    background: transparent;
    padding: 0;
  }

  /* Responsive Adjustments */
  @media (max-width: 768px) {
    .studio-sidebar {
      position: absolute;
      left: 0;
      top: 56px;
      bottom: 0;
      z-index: 45;
      box-shadow: var(--shadow-elevation-3);
    }
    .agents-catalog-grid {
      grid-template-columns: 1fr;
    }
    .capabilities-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
