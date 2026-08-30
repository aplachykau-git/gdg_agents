import { marked } from 'marked';

const ALLOWED_LINK_PROTOCOLS = new Set(['http:', 'https:']);

function escapeHtml(value) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function safeLinkUrl(value) {
  try {
    const url = new URL(value);
    return ALLOWED_LINK_PROTOCOLS.has(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

const markdownRenderer = {
  link({ href, title, tokens }) {
    const label = this.parser.parseInline(tokens);
    const safeUrl = safeLinkUrl(href);
    if (!safeUrl) return label;
    const titleAttribute = title ? ` title="${escapeHtml(title)}"` : '';
    return `<a href="${escapeHtml(safeUrl)}"${titleAttribute} target="_blank" rel="noopener noreferrer">${label}</a>`;
  }
};

marked.use({ renderer: markdownRenderer });

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

export const DEFAULT_TEMPLATE_ID = '1nkT3N6ovmmBJYDK9S9oRRaOZ6sCQkAwve58y7sS2eOw';
export const DEFAULT_TEMPLATE_URL = `https://docs.google.com/document/d/${DEFAULT_TEMPLATE_ID}/edit`;

export const DEFAULT_CONFIG = {
  communityName: 'GDG Krakow',
  googleDriveFolderId: '',
  googleDocsTemplateId: '',
  serviceAccountEmail: import.meta.env.VITE_STUDIO_SA_EMAIL || 'community-studio-runtime@gdg-agents-6b59a.iam.gserviceaccount.com',
  // Video Editor rendering toggles
  render4k: true,
  renderGif: true,
  generateAvatar: true,
  enableVideoGeneration: true,
  videoEngine: 'omni'
};

export const AGENT_CAPABILITIES_CATALOG = [
  {
    id: 'root_agent',
    name: 'Main',
    tag: 'Primary Coordinator',
    accent: 'var(--agent-root)',
    bg: 'var(--bg-root)',
    icon: 'layers',
    summary: 'Your primary AI assistant for community management. Understands plain-language requests, answers general questions, and coordinates specialized agents to handle multi-step tasks across finances, media, marketing, and event planning.',
    whatItDoes: 'Directs your requests to the right specialist agent, merges multi-step outputs, and assists with all general community organization tasks.',
    whenToUse: [
      'When you have a multi-step request (e.g. process receipts AND draft an announcement).',
      'When you are unsure which specialized agent is best suited for your task.',
      'For general questions about event planning, GDG guidelines, or community logistics.'
    ],
    starterPrompts: [
      'Here is a receipt from yesterday\'s meetup dinner — calculate expenses and prepare a report for reimbursement',
      'Help me organize our next AI meetup: find a conflict-free date in November and format an agenda starting at 17:30',
      'Create a 9:16 speaker intro video for Anna Kowalska and draft a LinkedIn announcement with registration link'
    ]
  },
  {
    id: 'receipt_scanner',
    name: 'Receipt Scanner',
    tag: 'Expenses & Finance',
    accent: 'var(--agent-receipt)',
    bg: 'var(--bg-receipt)',
    icon: 'receipt',
    summary: 'Automates expense reimbursements and financial tracking. Reads attached receipts or invoices, calculates currency conversions to PLN using live official bank rates, and creates ready-to-share Google Docs expense reports in your Google Drive.',
    whatItDoes: 'Extracts line items, dates, and amounts from receipt photos/PDFs, converts USD/EUR to PLN with live rates, and generates Google Docs reports.',
    whenToUse: [
      'Processing receipts for pizza, catering, equipment, venue rental, or travel expenses.',
      'Checking current official USD/PLN and EUR/PLN exchange rates from the National Bank of Poland.',
      'Compiling formatted expense summaries for sponsors, community leads, or accounting.'
    ],
    starterPrompts: [
      'I attached a photo of our catering invoice ($145.50). Extract line items, convert to PLN with today\'s bank rate, and create a Google Doc report',
      'What is today\'s official NBP banking exchange rate for USD/PLN and EUR/PLN?',
      'Scan this receipt for event badges (350 PLN) and export an expense report to our Google Drive folder'
    ]
  },
  {
    id: 'video_editor',
    name: 'Live Video Editor',
    tag: 'Speaker Video & Cards',
    accent: 'var(--agent-video)',
    bg: 'var(--bg-video)',
    icon: 'video',
    summary: 'Generates branded video intros and presentation cards from speaker photos. Automatically centers portraits, expands them to a 9:16 vertical video with dynamic AI animated backgrounds, and renders 1080p MP4 videos, animated GIFs, and high-res posters.',
    whatItDoes: 'Transforms portrait photos into vertical 9:16 video cards and posters with speaker names, titles, and animated backgrounds.',
    whenToUse: [
      'Creating vertical video teasers for Instagram Reels, YouTube Shorts, or LinkedIn.',
      'Generating animated intro cards to display on stage screens before a speaker talk.',
      'Rendering high-resolution speaker announcement posters.'
    ],
    starterPrompts: [
      'Create a 9:16 vertical speaker intro video for attached photo: John Doe, Staff Engineer at Google, Talk: "Building AI Agents"',
      'Generate an animated speaker card with a dynamic neon tech background for Anna Kowalska, Lead Architect',
      'Render a 1080p MP4 video, animated GIF, and poster card for our keynote speaker'
    ]
  },
  {
    id: 'linkedin_post_generator',
    name: 'LinkedIn Planner',
    tag: 'Social Media & Posts',
    accent: 'var(--agent-linkedin)',
    bg: 'var(--bg-linkedin)',
    icon: 'share',
    summary: 'Writes high-impact LinkedIn posts for tech meetups. Crafts engaging speaker spotlight announcements with key talk takeaways, event invitations with registration links, and generates multiple recap post options with hashtags after the event.',
    whatItDoes: 'Drafts ready-to-publish LinkedIn announcements, registration reminders, and post-event recaps with tailored hashtags.',
    whenToUse: [
      'Announcing a new speaker, presentation topic, and key learning points.',
      'Publishing last-chance registration reminders before seats run out.',
      'Sharing 3 variations of post-event summaries (short highlights, technical recap, community conversational).'
    ],
    starterPrompts: [
      'Draft an exciting speaker announcement for Alex River on "Agentic Workflows" with registration link https://gdg.community.dev/events/...',
      'Generate 3 different recap post options with hashtags for our Cloud & AI meetup that finished yesterday with 65 attendees',
      'Write a last-chance registration reminder post: only 15 seats left for this Thursday\'s meetup at Google Krakow'
    ]
  },
  {
    id: 'registration_manager',
    name: 'Registrations Manager',
    tag: 'Attendee Rosters',
    accent: 'var(--agent-registration)',
    bg: 'var(--bg-registration)',
    icon: 'users',
    summary: 'Cleans and organizes attendee registration lists from Meetup, Luma, Google Forms, or CSV/text files. Removes test registrations and duplicate names, partitions attendees by venue capacity into Confirmed and Waitlist groups, and generates clean DOCX check-in sheets.',
    whatItDoes: 'Cleans dirty attendee lists, removes duplicates, splits guests by venue capacity, and exports printable Word check-in rosters.',
    whenToUse: [
      'Sanitizing registration CSV files or copied text before an event.',
      'Splitting attendees when registrations exceed room capacity (e.g. venue limit 50).',
      'Creating an alphabetized printable check-in roster for reception volunteers.'
    ],
    starterPrompts: [
      'Here is our attendee CSV export. Venue capacity is 50 people. Clean duplicate names, remove test entries, and export confirmed/waitlist lists to DOCX',
      'Check this pasted list of registrations, remove duplicate names, and sort everyone alphabetically by last name',
      'Split our attendee list into 60 confirmed attendees and a waitlist, making sure organizers are protected in the confirmed list'
    ]
  },
  {
    id: 'event_planner',
    name: 'Event Scheduler',
    tag: 'Dates & Holidays',
    accent: 'var(--agent-planner)',
    bg: 'var(--bg-planner)',
    icon: 'calendar',
    summary: 'Finds conflict-free dates for community meetups and workshops. Checks Polish statutory public holidays, church holidays, long weekend bridge days (długie weekendy), and local Krakow tech calendars to recommend the best mid-week dates for high attendance.',
    whatItDoes: 'Analyzes dates against Polish holidays, long weekends, and local tech events to recommend optimal days (Tue–Thu).',
    whenToUse: [
      'Picking the best date for next month\'s meetup to maximize attendance.',
      'Checking if a specific date clashes with public holidays or competing IT conferences in Krakow.',
      'Finding long weekend dates to avoid low-turnout days.'
    ],
    starterPrompts: [
      'Find the best date for our next GDG meetup in November: recommend a Tuesday or Thursday without holiday conflicts or long weekends',
      'Check if November 14 is a good date for a meetup in Krakow: are there any holiday collisions or competing tech events?',
      'List all Polish public holidays and long weekends for next quarter so we can plan our event calendar'
    ]
  },
  {
    id: 'agenda_generator',
    name: 'Agenda Formatter',
    tag: 'Event Agendas',
    accent: 'var(--agent-agenda)',
    bg: 'var(--bg-agenda)',
    icon: 'clock',
    summary: 'Calculates minute-level event timelines for tech meetups and workshops. You provide the start time (e.g. 17:30) and list of talks — the agent calculates exact timestamps, allocates time for welcome remarks, speaker sessions, Q&A, and pizza networking breaks.',
    whatItDoes: 'Calculates exact start and end times for all agenda items, talks, Q&A sessions, and networking breaks.',
    whenToUse: [
      'Creating a clear, professional schedule for event landing pages and slides.',
      'Planning talk durations, Q&A time, and networking breaks so the event finishes on time.',
      'Reformatting an agenda when talk lengths or speaker counts change.'
    ],
    starterPrompts: [
      'Format an event agenda starting at 17:30 with welcome (10m), 2 talks (30m each with 10m Q&A), a 20m pizza break, and networking until 20:30',
      'Create a 3-hour workshop schedule starting at 18:00 with 3 hands-on modules and a 15-minute coffee pause',
      'Format a Lightning Talks schedule starting at 18:30 with five 10-minute slots and closing remarks'
    ]
  },
  {
    id: 'office_secretary',
    name: 'Office Secretary',
    tag: 'Access & Logistics',
    accent: 'var(--agent-office)',
    bg: 'var(--bg-office)',
    icon: 'mail',
    summary: 'Drafts formal, polite administrative emails for venue access and room reservations. Prepares building security visitor key requests and Event Hub reservation drafts, with one-click buttons to open pre-filled emails directly in Gmail or your default email client.',
    whatItDoes: 'Writes visitor security key access requests and room booking emails with 1-click launch in Gmail and mailto.',
    whenToUse: [
      'Requesting visitor keys and access badges from building security for upcoming events.',
      'Booking the Event Hub or meeting rooms with date, time, and attendee count details.',
      'Notifying building reception about external guest speakers arriving.'
    ],
    starterPrompts: [
      'Draft a visitor keys access request email to building security for next Tuesday\'s meetup from 17:30 to 21:00 for 50 attendees',
      'Prepare an Event Hub room reservation email to facility management for October 24 (17:00 - 21:30)',
      'Draft a security access notification for 2 external guest speakers arriving at 17:00 this Thursday'
    ]
  }
];

export function extractDriveFolderId(input) {
  if (!input || typeof input !== 'string') return '';
  const trimmed = input.trim();
  if (!trimmed) return '';

  // Extract from /folders/<id>
  const folderMatch = trimmed.match(/\/folders\/([a-zA-Z0-9_-]+)/);
  if (folderMatch) return folderMatch[1];

  // Extract from ?id=<id> or &id=<id>
  const idParamMatch = trimmed.match(/[?&]id=([a-zA-Z0-9_-]+)/);
  if (idParamMatch) return idParamMatch[1];

  return trimmed;
}

export function validateDriveFolderInput(input) {
  if (!input || typeof input !== 'string') return { valid: true, folderId: '', error: '' };
  const trimmed = input.trim();
  if (!trimmed) return { valid: true, folderId: '', error: '' };

  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
    if (!trimmed.includes('drive.google.com') && !trimmed.includes('docs.google.com')) {
      return { valid: false, folderId: '', error: 'Only Google Drive links (drive.google.com) or folder IDs are supported.' };
    }
    const extracted = extractDriveFolderId(trimmed);
    if (!extracted || extracted === trimmed || !/^[a-zA-Z0-9_-]{10,80}$/.test(extracted)) {
      return { valid: false, folderId: '', error: 'Could not find a valid Google Drive folder ID in the URL.' };
    }
    return { valid: true, folderId: extracted, error: '' };
  }

  // Raw ID check
  if (!/^[a-zA-Z0-9_-]{10,80}$/.test(trimmed)) {
    return { valid: false, folderId: '', error: 'Invalid Google Drive folder ID format.' };
  }

  return { valid: true, folderId: trimmed, error: '' };
}

export function extractGoogleDocId(input) {
  if (!input || typeof input !== 'string') return '';
  const trimmed = input.trim();
  if (!trimmed) return '';

  // Extract from /document/d/<id>
  const docMatch = trimmed.match(/\/document\/d\/([a-zA-Z0-9_-]+)/);
  if (docMatch) return docMatch[1];

  // Extract from ?id=<id> or &id=<id>
  const idParamMatch = trimmed.match(/[?&]id=([a-zA-Z0-9_-]+)/);
  if (idParamMatch) return idParamMatch[1];

  return trimmed;
}

export function validateGoogleDocTemplateInput(input) {
  if (!input || typeof input !== 'string') return { valid: true, docId: '', error: '' };
  const trimmed = input.trim();
  if (!trimmed) return { valid: true, docId: '', error: '' };

  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
    if (!trimmed.includes('docs.google.com')) {
      return { valid: false, docId: '', error: 'Only Google Docs links (docs.google.com/document/d/...) or Doc IDs are supported.' };
    }
    const extracted = extractGoogleDocId(trimmed);
    if (!extracted || extracted === trimmed || !/^[a-zA-Z0-9_-]{10,80}$/.test(extracted)) {
      return { valid: false, docId: '', error: 'Could not find a valid Google Doc ID in the URL.' };
    }
    return { valid: true, docId: extracted, error: '' };
  }

  // Raw ID check
  if (!/^[a-zA-Z0-9_-]{10,80}$/.test(trimmed)) {
    return { valid: false, docId: '', error: 'Invalid Google Doc ID format.' };
  }

  return { valid: true, docId: trimmed, error: '' };
}

export function getAppConfig() {
  if (typeof window === 'undefined') return DEFAULT_CONFIG;
  try {
    const saved = localStorage.getItem('community_studio_config') || localStorage.getItem('gdg_studio_config');
    if (saved) {
      const parsed = JSON.parse(saved);
      if (!parsed.serviceAccountEmail || parsed.serviceAccountEmail.includes('receipt-docs-bot')) {
        parsed.serviceAccountEmail = DEFAULT_CONFIG.serviceAccountEmail;
      }
      return { ...DEFAULT_CONFIG, ...parsed };
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

  const urlRegex = /((?:https?|file):\/\/[^\s\)\"\'<>]+?\.(?:mp4|webm|mov|gif|png|jpg|jpeg|webp)(?:\?[^\s\)\"\'<>]*)?|(?:\/(?:renders|results)\/[^\s\)\"\'<>]+?\.(?:mp4|webm|mov|gif|png|jpg|jpeg|webp)))/gi;
  const matches = [...text.matchAll(urlRegex)].map(m => m[1]);

  if (!matches || matches.length === 0) return null;

  const mapToPlayableUrl = (rawUrl) => {
    if (!rawUrl) return '';
    if (rawUrl.startsWith('file://')) {
      const filename = rawUrl.split('/').pop()?.split('?')[0];
      return filename ? `/renders/${filename}` : rawUrl;
    }
    return rawUrl;
  };

  let rawVideoUrl = matches.find(u => u.toLowerCase().includes('.mp4') || u.toLowerCase().includes('.webm') || u.toLowerCase().includes('.mov'));
  let rawGifUrl = matches.find(u => u.toLowerCase().includes('.gif'));
  let rawPosterUrl = matches.find(u => u.toLowerCase().includes('_poster.') || u.toLowerCase().includes('poster') || (u.toLowerCase().includes('.png') && !u.toLowerCase().includes('_avatar')));
  let rawAvatarUrl = matches.find(u => u.toLowerCase().includes('_avatar.') || u.toLowerCase().includes('avatar'));

  if (!rawPosterUrl) {
    rawPosterUrl = matches.find(u => u !== rawVideoUrl && u !== rawGifUrl && u !== rawAvatarUrl);
  }

  if (!rawVideoUrl && !rawGifUrl && !rawPosterUrl) return null;

  const nameMatch = text.match(/\*\*Speaker Name:\*\*\s*([^\n]+)/i) || text.match(/name:\s*"?([^"\n]+)"?/i) || text.match(/speaker:\s*"?([^"\n]+)"?/i);
  const titleMatch = text.match(/\*\*Talk Title:\*\*\s*([^\n]+)/i) || text.match(/title:\s*"?([^"\n]+)"?/i) || text.match(/talk:\s*"?([^"\n]+)"?/i);
  const positionCompanyMatch = text.match(/\*\*Position & Company:\*\*\s*([^\n]+)/i) || text.match(/position_company:\s*"?([^"\n]+)"?/i);

  return {
    videoUrl: mapToPlayableUrl(rawVideoUrl),
    rawVideoUrl,
    gifUrl: mapToPlayableUrl(rawGifUrl),
    rawGifUrl,
    posterUrl: mapToPlayableUrl(rawPosterUrl),
    rawPosterUrl,
    avatarUrl: mapToPlayableUrl(rawAvatarUrl),
    allUrls: matches,
    speakerName: nameMatch ? nameMatch[1].replace(/[`*]/g, '').trim() : '',
    talkTitle: titleMatch ? titleMatch[1].replace(/[`*]/g, '').trim() : '',
    positionCompany: positionCompanyMatch ? positionCompanyMatch[1].replace(/[`*]/g, '').trim() : ''
  };
}

export async function downloadDirectFile(url, suggestedFilename) {
  if (!url) return;
  const filename = suggestedFilename || url.split('/').pop()?.split('?')[0] || 'media_asset';
  if (url.startsWith('file://')) {
    window.location.assign(url);
    return;
  }

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
      trimmed.match(/^[-*•]\s*(?:🎥|🖼️|📸|👤)?.*(?:(?:https?|file):\/\/[^\s\)]+?\.(?:mp4|gif|png|jpg|jpeg|webp)|\[(?:Download|View)[^\]]*\])/i) ||
      trimmed.match(/^\[(?:Download|View)[^\]]*\]\((?:https?|file):\/\/[^\s\)]+\)/i) ||
      trimmed.match(/^(?:https?|file):\/\/[^\s\)]+?\.(?:mp4|gif|png|jpg|jpeg|webp)$/i)
    ) {
      return false;
    }
    return true;
  });

  return filteredLines.join('\n').trim();
}

export function extractDocumentAssets(text) {
  if (!text) return null;

  // Regex to match Google Docs URLs
  const gdocRegex = /https?:\/\/docs\.google\.com\/document\/d\/[a-zA-Z0-9_-]+[^\s\)\"\'<>]*/gi;
  const gdocMatches = text.match(gdocRegex) || [];

  if (gdocMatches.length > 0) {
    const gdocUrl = gdocMatches[0].replace(/[\)\]\.\,]+$/, '');
    const titleMatch = text.match(/(?:Expense Reimbursement Report|Expense Report|Reimbursement Report|Expense_report_[^\s\n\)\"\'<>]+|Report)[\s\:\*\#\-]*([^\n]+)?/i);
    const docTitle = titleMatch ? titleMatch[0].replace(/[`*#\[\]\(\)]/g, '').trim() : 'Expense Reimbursement Report';

    return {
      primaryUrl: gdocUrl,
      gdocUrl: gdocUrl,
      isGoogleDoc: true,
      filename: docTitle,
      fileType: 'Google Docs',
      typeLabel: 'Google Docs Expense Report',
      title: docTitle,
      allUrls: [gdocUrl]
    };
  }

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
  let typeLabel = 'Word & Google Docs Compatible';
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
      // Markdown links with documents or Google Docs
      trimmed.match(/^[-*•]?\s*(?:📄|📑|📊|💾|📁|📥)?\s*.*(?:\/results\/|https?:\/\/|file:\/\/)[^\s\)]+?\.(?:docx|xlsx|csv|pdf)/i) ||
      trimmed.match(/^[-*•]?\s*(?:📄|📑|📊|💾|📁|📥)?\s*.*https?:\/\/docs\.google\.com\/document\/d\/[^\s\)]+/i) ||
      trimmed.match(/^\[(?:Download|View|Expense|Successfully|Open|Скачать|Открыть)[^\]]*\]\([^\)]+\)/i) ||
      trimmed.match(/^(?:https?:\/\/|\/results\/|file:\/\/)[^\s\)]+?\.(?:docx|xlsx|csv|pdf)$/i) ||
      trimmed.match(/^https?:\/\/docs\.google\.com\/document\/d\/[^\s]+$/i) ||
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

/**
 * Parses and extracts recommended meetup dates and calendar event payloads
 * from Event Planner / Scheduler responses for interactive A2UI rendering.
 */
export function extractEventDates(text, author) {
  if (!text) return null;
  const clean = cleanAuthorName(author).toLowerCase();

  const isEventPlanner =
    clean.includes('event_planner') ||
    clean.includes('planner') ||
    clean.includes('scheduler') ||
    clean.includes('root') ||
    clean.includes('main');

  const hasDateIndicator =
    /(?:Recommended Date|Optimal Date|Proposed Date|Selected Date|Alternative Date|Option \d+:\s*(?:Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|\w+,\s*\w+\s*\d+)|Primary Recommendation)/i.test(text) ||
    /(?:Thursday|Tuesday|Wednesday),\s*(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?,\s*202\d/i.test(text) ||
    /\b202\d-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])\b/.test(text);

  if (!isEventPlanner || !hasDateIndicator) return null;

  // Month names mapping
  const monthMap = {
    january: 0, feb: 1, february: 1, mar: 2, march: 2, apr: 3, april: 3,
    may: 4, jun: 5, june: 5, jul: 6, july: 6, aug: 7, august: 7,
    sep: 8, sept: 8, september: 8, oct: 9, october: 9, nov: 10, november: 10,
    dec: 11, december: 11
  };

  // Find all date matches
  const dateRegex = /(?:(\w+day),?\s+)?(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(202\d)/gi;
  const foundDates = [];
  let match;

  while ((match = dateRegex.exec(text)) !== null) {
    const rawWeekday = match[1] || '';
    const monthName = match[2];
    const day = parseInt(match[3], 10);
    const year = parseInt(match[4], 10);
    const monthIdx = monthMap[monthName.toLowerCase()];

    if (monthIdx !== undefined && day >= 1 && day <= 31) {
      const dObj = new Date(year, monthIdx, day, 18, 0, 0);
      const weekday = rawWeekday || dObj.toLocaleDateString('en-US', { weekday: 'long' });
      const isoDate = `${year}-${String(monthIdx + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
      const fullDateStr = `${weekday}, ${monthName} ${day}, ${year}`;

      // Avoid duplicates
      if (!foundDates.some(fd => fd.isoDate === isoDate)) {
        foundDates.push({
          fullDateStr,
          isoDate,
          weekday,
          day,
          monthName,
          year,
          monthShort: monthName.slice(0, 3).toUpperCase(),
          dateObj: dObj
        });
      }
    }
  }

  if (foundDates.length === 0) return null;

  // Extract Event Title if mentioned in text
  let eventTitle = '';
  const titleMatch = text.match(/(?:for|organize|planning|meetup|event)\s+([A-Z0-9][A-Za-z0-9\s:\-_]{4,50}(?:Meetup|Night|Workshop|Conference|AI|GDG|Summit))/i);
  if (titleMatch) {
    eventTitle = titleMatch[1].trim();
  } else {
    const genericMatch = text.match(/(?:GDG\s+[A-Za-z0-9\s]+(?:Night|Meetup|AI|Summit|Day))/i);
    if (genericMatch) {
      eventTitle = genericMatch[0].trim();
    }
  }

  // Location: ONLY extract if explicitly mentioned in text (e.g. at/in Location), do NOT hardcode!
  let location = '';
  const locationMatch = text.match(/(?:at|venue|location)\s*:\s*([^\n,]+(?:Hub|Office|Hall|Room|ul\.|Street|Center)[^\n]*)/i);
  if (locationMatch) {
    location = locationMatch[1].trim();
  }

  const description = eventTitle
    ? `Community Technical Meetup: ${eventTitle}.`
    : 'Community Technical Meetup.';

  // Format dates with Google Calendar & ICS payloads
  const dates = foundDates.map((item, idx) => {
    // 18:00 to 21:30 local time
    const startStr = `${item.year}${String(item.dateObj.getMonth() + 1).padStart(2, '0')}${String(item.day).padStart(2, '0')}T180000`;
    const endStr = `${item.year}${String(item.dateObj.getMonth() + 1).padStart(2, '0')}${String(item.day).padStart(2, '0')}T213000`;

    const calTitle = eventTitle || 'Community AI Meetup';
    let gcalUrl = `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${encodeURIComponent(calTitle)}&dates=${startStr}/${endStr}&details=${encodeURIComponent(description)}&ctz=Europe/Warsaw`;
    if (location) {
      gcalUrl += `&location=${encodeURIComponent(location)}`;
    }

    // Standard RFC 5545 iCalendar payload
    const icsLines = [
      'BEGIN:VCALENDAR',
      'VERSION:2.0',
      'PRODID:-//Community AI Studio//EN',
      'CALSCALE:GREGORIAN',
      'METHOD:PUBLISH',
      'BEGIN:VEVENT',
      `UID:meetup-${item.isoDate}@gdg-agents.web.app`,
      `DTSTAMP:${item.year}0101T000000Z`,
      `DTSTART;TZID=Europe/Warsaw:${startStr}`,
      `DTEND;TZID=Europe/Warsaw:${endStr}`,
      `SUMMARY:${calTitle}`,
      `DESCRIPTION:${description.replace(/\n/g, '\\n')}`
    ];
    if (location) {
      icsLines.push(`LOCATION:${location}`);
    }
    icsLines.push('STATUS:CONFIRMED', 'END:VEVENT', 'END:VCALENDAR');

    const icsPayload = icsLines.join('\r\n');
    const icsDataUri = `data:text/calendar;charset=utf8,${encodeURIComponent(icsPayload)}`;

    return {
      ...item,
      isPrimary: idx === 0,
      label: idx === 0 ? 'Optimal Choice' : `Alternative Option ${idx + 1}`,
      timeRange: '18:00 – 21:30',
      gcalUrl,
      icsDataUri,
      icsFilename: `event_${item.isoDate}.ics`
    };
  });

  return {
    eventTitle,
    location,
    dates,
    primaryDate: dates[0],
    totalOptions: dates.length
  };
}
