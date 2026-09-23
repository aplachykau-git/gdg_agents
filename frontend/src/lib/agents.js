import { DEFAULT_APPS } from './config.js';

export function cleanAuthorName(author) {
  if (!author || typeof author !== 'string') return '';
  return author.replace(/^Active Context:\s*/i, '').trim();
}

export function getAgentTheme(author) {
  if (!author) return { color: 'var(--primary-accent)', bg: 'var(--primary-accent-container)', label: 'Agent', icon: 'layers' };
  const clean = cleanAuthorName(author);
  const lower = clean.toLowerCase();
  if (lower.includes('root') || lower === 'main' || lower.includes('orchestrator')) return { color: 'var(--agent-root)', bg: 'var(--bg-root)', label: 'Main', icon: 'layers' };
  if (lower.includes('receipt')) return { color: 'var(--agent-receipt)', bg: 'var(--bg-receipt)', label: 'Receipt Scanner', icon: 'receipt' };
  if (lower.includes('video') || lower.includes('avatar')) return { color: 'var(--agent-video)', bg: 'var(--bg-video)', label: 'Live Video Editor', icon: 'video' };
  if (lower.includes('linkedin')) return { color: 'var(--agent-linkedin)', bg: 'var(--bg-linkedin)', label: 'LinkedIn Planner', icon: 'share' };
  if (lower.includes('registration')) return { color: 'var(--agent-registration)', bg: 'var(--bg-registration)', label: 'Registrations Manager', icon: 'users' };
  if (lower.includes('planner')) return { color: 'var(--agent-planner)', bg: 'var(--bg-planner)', label: 'Event Scheduler', icon: 'calendar' };
  if (lower.includes('agenda')) return { color: 'var(--agent-agenda)', bg: 'var(--bg-agenda)', label: 'Agenda Formatter', icon: 'clock' };
  if (lower.includes('office') || lower.includes('secretary')) return { color: 'var(--agent-office)', bg: 'var(--bg-office)', label: 'Office Secretary', icon: 'mail' };
  
  const formatted = clean.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  return { color: 'var(--primary-accent)', bg: 'var(--primary-accent-container)', label: formatted, icon: 'layers' };
}

export function getAgentIconName(agentId) {
  return getAgentTheme(agentId).icon || 'layers';
}

export function getAgentHeading(agentId) {
  if (!agentId) return 'Main Coordinator';
  const clean = cleanAuthorName(agentId).toLowerCase();
  if (clean.includes('root') || clean === 'main' || clean.includes('orchestrator')) return 'Main Coordinator';
  if (clean.includes('receipt')) return 'Receipt Scanner & OCR';
  if (clean.includes('video') || clean.includes('avatar')) return 'Live Video Editor';
  if (clean.includes('linkedin')) return 'LinkedIn Planner';
  if (clean.includes('registration')) return 'Registrations Manager';
  if (clean.includes('planner')) return 'Event Scheduler';
  if (clean.includes('agenda')) return 'Agenda Formatter';
  if (clean.includes('office') || clean.includes('secretary')) return 'Office Secretary';
  return 'Specialized Agent';
}

export function getAgentDescription(agentId) {
  if (!agentId) return 'Root coordinator agent for Community AI Studio.';
  const clean = cleanAuthorName(agentId).toLowerCase();
  if (clean.includes('root') || clean === 'main' || clean.includes('orchestrator')) {
    return 'Coordinates tasks across agents and answers questions for your community events.';
  }
  if (clean.includes('receipt')) {
    return 'Scans receipts, checks live bank exchange rates, and creates expense reports in Google Drive.';
  }
  if (clean.includes('video') || clean.includes('avatar')) {
    return 'Turns speaker portrait photos into animated video intros and speaker cards.';
  }
  if (clean.includes('linkedin')) {
    return 'Writes engaging speaker announcements, event invitations, and post-event recaps with hashtags.';
  }
  if (clean.includes('registration')) {
    return 'Cleans attendee lists, removes duplicates, and organizes confirmed and waitlisted guests.';
  }
  if (clean.includes('planner')) {
    return 'Scans meetup calendars and holidays to find the best dates for community events.';
  }
  if (clean.includes('agenda')) {
    return 'Creates structured event schedules with talks, networking sessions, and break times.';
  }
  if (clean.includes('office') || clean.includes('secretary')) {
    return 'Prepares building visitor access requests and meeting room reservation emails.';
  }
  return 'Ready to assist with your community tasks.';
}

export function getAgentStarterPrompts(agentId) {
  if (!agentId) return [];
  const clean = cleanAuthorName(agentId).toLowerCase();
  if (clean.includes('root') || clean === 'main' || clean.includes('orchestrator')) {
    return [
      { icon: 'receipt', text: 'Process receipts and export an expense report', prompt: 'Process receipts and export an expense report' },
      { icon: 'video', text: 'Create speaker intro video and animated card', prompt: 'Create speaker intro video and animated card' },
      { icon: 'megaphone', text: 'Draft LinkedIn speaker spotlight announcement', prompt: 'Draft LinkedIn speaker spotlight announcement' },
      { icon: 'calendar', text: 'Find optimal meetup date next month without collisions', prompt: 'Find optimal meetup date next month without collisions' },
      { icon: 'users', text: 'Clean registration CSV and partition attendees by capacity', prompt: 'Clean registration CSV and partition attendees by capacity' },
      { icon: 'clock', text: 'Format event agenda with 2 speaker talks and networking', prompt: 'Format event agenda with 2 speaker talks and networking' },
      { icon: 'mail', text: 'Draft office keys access and Event Hub reservation email', prompt: 'Draft office keys access and Event Hub reservation email' }
    ];
  }
  if (clean.includes('receipt')) {
    return [
      { icon: 'receipt', text: 'Scan attached receipt and convert to PLN using live rates', prompt: 'Scan attached receipt and convert to PLN using live rates' },
      { icon: 'file-text', text: 'Extract line items and export expense report to Google Docs', prompt: 'Extract line items and export expense report to Google Docs' }
    ];
  }
  if (clean.includes('video') || clean.includes('avatar')) {
    return [
      { icon: 'video', text: 'Generate speaker intro video with Omni', prompt: 'Generate speaker intro video with Omni' },
      { icon: 'image', text: 'Enhance portrait photo and render animated speaker card', prompt: 'Enhance portrait photo and render animated speaker card' }
    ];
  }
  if (clean.includes('linkedin')) {
    return [
      { icon: 'megaphone', text: 'Draft speaker announcement post with registration link', prompt: 'Draft speaker announcement post with registration link' },
      { icon: 'file-pen-line', text: 'Generate 3 event recap post options with hashtags', prompt: 'Generate 3 event recap post options with hashtags' }
    ];
  }
  if (clean.includes('registration')) {
    return [
      { icon: 'users', text: 'Clean, deduplicate, and sort attendee registration list', prompt: 'Clean, deduplicate, and sort attendee registration list' },
      { icon: 'clipboard-list', text: 'Split confirmed attendees (capacity 50) and waitlist into DOCX', prompt: 'Split confirmed attendees (capacity 50) and waitlist into DOCX' }
    ];
  }
  if (clean.includes('planner')) {
    return [
      { icon: 'calendar', text: 'Find best meetup date next month avoiding conflicts', prompt: 'Find best meetup date next month avoiding conflicts' },
      { icon: 'map-pin', text: 'Check Polish public holidays and tech events in Krakow', prompt: 'Check Polish public holidays and tech events in Krakow' }
    ];
  }
  if (clean.includes('agenda')) {
    return [
      { icon: 'clock', text: 'Format agenda with 3 speaker talks and networking', prompt: 'Format agenda with 3 speaker talks and networking' }
    ];
  }
  if (clean.includes('office') || clean.includes('secretary')) {
    return [
      { icon: 'mail', text: 'Draft visitor keys access request email for upcoming event', prompt: 'Draft visitor keys access request email for upcoming event' },
      { icon: 'building', text: 'Draft Event Hub room reservation request email', prompt: 'Draft Event Hub room reservation request email' }
    ];
  }
  return [];
}

export function getAgentFromToolName(name) {
  if (!name || typeof name !== 'string') return null;
  const lower = name.toLowerCase();

  // 1. Direct transfer_to_* pattern
  if (lower.startsWith('transfer_to_') || lower.startsWith('transferto')) {
    const sub = lower.replace(/^transfer_to_|^transferto/, '');
    if (sub.includes('video')) return 'video_editor';
    if (sub.includes('receipt')) return 'receipt_scanner';
    if (sub.includes('linkedin') || sub.includes('post')) return 'linkedin_post_generator';
    if (sub.includes('registration')) return 'registration_manager';
    if (sub.includes('planner') || sub.includes('event')) return 'event_planner';
    if (sub.includes('agenda')) return 'agenda_generator';
    if (sub.includes('office') || sub.includes('secretary')) return 'office_secretary';
  }

  // 2. Specific known tools
  // Video Editor tools:
  if (
    lower.includes('portrait') ||
    lower.includes('animate_photo') ||
    lower.includes('composer') ||
    lower.includes('render_composer') ||
    lower.includes('speaker_video') ||
    lower.includes('validate_metadata') ||
    lower.includes('stage_uploaded_media')
  ) {
    return 'video_editor';
  }

  // Receipt Scanner tools:
  if (
    lower.includes('receipt') ||
    lower.includes('usd_pln') ||
    lower.includes('convert_currency') ||
    lower.includes('google_doc') ||
    lower.includes('expense')
  ) {
    return 'receipt_scanner';
  }

  // Registration Manager tools:
  if (
    lower.includes('registration') ||
    lower.includes('filter_and_clean') ||
    lower.includes('process_registrations') ||
    lower.includes('stage_manual_text') ||
    lower.includes('transliterate')
  ) {
    return 'registration_manager';
  }

  // Event Planner tools:
  if (
    lower.includes('holidays') ||
    lower.includes('optimal_meetup') ||
    lower.includes('meetup_date') ||
    lower.includes('google_search')
  ) {
    return 'event_planner';
  }

  // Agenda Formatter tools:
  if (lower.includes('agenda') || lower.includes('timeline')) {
    return 'agenda_generator';
  }

  // Office Secretary tools:
  if (
    lower.includes('office_email') ||
    lower.includes('visitor_access') ||
    lower.includes('reservation_email')
  ) {
    return 'office_secretary';
  }

  return null;
}

export function getEventAgent(ev, appsList = DEFAULT_APPS) {
  if (!ev) return null;
  
  // 1. Check direct actions transfer
  const actionTarget = ev.actions?.transfer_to_agent || ev.actions?.transferToAgent;
  if (actionTarget) {
    const resolved = resolveAgentId(actionTarget, appsList);
    if (resolved) return resolved;
  }

  // 2. Check parts for tool calls, function responses, or transfer args
  if (ev.content?.parts) {
    for (const part of ev.content.parts) {
      const fc = part.function_call || part.functionCall;
      if (fc) {
        if (fc.name === 'transfer_to_agent' || fc.name === 'transferToAgent') {
          const target = fc.args?.agent_name || fc.args?.target_agent || fc.args?.agentName;
          if (target) {
            const resolved = resolveAgentId(target, appsList);
            if (resolved) return resolved;
          }
        }
        const toolAgent = getAgentFromToolName(fc.name);
        if (toolAgent) return toolAgent;
      }

      const fr = part.function_response || part.functionResponse;
      if (fr) {
        if (fr.name === 'transfer_to_agent' || fr.name === 'transferToAgent') {
          const target = fr.response?.agent_name || fr.response?.target_agent || fr.response?.agentName;
          if (target) {
            const resolved = resolveAgentId(target, appsList);
            if (resolved) return resolved;
          }
        }
        const toolAgent = getAgentFromToolName(fr.name);
        if (toolAgent) return toolAgent;
      }
    }
  }

  // 3. Check author if it is a specific subagent (not generic root/main/user)
  if (ev.author && ev.author !== 'user') {
    const clean = cleanAuthorName(ev.author).toLowerCase();
    if (clean !== 'root_agent' && clean !== 'root' && clean !== 'main' && clean !== 'orchestrator') {
      const resolved = resolveAgentId(ev.author, appsList);
      if (resolved) return resolved;
    }
  }

  // 4. If author is root_agent / main, return 'root_agent'
  if (ev.author && ev.author !== 'user') {
    return resolveAgentId(ev.author, appsList) || 'root_agent';
  }

  return null;
}

export function resolveAgentId(author, appsList = DEFAULT_APPS) {
  if (!author) return null;
  const clean = cleanAuthorName(author).toLowerCase().trim();
  if (!clean || clean === 'user') return null;

  // 1. Direct match on name or root_agent_name
  for (const app of appsList) {
    if (app.name.toLowerCase() === clean) return app.name;
    if (app.root_agent_name && app.root_agent_name.toLowerCase() === clean) return app.name;
  }

  // 2. Specific known agent mappings
  if (clean === 'root' || clean === 'main' || clean === 'orchestrator' || clean === 'root_agent') return 'root_agent';
  if (clean.includes('receipt')) return 'receipt_scanner';
  if (clean.includes('video') || clean.includes('avatar')) return 'video_editor';
  if (clean.includes('linkedin') || clean.includes('post')) return 'linkedin_post_generator';
  if (clean.includes('registration')) return 'registration_manager';
  if (clean.includes('planner') || clean.includes('event')) return 'event_planner';
  if (clean.includes('agenda')) return 'agenda_generator';
  if (clean.includes('office') || clean.includes('secretary')) return 'office_secretary';

  // 3. Fallback partial match with appsList
  for (const app of appsList) {
    const base = app.name.toLowerCase().replace(/_agent$/, '');
    if (clean.includes(base) || base.includes(clean)) return app.name;
  }

  return null;
}

export function getActiveAgentFromEvents(eventsList, fallback = 'root_agent', appsList = DEFAULT_APPS) {
  if (!eventsList || eventsList.length === 0) return fallback;
  for (let i = eventsList.length - 1; i >= 0; i--) {
    const ev = eventsList[i];
    if (!ev || ev.author === 'user') continue;
    
    // Check if event has a specific sub-agent identity or delegation
    const evAgent = getEventAgent(ev, appsList);
    if (evAgent && evAgent !== 'root_agent') {
      return evAgent;
    }
    
    // If the event is explicitly from a sub-agent author
    if (ev.author) {
      const resolved = resolveAgentId(ev.author, appsList);
      if (resolved && resolved !== 'root_agent') {
        return resolved;
      }
    }
  }
  return fallback;
}

export const STATUS_TICKERS = {
  root_agent: [
    'Main agent coordinating request...',
    'Analyzing routing parameters...',
    'Invoking specialized sub-agents...',
    'Verifying execution prerequisites...'
  ],
  receipt_scanner: [
    'Fetching live banking exchange rates...',
    'Scanning attachment with Vision OCR...',
    'Converting expenses to EUR/USD/PLN...',
    'Checking historical structures (Anti-re-processing)...',
    'Translating item details to English...',
    'Generating Docs Expense Report...'
  ],
  video_editor: [
    'Staging uploaded photo in workspace assets...',
    'Validating speaker details...',
    'Analyzing portrait photo...',
    'Generating animated background video with Omni...',
    'Composing speaker video card...',
    'Rendering animated video card and preview poster...',
    'Saving generated assets...'
  ],
  registration_manager: [
    'Scanning participant registration list...',
    'Filtering test and duplicate registrations...',
    'Sorting attendees alphabetically...',
    'Organizing attendance roster...'
  ],
  event_planner: [
    'Checking meetup calendars...',
    'Checking public holidays and long weekends...',
    'Finding optimal dates for meetup...'
  ],
  agenda_generator: [
    'Calculating event timeline...',
    'Formatting speaker session durations...',
    'Adding networking and break times...',
    'Generating clean schedule summary...'
  ],
  office_secretary: [
    'Validating event details...',
    'Composing visitor access request...',
    'Drafting room reservation email...'
  ]
};

export function getFriendlyToolCall(name, args) {
  if (name === 'transfer_to_agent' || name === 'transferToAgent') {
    const target = args?.agent_name || args?.target_agent || args?.agentName || '';
    const theme = getAgentTheme(target);
    return `Delegating task to ${theme.label || 'specialized sub-agent'}...`;
  }

  const mappings = {
    transfer_to_video_editor: () => "Delegating task to Live Video Editor (A2A)...",
    transfer_to_receipt_scanner: () => "Delegating task to Receipt Scanner (A2A)...",
    transfer_to_linkedin_post_generator: () => "Delegating task to LinkedIn Planner...",
    transfer_to_event_planner: () => "Delegating task to Event Scheduler...",
    transfer_to_registration_manager: () => "Delegating task to Registrations Manager...",
    transfer_to_agenda_generator: () => "Delegating task to Agenda Formatter...",
    transfer_to_office_secretary: () => "Delegating task to Office Secretary...",

    update_speaker: (a) => a?.new_speaker ? "🪪 Starting a card for a new speaker..." : "🪪 Saving speaker details...",
    propose_scenarios: (a) => a?.creative_guidance ? `🎬 Inventing new scenarios (${a.creative_guidance})...` : "🎬 Inventing 5 cinematic scenarios...",
    show_scenarios: () => "🗂️ Reopening saved scenarios...",
    render_video: (a) => a?.option ? `🎞️ Rendering option ${a.option}... (usually 1–3 min)` : "🎞️ Rendering speaker card... (usually 1–3 min)",
    get_card_status: () => "🔎 Checking the saved card...",
    present_email_draft: () => "✉️ Preparing the e-mail card...",
    present_meetup_dates: () => "📅 Validating the recommended dates...",
    stage_uploaded_media: () => "📦 Staging attached media to workspace assets...",
    validate_metadata: (a) => `📏 Validating text character limits for "${a?.name || 'speaker'}"...`,
    verify_portrait_photo: () => "🔍 Running facial detection on portrait photo...",
    animate_photo: (a) => `🎬 Animating 9:16 background video with Omni (${a?.creative_prompt ? 'AI Prompt' : 'Direct Video'})...`,
    update_composer: (a) => `🎨 Updating HTML5 composition layout for "${a?.name || 'speaker'}"...`,
    render_composer: () => "🚀 HyperFrames pipeline rendering 1080p MP4, GIF & Poster...",

    get_usd_pln_rate: () => "💱 Fetching live banking exchange rates (USD/PLN)...",
    read_receipt_file: () => "🧾 Analyzing receipt image via Gemini 3.7 Flash Vision OCR...",
    export_summary_to_google_doc: () => "📄 Exporting approved expense report to Google Docs...",
    scan_receipt_with_vision: () => "🧾 Extracting items and taxes via Vision OCR...",
    convert_currency: () => "💱 Converting currencies to PLN using exchange rates...",
    export_to_google_docs: () => "📄 Exporting expense report to Google Docs template...",

    filter_and_clean_registrations: () => "👥 Cleaning, deduplicating, and partitioning registrations...",
    process_registrations: () => "👥 Parsing attendee CSV and generating DOCX roster...",
    verify_and_deduplicate_registrations: () => "🔍 Auditing attendee list and removing duplicates...",
    transliterate_cyrillic_to_latin: () => "🔤 Transliterating Cyrillic attendee names to Latin...",
    stage_manual_text_registrations: () => "📝 Staging attendee registration records...",
    get_public_holidays: () => "📅 Checking statutory public holidays from Nager.Date...",
    find_optimal_meetup_date: () => "📅 Scanning calendars, holidays, and meetup conflicts...",
    generate_agenda: () => "⏱️ Formatting structured timeline and speaker agenda...",
    generate_office_email: () => "✉️ Drafting office access and event reservation email...",
    generate_visitor_access_request: () => "✉️ Generating building key & access request..."
  };

  if (mappings[name]) {
    return mappings[name](args || {});
  }
  const formatted = name.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  return `Executing ${formatted}...`;
}

export function isToolResponseError(response) {
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

export function getToolErrorMessage(response) {
  if (!response) return 'Tool execution failed';
  if (typeof response === 'object') {
    return response.error || response.error_message || response.errorMessage || response.exception || response.detail || JSON.stringify(response);
  }
  return String(response);
}

export function getFriendlyToolResponse(name, response, args) {
  if (isToolResponseError(response)) {
    return `❌ Tool error: ${getToolErrorMessage(response)}`;
  }
  if (name === 'transfer_to_agent' || name === 'transferToAgent') {
    const target = args?.agent_name || args?.target_agent || args?.agentName || response?.agent_name || '';
    const theme = getAgentTheme(target);
    return `Workflow handed off to ${theme.label || 'specialized sub-agent'}.`;
  }
  const mappings = {
    transfer_to_video_editor: () => "Workflow handed off to Live Video Editor.",
    transfer_to_receipt_scanner: () => "Workflow handed off to Receipt Scanner.",
    transfer_to_linkedin_post_generator: () => "Workflow handed off to LinkedIn Planner.",
    transfer_to_event_planner: () => "Workflow handed off to Event Scheduler.",
    transfer_to_registration_manager: () => "Workflow handed off to Registrations Manager.",
    transfer_to_agenda_generator: () => "Workflow handed off to Agenda Formatter.",
    transfer_to_office_secretary: () => "Workflow handed off to Office Secretary.",

    update_speaker: (r) => r?.missing_fields?.length ? `Details saved. Missing: ${r.missing_fields.join(', ')}` : "Speaker details saved.",
    propose_scenarios: (r) => r?.scenarios?.length ? `${r.scenarios.length} scenarios ready.` : (r?.message || "Scenarios step finished."),
    show_scenarios: (r) => r?.scenarios?.length ? "Saved scenarios reopened." : (r?.message || "No saved scenarios."),
    render_video: (r) => r?.status === 'success' ? "Speaker card rendered." : (r?.message || "Render step finished."),
    get_card_status: () => "Card status checked.",
    present_email_draft: (r) => r?.status === 'error' ? (r.message || "E-mail needs changes.") : "E-mail draft ready.",
    present_meetup_dates: (r) => r?.status === 'error' ? (r.message || "Dates rejected, picking others.") : "Dates validated.",
    stage_uploaded_media: () => "Media staged in workspace assets.",
    validate_metadata: () => "Speaker details verified.",
    verify_portrait_photo: () => "Portrait photo verified.",
    animate_photo: () => "Background video generated with Omni.",
    update_composer: () => "Speaker card layout updated.",
    render_composer: () => "Animated video card rendered.",

    get_usd_pln_rate: (r) => r?.rate ? `Rate fetched: 1 USD = ${r.rate} PLN` : "Exchange rate fetched.",
    read_receipt_file: () => "Receipt extracted.",
    export_summary_to_google_doc: (r) => r?.document_url ? `Expense report ready: ${r.document_url}` : "Document exported.",
    scan_receipt_with_vision: () => "Receipt parsed.",
    convert_currency: () => "Currency converted.",
    export_to_google_docs: () => "Expense report exported to Google Docs.",

    filter_and_clean_registrations: () => "Registration roster cleaned.",
    process_registrations: () => "Registration records organized into roster.",
    verify_and_deduplicate_registrations: () => "Attendee list audit complete and duplicates filtered.",
    transliterate_cyrillic_to_latin: () => "Cyrillic names transliterated into Latin script.",
    stage_manual_text_registrations: () => "Manual registrations staged.",
    get_public_holidays: () => "Public holidays checked.",
    find_optimal_meetup_date: () => "Meetup dates evaluated.",
    generate_agenda: () => "Agenda timeline created.",
    generate_office_email: () => "Email template generated.",
    generate_visitor_access_request: () => "Access request draft generated."
  };

  if (mappings[name]) {
    return mappings[name](response || {}, args || {});
  }
  return "Step completed successfully.";
}

export function getEventError(event) {
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

export function isIntermediateEvent(event) {
  if (!event) return true;
  if (event.author === 'user') return false;
  if (getEventError(event)) return false;
  if (event.output && (event.output.summary || event.output.assets)) return false;
  if (!event.content || !event.content.parts || event.content.parts.length === 0) return true;

  const hasVisibleContent = event.content.parts.some(part => {
    // Remote (A2A) agents stream their final answer twice: once as a "thought" status update and
    // once as the final artifact. Thought-only text is therefore not shown on its own.
    if (part.text && part.text.trim() !== '' && !part.thought) return true;
    if (part.inline_data || part.inlineData) return true;
    if (part.function_call || part.functionCall) return true;
    if (part.function_response || part.functionResponse) return true;
    return false;
  });

  return !hasVisibleContent;
}

export function shouldShowDelegationHandoff(event, idx, allEvents) {
  if (!event || event.author === 'user') return false;
  const currentAuthor = cleanAuthorName(event.author).toLowerCase();
  if (!currentAuthor || currentAuthor === 'root_agent' || currentAuthor === 'root') return false;
  
  for (let i = idx - 1; i >= 0; i--) {
    const prev = allEvents[i];
    if (prev && prev.author !== 'user') {
      const prevAuthor = cleanAuthorName(prev.author).toLowerCase();
      return prevAuthor !== currentAuthor;
    }
  }
  return true;
}
