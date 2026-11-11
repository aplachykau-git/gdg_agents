export const DEFAULT_APPS = [
  { name: 'root_agent', root_agent_name: 'Main' },
  { name: 'receipt_scanner', root_agent_name: 'Receipt Scanner' },
  { name: 'video_editor', root_agent_name: 'Live Video Editor' },
  { name: 'linkedin_post_generator', root_agent_name: 'Social Planner' },
  { name: 'registration_manager', root_agent_name: 'Registrations Manager' },
  { name: 'event_planner', root_agent_name: 'Event Scheduler' },
  { name: 'agenda_generator', root_agent_name: 'Agenda Formatter' },
  { name: 'office_secretary', root_agent_name: 'Office Secretary' },
  { name: 'qr_code_generator', root_agent_name: 'QR Code Generator' }
];

export const DEFAULT_TEMPLATE_ID = '1nkT3N6ovmmBJYDK9S9oRRaOZ6sCQkAwve58y7sS2eOw';

export const DEFAULT_TEMPLATE_URL = `https://docs.google.com/document/d/${DEFAULT_TEMPLATE_ID}/edit`;

export const DEFAULT_CONFIG = {
  communityName: 'GDG Krakow',
  googleDriveFolderId: '',
  googleDocsTemplateId: '',
  serviceAccountEmail: (import.meta.env || {}).VITE_STUDIO_SA_EMAIL || 'community-studio-runtime@gdg-agents-6b59a.iam.gserviceaccount.com',
  // Video Editor rendering toggles
  render4k: true,
  renderGif: true,
  generateAvatar: true,
  enableVideoGeneration: true,
  videoEngine: 'omni',
  videoTemplate: 'build_with_ai',
  // Event & social posts (Settings -> Event). Sent to every agent as event_* session state.
  eventName: '',
  eventDate: '',
  eventWebsite: 'https://devfestkrakow.pl/',
  eventRegistrationUrl: '',
  eventVenue: '',
  eventHighlights: '',
  eventHashtags: '',
  // Settings -> Social networks: profile links; `post` = plan countdown posts there.
  socialProfiles: [
    { network: 'linkedin', url: '', post: true },
    { network: 'instagram', url: '', post: true }
  ],
  countdownPlan: ''
};

// Default countdown sequence; keep in sync with DEFAULT_SEQUENCE in
// agents/linkedin_post_generator/countdown.py (tests/test_countdown_planner.py checks it).
export const DEFAULT_COUNTDOWN_PLAN = [
  '30: Save the date',
  '21: Why attend',
  '14: Hands-on workshops',
  '12: Agenda is live',
  '10: Community spaces',
  '7: One week to go',
  '5: Mentoring and careers',
  '3: Venue and getting there',
  '2: Thank you, partners',
  '1: See you tomorrow',
  '0: It is today'
].join('\n');

// Keep in sync with NETWORKS in agents/common/event_profile.py. `plannable` networks get
// countdown posts; the others are profile links only.
export const SOCIAL_NETWORKS = [
  { id: 'linkedin', name: 'LinkedIn', plannable: true, domains: ['linkedin.com'], placeholder: 'https://www.linkedin.com/company/your-community/' },
  { id: 'instagram', name: 'Instagram', plannable: true, domains: ['instagram.com'], placeholder: 'https://www.instagram.com/your_handle/' },
  { id: 'facebook', name: 'Facebook', plannable: true, domains: ['facebook.com', 'fb.com'], placeholder: 'https://www.facebook.com/your-page' },
  { id: 'x', name: 'X', plannable: true, domains: ['x.com', 'twitter.com'], placeholder: 'https://x.com/your_handle' },
  { id: 'threads', name: 'Threads', plannable: true, domains: ['threads.net', 'threads.com'], placeholder: 'https://www.threads.net/@your_handle' },
  { id: 'bluesky', name: 'Bluesky', plannable: true, domains: ['bsky.app'], placeholder: 'https://bsky.app/profile/you.bsky.social' },
  { id: 'mastodon', name: 'Mastodon', plannable: true, domains: [], placeholder: 'https://mastodon.social/@your_handle' },
  { id: 'youtube', name: 'YouTube', plannable: false, domains: ['youtube.com', 'youtu.be'], placeholder: 'https://www.youtube.com/@YourChannel' },
  { id: 'tiktok', name: 'TikTok', plannable: false, domains: ['tiktok.com'], placeholder: 'https://www.tiktok.com/@your_handle' },
  { id: 'discord', name: 'Discord', plannable: false, domains: ['discord.gg', 'discord.com'], placeholder: 'https://discord.gg/invite-code' },
  { id: 'telegram', name: 'Telegram', plannable: false, domains: ['t.me', 'telegram.me'], placeholder: 'https://t.me/your_channel' },
  { id: 'gdg', name: 'GDG community page', plannable: false, domains: ['gdg.community.dev'], placeholder: 'https://gdg.community.dev/gdg-your-city/' }
];

export function socialNetwork(id) {
  return SOCIAL_NETWORKS.find((n) => n.id === id) || { id, name: id, plannable: false, domains: [], placeholder: 'https://' };
}

/** Warning text when a profile link points to another site than its network, else ''. */
export function profileUrlWarning(network, url) {
  const value = (url || '').trim();
  if (!value) return '';
  let host = '';
  try {
    host = new URL(/^https?:\/\//i.test(value) ? value : `https://${value}`).hostname.toLowerCase().replace(/^www\./, '');
  } catch {
    return 'This does not look like a link.';
  }
  const { domains, name } = socialNetwork(network);
  if (!domains.length || domains.some((d) => host === d || host.endsWith(`.${d}`))) return '';
  return `This link goes to ${host}, not ${name}.`;
}

/** Profiles from settings; configs saved before profiles existed are migrated from socialChannels. */
export function socialProfilesOf(cfg = {}) {
  if (Array.isArray(cfg.socialProfiles)) return cfg.socialProfiles;
  if (Array.isArray(cfg.socialChannels) && cfg.socialChannels.length) {
    return cfg.socialChannels.map((network) => ({ network, url: '', post: true }));
  }
  return DEFAULT_CONFIG.socialProfiles;
}

export const VIDEO_TEMPLATES = [
  {
    id: 'build_with_ai',
    name: 'Build With AI',
    description: 'Classic Google AI community speaker intro layout'
  },
  {
    id: 'devfest',
    name: 'DevFest',
    description: 'DevFest conference dynamic speaker showcase'
  }
];

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
    name: 'Social Planner',
    tag: 'Social Media & Posts',
    accent: 'var(--agent-linkedin)',
    bg: 'var(--bg-linkedin)',
    icon: 'share',
    summary: 'Writes LinkedIn and Instagram posts for the community. Plans a dated countdown to the event (which teaser goes to LinkedIn, which to Instagram, and why), drafts speaker spotlight announcements and recap options with hashtags.',
    whatItDoes: 'Drafts ready-to-publish countdown posts, LinkedIn announcements, Instagram captions and post-event recaps, and exports the plan as CSV for Google Sheets.',
    whenToUse: [
      'Planning the "N days to go" countdown posts for LinkedIn and Instagram.',
      'Announcing a new speaker, presentation topic, and key learning points.',
      'Publishing last-chance registration reminders before seats run out.',
      'Sharing 3 variations of post-event summaries (short highlights, technical recap, community conversational).'
    ],
    starterPrompts: [
      'Plan the countdown posts for LinkedIn and Instagram until the event',
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
  },
  {
    id: 'qr_code_generator',
    name: 'QR Code Generator',
    tag: 'Links & Print',
    accent: 'var(--agent-qr)',
    bg: 'var(--bg-qr)',
    icon: 'qr',
    summary: 'Turns any link into a good-looking rounded QR code. Every code comes as one flat vector SVG (one path, scales for print, banners and slides) and a 1024px PNG, with optional brand colours, coloured corner eyes and a transparent background.',
    whatItDoes: 'Creates rounded QR codes for links as a flat SVG and a PNG, ready to download.',
    whenToUse: [
      'Putting the registration or feedback link on slides, posters and roll-ups.',
      'Sharing the Wi-Fi page, slides or a survey link at the venue.',
      'Branded codes in Google colours or with a transparent background for designs.'
    ],
    starterPrompts: [
      'Make a QR code for https://gdg.community.dev/gdg-krakow/',
      'Blue QR code with red corner eyes for https://example.com/register',
      'QR with a transparent background for our poster: https://example.com/feedback'
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
      if (!Array.isArray(parsed.socialProfiles) && Array.isArray(parsed.socialChannels)) {
        parsed.socialProfiles = socialProfilesOf(parsed);
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

/** Settings -> Event as session state keys read by agents/common/event_profile.py. */
export function eventStatePayload(cfg = {}) {
  const profiles = socialProfilesOf(cfg)
    .filter((p) => p && SOCIAL_NETWORKS.some((n) => n.id === p.network))
    .map((p) => ({ network: p.network, url: (p.url || '').trim(), post: Boolean(p.post) && socialNetwork(p.network).plannable }));
  const channels = profiles.filter((p) => p.post).map((p) => p.network);
  return {
    event_name: cfg.eventName || '',
    event_date: cfg.eventDate || '',
    event_website: cfg.eventWebsite || DEFAULT_CONFIG.eventWebsite,
    event_registration_url: cfg.eventRegistrationUrl || '',
    event_venue: cfg.eventVenue || '',
    event_highlights: cfg.eventHighlights || '',
    event_hashtags: cfg.eventHashtags || '',
    social_profiles: profiles,
    social_channels: channels,
    countdown_plan: cfg.countdownPlan || DEFAULT_COUNTDOWN_PLAN,
  };
}

// --------------------------------------------------------------------------- event profile
// Event details and social profiles are set in the chat (the Social Planner's event card), not
// in Settings. They are stored with the studio config so every new session sends them.

/** Event profile payload (agents/common/event_profile_tools.py profile_dict) -> config keys. */
export function profileToConfig(profile = {}) {
  return {
    eventName: profile.name || '',
    eventDate: profile.date || '',
    eventWebsite: profile.website || DEFAULT_CONFIG.eventWebsite,
    eventRegistrationUrl: profile.registration_url || '',
    eventVenue: profile.venue || '',
    eventHighlights: profile.highlights || '',
    eventHashtags: (profile.hashtags || []).join(' '),
    socialProfiles: Array.isArray(profile.social_profiles) ? profile.social_profiles : DEFAULT_CONFIG.socialProfiles,
    countdownPlan: profile.countdown && profile.countdown !== DEFAULT_COUNTDOWN_PLAN ? profile.countdown : '',
  };
}

/** Config keys -> the profile shape the event card edits. */
export function configToProfile(cfg = {}) {
  const state = eventStatePayload(cfg);
  return {
    name: state.event_name,
    date: state.event_date,
    website: state.event_website,
    registration_url: state.event_registration_url,
    venue: state.event_venue,
    highlights: state.event_highlights,
    hashtags: (state.event_hashtags || '').split(/[\s,;]+/).filter(Boolean),
    social_profiles: state.social_profiles,
    countdown: cfg.countdownPlan || '',
  };
}

export const STUDIO_CONFIG_PATCH_EVENT = 'studio-config-patch';

/** Ask App.svelte to merge `patch` into the studio config (and localStorage). */
export function patchStudioConfig(patch) {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent(STUDIO_CONFIG_PATCH_EVENT, { detail: patch }));
}
