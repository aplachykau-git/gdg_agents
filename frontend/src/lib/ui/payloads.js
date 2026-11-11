/**
 * Structured "ui" payloads produced by the backend (agents/common/ui_payloads.py).
 *
 * The backend attaches `{ type, ... }` either to a tool result (`function_response.response.ui`)
 * or to a final text event (`customMetadata.ui`). Components render from these payloads, so the
 * UI no longer depends on how the model happens to word its answer. The regex parsers in
 * ../legacy/textParsers.js are only used for old sessions recorded before this contract.
 */

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

function functionResponses(event) {
  return (event?.content?.parts || [])
    .map((part) => (part.function_response || part.functionResponse)?.response)
    .filter(Boolean);
}

/** All payloads of one event: the text payload first, then one per tool result (in call order). */
export function getEventUiPayloads(event) {
  const payloads = [];
  const meta = event?.customMetadata || event?.custom_metadata;
  if (meta?.ui?.type) payloads.push(meta.ui);
  for (const response of functionResponses(event)) {
    if (response?.ui?.type) payloads.push(response.ui);
  }
  return payloads;
}

export function getEventUiPayload(event) {
  return getEventUiPayloads(event)[0] || null;
}

function turnHasScenarios(event) {
  return functionResponses(event).some((response) => Array.isArray(response?.scenarios) && response.scenarios.length > 0);
}

/**
 * Map<eventIndex, payload> (first payload), Map<eventIndex, payload[]> (all payloads, e.g. a
 * receipt summary and its Google Doc returned by parallel tool calls in one event) plus the set
 * of event indices whose turn already has a structured payload (legacy text parsing is skipped
 * there, so the same deliverable is not rendered twice).
 */
export function computeUiCards(events) {
  const cards = new Map();
  const lists = new Map();
  const structuredTurnEvents = new Set();
  let turn = [];
  let turnPayloads = [];
  let turnHasVideoOutcome = false;

  const isChoice = (p) => p?.type === 'video_output_choice';
  const resolvesChoice = (p) => p?.type === 'media' || isChoice(p);

  const flushTurn = () => {
    const visibleEntries = [];
    for (const [idx, payloads] of turnPayloads) {
      const kept = turnHasVideoOutcome ? payloads.filter((p) => !isChoice(p)) : payloads;
      if (kept.length) visibleEntries.push([idx, kept]);
    }
    if (visibleEntries.length) {
      for (const [idx, kept] of visibleEntries) {
        cards.set(idx, kept[0]);
        lists.set(idx, kept);
      }
      turn.forEach((idx) => structuredTurnEvents.add(idx));
    }
    turn = [];
    turnPayloads = [];
    turnHasVideoOutcome = false;
  };

  let lastOutcomeIdx = -1;
  (events || []).forEach((event, idx) => {
    if (!event) return;
    if (event.author === 'user') {
      flushTurn();
      return;
    }
    turn.push(idx);
    const payloads = getEventUiPayloads(event);
    const hasScenarios = turnHasScenarios(event);
    if (hasScenarios || payloads.some((p) => p?.type === 'media')) {
      turnHasVideoOutcome = true;
      lastOutcomeIdx = idx;
    } else if (payloads.some(resolvesChoice)) {
      lastOutcomeIdx = idx;
    }
    if (payloads.length) {
      turnPayloads.push([idx, payloads]);
    }
  });
  flushTurn();

  if (lastOutcomeIdx >= 0) {
    for (const [idx, payloads] of lists.entries()) {
      if (idx >= lastOutcomeIdx) continue;
      if (!payloads.some(isChoice)) continue;
      const updated = payloads.map((p) => (isChoice(p) ? { ...p, resolved: true } : p));
      lists.set(idx, updated);
      cards.set(idx, updated[0]);
    }
  }
  return { cards, lists, structuredTurnEvents };
}

// --------------------------------------------------------------------------- adapters

export function playableUrl(rawUrl) {
  if (!rawUrl) return '';
  if (rawUrl.startsWith('file://')) {
    const filename = rawUrl.split('/').pop()?.split('?')[0];
    return filename ? `/renders/${filename}` : rawUrl;
  }
  return rawUrl;
}

export function toVideoOutputChoice(ui) {
  return {
    ...(ui || {}),
    avatarUrl: playableUrl(ui?.avatar_url),
  };
}

export function toMediaCard(ui) {
  const urls = ui.urls || {};
  return {
    videoUrl: playableUrl(urls.video),
    rawVideoUrl: urls.video || '',
    gifUrl: playableUrl(urls.gif),
    rawGifUrl: urls.gif || '',
    posterUrl: playableUrl(urls.poster),
    rawPosterUrl: urls.poster || '',
    avatarUrl: playableUrl(urls.avatar),
    allUrls: (ui.assets || []).map((a) => a.url).filter(Boolean),
    speakerName: ui.speaker?.name || '',
    talkTitle: ui.speaker?.talk_title || '',
    positionCompany: ui.speaker?.position_company || '',
    notice: ui.notice || '',
  };
}

export function toDocumentCard(ui) {
  const url = ui.url || '';
  const lower = url.toLowerCase();
  const isGoogleDoc = lower.includes('docs.google.com/document');
  const isRegistration = ui.kind === 'registration_roster';
  return {
    primaryUrl: url,
    gdocUrl: isGoogleDoc ? url : undefined,
    isGoogleDoc,
    docxUrl: lower.includes('.docx') ? url : undefined,
    xlsxUrl: lower.includes('.xlsx') ? url : undefined,
    csvUrl: lower.includes('.csv') ? url : undefined,
    pdfUrl: lower.includes('.pdf') ? url : undefined,
    txtUrl: ui.extra_urls?.txt || null,
    rosterText: ui.roster_text || null,
    isRegistration,
    filename: ui.filename || url.split('/').pop()?.split('?')[0] || 'document',
    fileType: ui.file_type || 'DOCX',
    typeLabel: isRegistration
      ? 'Event Attendee & Registration Document'
      : isGoogleDoc
        ? 'Google Docs Expense Report'
        : 'Word & Google Docs Compatible',
    title: ui.title || 'Document',
    allUrls: [url, ...Object.values(ui.extra_urls || {})].filter(Boolean),
  };
}

export function toQrCard(ui) {
  const transparent = ui.background === 'transparent';
  return {
    link: ui.link || '',
    svgUrl: playableUrl(ui.svg_url),
    pngUrl: playableUrl(ui.png_url),
    filename: ui.filename || 'qr_code',
    color: ui.color || '#000000',
    background: transparent ? '' : ui.background || '#FFFFFF',
    transparent,
  };
}

export function toEmailDraft(ui) {
  const subject = ui.subject || '';
  const body = ui.body || '';
  return {
    subject,
    body,
    intro: ui.intro || '',
    fullText: `Subject: ${subject}\n\n${body}`,
    gmailUrl: `https://mail.google.com/mail/?view=cm&fs=1&tf=1&su=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`,
    mailtoUrl: `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`,
  };
}

export function toVariants(ui) {
  const variants = (ui.variants || []).map((v) => ({
    header: `Variant ${v.number}: ${v.name}`,
    body: v.body,
  }));
  return ui.intro ? [{ header: 'Introduction', body: ui.intro }, ...variants] : variants;
}

function calendarOption(option, idx, title, location, description) {
  const [year, month, day] = option.date.split('-').map((n) => parseInt(n, 10));
  const pad = (n) => String(n).padStart(2, '0');
  const stamp = `${year}${pad(month)}${pad(day)}`;
  const startStr = `${stamp}T180000`;
  const endStr = `${stamp}T213000`;
  const calTitle = title || 'Community AI Meetup';
  let gcalUrl = `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${encodeURIComponent(calTitle)}&dates=${startStr}/${endStr}&details=${encodeURIComponent(description)}&ctz=Europe/Warsaw`;
  if (location) gcalUrl += `&location=${encodeURIComponent(location)}`;
  const ics = [
    'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Community AI Studio//EN', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH',
    'BEGIN:VEVENT',
    `UID:meetup-${option.date}@gdg-agents.web.app`,
    `DTSTAMP:${year}0101T000000Z`,
    `DTSTART;TZID=Europe/Warsaw:${startStr}`,
    `DTEND;TZID=Europe/Warsaw:${endStr}`,
    `SUMMARY:${calTitle}`,
    `DESCRIPTION:${description}`,
    ...(location ? [`LOCATION:${location}`] : []),
    'STATUS:CONFIRMED', 'END:VEVENT', 'END:VCALENDAR',
  ].join('\r\n');
  const monthName = MONTHS[month - 1];
  return {
    fullDateStr: `${option.weekday}, ${monthName} ${day}, ${year}`,
    isoDate: option.date,
    weekday: option.weekday,
    day,
    monthName,
    year,
    monthShort: monthName.slice(0, 3).toUpperCase(),
    dateObj: new Date(year, month - 1, day, 18, 0, 0),
    reason: option.reason || '',
    isPrimary: Boolean(option.primary) || idx === 0,
    label: idx === 0 ? 'Optimal Choice' : `Alternative Option ${idx + 1}`,
    timeRange: '18:00 – 21:30',
    gcalUrl,
    icsDataUri: `data:text/calendar;charset=utf8,${encodeURIComponent(ics)}`,
    icsFilename: `event_${option.date}.ics`,
  };
}

export function toEventDates(ui) {
  const title = ui.event_title || '';
  const location = ui.location || '';
  const description = title ? `Community Technical Meetup: ${title}.` : 'Community Technical Meetup.';
  const dates = (ui.dates || []).map((option, idx) => calendarOption(option, idx, title, location, description));
  return { eventTitle: title, location, dates, primaryDate: dates[0], totalOptions: dates.length };
}

// --------------------------------------------------------------------------- receipts

export function formatMoney(amount, currency = '') {
  if (amount === null || amount === undefined || Number.isNaN(Number(amount))) return '—';
  const text = Number(amount)
    .toFixed(2)
    .replace(/\B(?=(\d{3})+(?!\d))/g, '\u2009');
  return currency ? `${text} ${currency}` : text;
}

function csvCell(value) {
  const text = value === null || value === undefined ? '' : String(value);
  return /[",;\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/** One row per line item (or per receipt without items), ready for Google Sheets / Excel. */
export function receiptSummaryCsv(summary) {
  const target = summary?.target_currency || '';
  const comm = summary?.community_currency || '';
  const includeComm = Boolean(comm && comm !== target);
  const header = [
    'Receipt',
    'Merchant',
    'Date',
    'Category',
    'Item',
    'Quantity',
    'Unit price',
    'Item total',
    'Receipt total',
    'Currency',
    `Receipt total (${target})`,
    ...(includeComm ? [`Receipt total (${comm})`] : []),
  ];
  const rows = [header];
  for (const r of summary?.receipts || []) {
    const base = [r.index, r.merchant, r.date, r.category];
    const tail = [
      r.total ?? '',
      r.currency,
      r.total_target ?? '',
      ...(includeComm ? [r.total_community ?? ''] : []),
    ];
    if (r.items?.length) {
      for (const item of r.items) rows.push([...base, item.name, item.quantity ?? '', item.unit_price ?? '', item.total ?? '', ...tail]);
    } else {
      rows.push([...base, '', '', '', '', ...tail]);
    }
  }
  return rows.map((row) => row.map(csvCell).join(',')).join('\n') + '\n';
}

// --------------------------------------------------------------------------- post plan

export const PLATFORM_LABELS = {
  linkedin: 'LinkedIn',
  instagram: 'Instagram',
  facebook: 'Facebook',
  x: 'X',
  threads: 'Threads',
  bluesky: 'Bluesky',
  mastodon: 'Mastodon',
};

/** All written posts as plain text, grouped by date, for pasting into a doc or a chat. */
export function postPlanText(plan) {
  const out = [];
  for (const slot of plan?.slots || []) {
    out.push(`${slot.date} (${slot.weekday}) - ${slot.label}: ${slot.theme}`);
    for (const channel of slot.channels || []) {
      const post = slot.posts?.[channel.platform];
      out.push(`\n[${PLATFORM_LABELS[channel.platform] || channel.platform} · ${channel.format}]`);
      out.push(post?.text || '(not written yet)');
      if (post?.visual) out.push(`Visual: ${post.visual}`);
    }
    out.push('\n---\n');
  }
  return out.join('\n').trim();
}

function icsEscape(text) {
  return String(text || '')
    .replace(/\\/g, '\\\\')
    .replace(/;/g, '\;')
    .replace(/,/g, '\\,')
    .replace(/\r?\n/g, '\\n');
}

/** Posting reminders (10:00 Europe/Warsaw on each slot date) with the post texts inside. */
export function postPlanIcs(plan, hour = 10) {
  const pad = (n) => String(n).padStart(2, '0');
  const lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Community AI Studio//Post plan//EN', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH'];
  for (const slot of plan?.slots || []) {
    const stamp = slot.date.replace(/-/g, '');
    const networks = (slot.channels || []).map((c) => PLATFORM_LABELS[c.platform] || c.platform).join(' + ');
    const body = (slot.channels || [])
      .map((c) => `${PLATFORM_LABELS[c.platform] || c.platform} (${c.format}):\n${slot.posts?.[c.platform]?.text || '(not written yet)'}`)
      .join('\n\n');
    lines.push(
      'BEGIN:VEVENT',
      `UID:post-${stamp}-${slot.id}@community-studio`,
      `DTSTAMP:${stamp}T000000Z`,
      `DTSTART;TZID=Europe/Warsaw:${stamp}T${pad(hour)}0000`,
      `DTEND;TZID=Europe/Warsaw:${stamp}T${pad(hour)}1500`,
      `SUMMARY:${icsEscape(`Post ${networks}: ${slot.label} - ${slot.theme}`)}`,
      `DESCRIPTION:${icsEscape(body)}`,
      'END:VEVENT'
    );
  }
  lines.push('END:VCALENDAR');
  return lines.join('\r\n');
}
