import { marked } from 'marked';

export const DEFAULT_APPS = [
  { name: 'root_agent', root_agent_name: 'Main' },
  { name: 'receipt_scanner', root_agent_name: 'Receipt Scanner' },
  { name: 'video_editor', root_agent_name: 'Live Video Editor' },
  { name: 'linkedin_post_generator', root_agent_name: 'LinkedIn Planner' },
  { name: 'registration_manager', root_agent_name: 'Registrations Manager' },
  { name: 'event_planner', root_agent_name: 'Event Scheduler' },
  { name: 'agenda_generator', root_agent_name: 'Agenda Formatter' },
  { name: 'office_secretary', root_agent_name: 'Office Secretary' }
];

export const DEFAULT_CONFIG = {
  communityName: 'GDG Krakow'
};

export function getAppConfig() {
  if (typeof window === 'undefined') return DEFAULT_CONFIG;
  try {
    const saved = localStorage.getItem('community_studio_config') || localStorage.getItem('gdg_studio_config');
    if (saved) {
      return { ...DEFAULT_CONFIG, ...JSON.parse(saved) };
    }
  } catch (e) {
    console.error('Failed to read config from localStorage:', e);
  }
  return DEFAULT_CONFIG;
}

export function saveAppConfig(cfg) {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem('community_studio_config', JSON.stringify(cfg));
  } catch (e) {
    console.error('Failed to save config to localStorage:', e);
  }
}

export const MAX_INPUT_TOKENS = 8192;

export function cleanAuthorName(author) {
  if (!author || typeof author !== 'string') return '';
  return author.replace(/^Active Context:\s*/i, '').trim();
}

export function getAgentTheme(author) {
  if (!author) return { color: 'var(--primary-accent)', bg: 'var(--primary-accent-container)', label: 'Agent' };
  const clean = cleanAuthorName(author);
  const lower = clean.toLowerCase();
  if (lower.includes('root') || lower === 'main' || lower.includes('orchestrator')) return { color: 'var(--agent-root)', bg: 'var(--bg-root)', label: 'Main' };
  if (lower.includes('receipt')) return { color: 'var(--agent-receipt)', bg: 'var(--bg-receipt)', label: 'Receipt Scanner' };
  if (lower.includes('video') || lower.includes('avatar')) return { color: 'var(--agent-video)', bg: 'var(--bg-video)', label: 'Live Video Editor' };
  if (lower.includes('linkedin')) return { color: 'var(--agent-linkedin)', bg: 'var(--bg-linkedin)', label: 'LinkedIn Planner' };
  if (lower.includes('registration')) return { color: 'var(--agent-registration)', bg: 'var(--bg-registration)', label: 'Registrations Manager' };
  if (lower.includes('planner')) return { color: 'var(--agent-planner)', bg: 'var(--bg-planner)', label: 'Event Scheduler' };
  if (lower.includes('agenda')) return { color: 'var(--agent-agenda)', bg: 'var(--bg-agenda)', label: 'Agenda Formatter' };
  if (lower.includes('office') || lower.includes('secretary')) return { color: 'var(--agent-office)', bg: 'var(--bg-office)', label: 'Office Secretary' };
  
  const formatted = clean.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  return { color: 'var(--primary-accent)', bg: 'var(--primary-accent-container)', label: formatted };
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
    lower.includes('stage_manual_text')
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
    'Staging uploaded photo/video in workspace assets...',
    'Validating speaker metadata & text limits...',
    'Analyzing portrait facial landmarks...',
    'Executing AI Outpainting to 9:16 vertical canvas...',
    'Generating Veo cinematic background video animation...',
    'Injecting speaker typography into HyperFrames composition...',
    'Launching headless Chromium rendering pipeline...',
    'Compiling 1080p MP4 video & stripping audio tracks...',
    'Encoding high-framerate animated GIF...',
    'Extracting high-resolution card poster...',
    'Uploading generated assets to Google Cloud Storage...'
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

export function getFriendlyToolCall(name, args) {
  if (name === 'transfer_to_agent' || name === 'transferToAgent') {
    const target = args?.agent_name || args?.target_agent || args?.agentName || '';
    const theme = getAgentTheme(target);
    return `🔄 Delegating task to ${theme.label || 'specialized sub-agent'}...`;
  }

  const mappings = {
    transfer_to_video_editor: () => "🔄 Delegating task to Live Video Editor (A2A)...",
    transfer_to_receipt_scanner: () => "🔄 Delegating task to Receipt Scanner (A2A)...",
    transfer_to_linkedin_post_generator: () => "🔄 Delegating task to LinkedIn Planner...",
    transfer_to_event_planner: () => "🔄 Delegating task to Event Scheduler...",
    transfer_to_registration_manager: () => "🔄 Delegating task to Registrations Manager...",
    transfer_to_agenda_generator: () => "🔄 Delegating task to Agenda Formatter...",
    transfer_to_office_secretary: () => "🔄 Delegating task to Office Secretary...",

    stage_uploaded_media: () => "📦 Staging attached media to workspace assets...",
    validate_metadata: (a) => `📏 Validating text character limits for "${a?.name || 'speaker'}"...`,
    verify_portrait_photo: () => "🔍 Running facial detection on portrait photo...",
    animate_photo: (a) => `🎬 Animating 9:16 background video with Veo (${a?.creative_prompt ? 'AI Prompt' : 'Direct Video'})...`,
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

    stage_uploaded_media: () => "Media staged in workspace assets.",
    validate_metadata: () => "Speaker metadata & text character limits verified.",
    verify_portrait_photo: () => "Face detected and aligned.",
    animate_photo: () => "Background video animation generated via Veo.",
    update_composer: () => "HyperFrames HTML5 composition layout updated.",
    render_composer: () => "1080p MP4, GIF & Poster rendered and stored in Cloud Storage.",

    get_usd_pln_rate: (r) => r?.rate ? `Rate fetched: 1 USD = ${r.rate} PLN` : "Exchange rate fetched.",
    read_receipt_file: () => "Receipt OCR extracted.",
    export_summary_to_google_doc: (r) => r?.document_url ? `Expense doc ready: ${r.document_url}` : "Document exported.",
    scan_receipt_with_vision: () => "Receipt parsed.",
    convert_currency: () => "Currency converted.",
    export_to_google_docs: () => "Document exported to Google Docs.",

    filter_and_clean_registrations: () => "Registration roster cleaned.",
    process_registrations: () => "Registration records processed into DOCX.",
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
    if (part.text && part.text.trim() !== '') return true;
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

export function renderMarkdown(text) {
  if (!text) return '';
  try {
    return marked.parse(text);
  } catch (e) {
    console.error("Failed to parse markdown:", e);
    return text.replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
}

export function isAgendaOutput(text, author) {
  if (!text) return false;
  const clean = cleanAuthorName(author).toLowerCase();
  const hasAgendaKeyword = text.toUpperCase().includes('AGENDA');
  const hasTimePattern = /\d{1,2}:\d{2}\s*[-–—]/.test(text);
  const hasAgendaEmojis = text.includes('🎟️') || text.includes('🚀') || text.includes('🎤') || text.includes('🍕');
  
  if (clean.includes('agenda') && (hasTimePattern || hasAgendaKeyword)) return true;
  if (hasAgendaKeyword && hasTimePattern && hasAgendaEmojis) return true;
  return false;
}

export function extractEmailDraft(text, author) {
  if (!text) return null;
  const clean = cleanAuthorName(author).toLowerCase();
  
  // Search for Subject: or Тема: header in the text
  const subjectMatch = text.match(/(?:^|\n)(?:```(?:text|markdown|email)?\s*\n)?(?:\*\*|\*|#+\s*)?(?:Subject|Тема)\s*:\s*([^\n]+)\n([\s\S]+)/i);
  if (!subjectMatch) return null;

  const fullMatchIndex = text.indexOf(subjectMatch[0]);
  const intro = fullMatchIndex > 0 ? text.substring(0, fullMatchIndex).trim() : '';

  let subject = subjectMatch[1].replace(/[`*#]/g, '').trim();
  let body = subjectMatch[2].trim();

  // Clean trailing code fences from body
  body = body.replace(/```\s*$/, '').trim();

  if (!subject || !body) return null;

  const fullText = `Subject: ${subject}\n\n${body}`;
  const gmailUrl = `https://mail.google.com/mail/?view=cm&fs=1&tf=1&su=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  const mailtoUrl = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;

  return {
    subject,
    body,
    fullText,
    intro,
    gmailUrl,
    mailtoUrl
  };
}

export function parseResponseVariants(text, author) {
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

export function extractMediaAssets(text) {
  if (!text) return null;

  const urlRegex = /(https?:\/\/[^\s\)\"\'<>]+?\.(?:mp4|webm|mov|gif|png|jpg|jpeg|webp)(?:\?[^\s\)\"\'<>]*)?)/gi;
  const matches = [...text.matchAll(urlRegex)].map(m => m[1]);

  if (!matches || matches.length === 0) return null;

  let videoUrl = matches.find(u => u.toLowerCase().includes('.mp4') || u.toLowerCase().includes('.webm') || u.toLowerCase().includes('.mov'));
  let gifUrl = matches.find(u => u.toLowerCase().includes('.gif'));
  let posterUrl = matches.find(u => u.toLowerCase().includes('_poster.') || u.toLowerCase().includes('poster') || (u.toLowerCase().includes('.png') && !u.toLowerCase().includes('_avatar')));
  let avatarUrl = matches.find(u => u.toLowerCase().includes('_avatar.') || u.toLowerCase().includes('avatar'));

  if (!posterUrl) {
    posterUrl = matches.find(u => u !== videoUrl && u !== gifUrl && u !== avatarUrl);
  }

  if (!videoUrl && !gifUrl && !posterUrl) return null;

  const nameMatch = text.match(/\*\*Speaker Name:\*\*\s*([^\n]+)/i) || text.match(/name:\s*"?([^"\n]+)"?/i) || text.match(/speaker:\s*"?([^"\n]+)"?/i);
  const titleMatch = text.match(/\*\*Talk Title:\*\*\s*([^\n]+)/i) || text.match(/title:\s*"?([^"\n]+)"?/i) || text.match(/talk:\s*"?([^"\n]+)"?/i);
  const companyMatch = text.match(/\*\*Position & Company:\*\*\s*([^\n]+)/i) || text.match(/position_company:\s*"?([^"\n]+)"?/i) || text.match(/company:\s*"?([^"\n]+)"?/i);

  return {
    videoUrl,
    gifUrl,
    posterUrl,
    avatarUrl,
    allUrls: matches,
    speakerName: nameMatch ? nameMatch[1].replace(/[`*]/g, '').trim() : '',
    talkTitle: titleMatch ? titleMatch[1].replace(/[`*]/g, '').trim() : '',
    company: companyMatch ? companyMatch[1].replace(/[`*]/g, '').trim() : ''
  };
}

export async function downloadDirectFile(url, suggestedFilename) {
  if (!url) return;
  const filename = suggestedFilename || url.split('/').pop()?.split('?')[0] || 'media_asset';

  try {
    const separator = url.includes('?') ? '&' : '?';
    const downloadUrl = `${url}${separator}dl=1&_t=${Date.now()}`;
    const res = await fetch(downloadUrl, { mode: 'cors' });
    if (!res.ok) {
      throw new Error(`Server returned HTTP status ${res.status}`);
    }
    const blob = await res.blob();
    const blobUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = blobUrl;
    link.download = filename;
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    setTimeout(() => {
      document.body.removeChild(link);
      window.URL.revokeObjectURL(blobUrl);
    }, 2000);
  } catch (err) {
    console.warn('Direct blob fetch failed:', err);
    // If it's a relative /results/ path, try direct download anchor
    if (url.startsWith('/results/') || url.startsWith('http')) {
      const fallbackLink = document.createElement('a');
      fallbackLink.href = url;
      fallbackLink.download = filename;
      fallbackLink.target = '_blank';
      fallbackLink.rel = 'noopener noreferrer';
      fallbackLink.click();
    } else {
      alert(`Could not download file: ${err.message || 'File not found'}`);
    }
  }
}

export function cleanTextForMediaDisplay(text) {
  if (!text) return '';

  const lines = text.split('\n');
  const filteredLines = lines.filter(line => {
    const trimmed = line.trim();
    if (
      trimmed.match(/^[-*•]\s*(?:🎥|🖼️|📸|👤)?.*(?:https?:\/\/[^\s\)]+?\.(?:mp4|gif|png|jpg|jpeg|webp)|\[(?:Download|View)[^\]]*\])/i) ||
      trimmed.match(/^\[(?:Download|View)[^\]]*\]\(https?:\/\/[^\s\)]+\)/i) ||
      trimmed.match(/^https?:\/\/[^\s\)]+?\.(?:mp4|gif|png|jpg|jpeg|webp)$/i)
    ) {
      return false;
    }
    return true;
  });

  return filteredLines.join('\n').trim();
}

export function extractDocumentAssets(text) {
  if (!text) return null;

  // Regex to match .docx, .xlsx, .csv, .pdf URLs or direct markdown links (including file:// and /results/)
  const urlRegex = /(?:https?:\/\/[^\s\)\"\'<>]+|\/results\/[^\s\)\"\'<>]+|file:\/\/[^\s\)\"\'<>]+)\.(?:docx|xlsx|csv|pdf)(?:\?[^\s\)\"\'<>]*)?/gi;
  const rawMatches = text.match(urlRegex) || [];

  if (rawMatches.length === 0) return null;

  // Normalize file:// links to /results/<filename> so browser can fetch them via Vite middleware
  const matches = rawMatches.map(u => {
    if (u.startsWith('file://')) {
      const fn = u.split('/').pop()?.split('?')[0];
      return `/results/${fn}`;
    }
    return u;
  });

  const docxUrl = matches.find(u => u.toLowerCase().includes('.docx'));
  const csvUrl = matches.find(u => u.toLowerCase().includes('.csv'));
  const xlsxUrl = matches.find(u => u.toLowerCase().includes('.xlsx'));
  const pdfUrl = matches.find(u => u.toLowerCase().includes('.pdf'));

  const primaryUrl = docxUrl || xlsxUrl || csvUrl || pdfUrl || matches[0];
  const filename = primaryUrl.split('/').pop()?.split('?')[0] || 'Report.docx';

  // Determine doc type & label
  let fileType = 'DOCX';
  let typeLabel = 'Formatted Document (Word & Docs)';
  if (primaryUrl.toLowerCase().includes('.docx')) {
    fileType = 'DOCX';
    typeLabel = 'Word & Google Docs Compatible';
  } else if (primaryUrl.toLowerCase().includes('.xlsx')) {
    fileType = 'XLSX';
    typeLabel = 'Excel Spreadsheet';
  } else if (primaryUrl.toLowerCase().includes('.csv')) {
    fileType = 'CSV';
    typeLabel = 'CSV Spreadsheet Backup';
  } else if (primaryUrl.toLowerCase().includes('.pdf')) {
    fileType = 'PDF';
    typeLabel = 'PDF Document';
  }

  // Extract title if available in text
  const titleMatch = text.match(/(?:Expense Reimbursement Report|Expense Report|Reimbursement Report|Event Registration Document|Registration Document|Report)[\s\:\*\#\-]*([^\n]+)/i);

  const isRegistration =
    filename.toLowerCase().includes('registration') ||
    (text && (
      text.toLowerCase().includes('registration') ||
      text.includes('Confirmed Registrants') ||
      text.includes('Confirmed Attendees') ||
      text.includes('Waitlisted Registrants')
    ));

  // Extract embedded plain-text attendee roster if present
  const rosterMatch = text.match(/<!--\s*ATTENDEE_ROSTER_START\s*\n([\s\S]*?)\n\s*ATTENDEE_ROSTER_END\s*-->/i);
  const rosterText = rosterMatch ? rosterMatch[1].trim() : null;

  return {
    primaryUrl,
    docxUrl,
    csvUrl,
    xlsxUrl,
    pdfUrl,
    txtUrl: isRegistration ? '/results/registrations_list.txt' : null,
    rosterText,
    isRegistration,
    filename,
    fileType,
    typeLabel: isRegistration ? 'Event Attendee & Registration Document' : typeLabel,
    title: titleMatch ? titleMatch[0].replace(/[`*#]/g, '').trim() : (isRegistration ? 'Event Registration Roster' : filename),
    allUrls: matches
  };
}

export function cleanTextForDocumentDisplay(text) {
  if (!text) return '';

  // First strip all HTML comments (including embedded roster payloads)
  const cleanComments = text.replace(/<!--[\s\S]*?-->/g, '');

  const lines = cleanComments.split('\n');
  const filteredLines = lines.filter(line => {
    const trimmed = line.trim();
    if (
      // Markdown links with documents
      trimmed.match(/^[-*•]?\s*(?:📄|📑|📊|💾|📁|📥)?\s*.*(?:\/results\/|https?:\/\/|file:\/\/)[^\s\)]+?\.(?:docx|xlsx|csv|pdf)/i) ||
      trimmed.match(/^\[(?:Download|View|Expense|Successfully|Скачать)[^\]]*\]\([^\)]+\)/i) ||
      trimmed.match(/^(?:https?:\/\/|\/results\/|file:\/\/)[^\s\)]+?\.(?:docx|xlsx|csv|pdf)$/i) ||
      // Redundant download sentences
      trimmed.match(/^(?:Вы можете скачать|Скачать отчет|You can download the report|Download link|Generated Deliverables)/i) ||
      trimmed.match(/^[-*•]?\s*(?:📁|📥)\s*(?:Скачать|Download)/i) ||
      trimmed.match(/^###\s*(?:📂\s*)?Generated Deliverables/i)
    ) {
      return false;
    }
    return true;
  });

  return filteredLines.join('\n').trim();
}

