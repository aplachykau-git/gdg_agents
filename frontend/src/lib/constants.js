import { marked } from 'marked';

export const DEFAULT_APPS = [
  { name: 'root_agent', root_agent_name: 'Root Orchestrator' },
  { name: 'receipt_scanner', root_agent_name: 'Receipt Scanner' },
  { name: 'video_editor', root_agent_name: 'Live Video Editor' },
  { name: 'linkedin_post_generator', root_agent_name: 'LinkedIn Planner' },
  { name: 'registration_manager', root_agent_name: 'Registrations Manager' },
  { name: 'event_planner', root_agent_name: 'Event Scheduler' },
  { name: 'agenda_generator', root_agent_name: 'Agenda Formatter' },
  { name: 'office_secretary', root_agent_name: 'Office Secretary' }
];

export const MAX_INPUT_TOKENS = 8192;

export function cleanAuthorName(author) {
  if (!author) return '';
  return author.replace(/^Active Context:\s*/i, '').trim();
}

export function getAgentTheme(author) {
  if (!author) return { color: 'var(--primary-accent)', bg: 'rgba(138, 180, 248, 0.1)', label: 'Agent' };
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

export const STATUS_TICKERS = {
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

export function getFriendlyToolCall(name, args) {
  const mappings = {
    transfer_to_video_editor: () => "🔄 Delegating task to Live Video Editor (A2A)...",
    transfer_to_receipt_scanner: () => "🔄 Delegating task to Receipt Scanner (A2A)...",
    transfer_to_linkedin_post_generator: () => "🔄 Delegating task to LinkedIn Planner...",
    transfer_to_event_planner: () => "🔄 Delegating task to Event Scheduler...",
    transfer_to_registration_manager: () => "🔄 Delegating task to Registrations Manager...",
    transfer_to_agenda_generator: () => "🔄 Delegating task to Agenda Formatter...",
    transfer_to_office_secretary: () => "🔄 Delegating task to Office Secretary...",

    verify_portrait_photo: () => "🔍 Running facial detection on portrait photo...",
    stage_uploaded_media: () => "📦 Staging uploaded media to workspace assets...",
    animate_photo: () => "🎬 Outpainting to 9:16 & generating Veo video intro...",
    update_composer: (a) => `🎨 Updating HTML5 composition layout for "${a.name || 'speaker'}"...`,
    render_composer: () => "🚀 HyperFrames compiler rendering final video (MP4, GIF, 4K)...",
    validate_metadata: (a) => `📐 Validating text character limits for "${a.name || 'speaker'}"...`,

    get_usd_pln_rate: () => "💱 Fetching live Pekao Bank & NBP exchange rates (USD/PLN)...",
    read_receipt_file: () => "🧾 Analyzing receipt image via Gemini 2.5 Pro Vision OCR...",
    export_summary_to_google_doc: () => "📄 Exporting approved expense report to Google Docs...",
    scan_receipt_with_vision: () => "🧾 Extracting items and taxes via Vision OCR...",
    convert_currency: () => "💱 Converting currencies to PLN using exchange rates...",
    export_to_google_docs: () => "📄 Exporting expense report to Google Docs template...",

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
  const mappings = {
    transfer_to_video_editor: () => "Workflow handed off to Live Video Editor (A2A).",
    transfer_to_receipt_scanner: () => "Workflow handed off to Receipt Scanner (A2A).",
    transfer_to_linkedin_post_generator: () => "Workflow handed off to LinkedIn Planner.",
    transfer_to_event_planner: () => "Workflow handed off to Event Scheduler.",
    transfer_to_registration_manager: () => "Workflow handed off to Registrations Manager.",
    transfer_to_agenda_generator: () => "Workflow handed off to Agenda Formatter.",
    transfer_to_office_secretary: () => "Workflow handed off to Office Secretary.",

    verify_portrait_photo: () => "Face detected and verified.",
    stage_uploaded_media: () => "Photo saved to assets.",
    animate_photo: () => "Veo animation generated.",
    update_composer: () => "Layout configuration updated.",
    render_composer: (r) => r?.render_urls?.mp4 ? `Video rendered: ${r.render_urls.mp4}` : "Video rendered successfully.",
    validate_metadata: () => "Metadata character limits validated.",

    get_usd_pln_rate: (r) => r?.rate ? `Rate fetched: 1 USD = ${r.rate} PLN` : "Exchange rate fetched.",
    read_receipt_file: () => "Receipt OCR extracted.",
    export_summary_to_google_doc: (r) => r?.document_url ? `Expense doc ready: ${r.document_url}` : "Document exported.",
    scan_receipt_with_vision: () => "Receipt parsed.",
    convert_currency: () => "Currency converted.",
    export_to_google_docs: () => "Document exported to Google Docs.",

    filter_and_clean_registrations: () => "Registration roster cleaned.",
    find_optimal_meetup_date: () => "Meetup dates evaluated.",
    generate_agenda: () => "Agenda timeline created.",
    generate_office_email: () => "Email template generated."
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
  if (!event.content || !event.content.parts) return true;
  return false;
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
