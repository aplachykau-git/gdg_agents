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

export function getEventUiPayload(event) {
  const meta = event?.customMetadata || event?.custom_metadata;
  if (meta?.ui?.type) return meta.ui;
  for (const response of functionResponses(event)) {
    if (response?.ui?.type) return response.ui;
  }
  return null;
}

/**
 * Map<eventIndex, payload> plus the set of event indices whose turn already has a structured
 * payload (legacy text parsing is skipped there, so the same deliverable is not rendered twice).
 */
export function computeUiCards(events) {
  const cards = new Map();
  const structuredTurnEvents = new Set();
  let turn = [];
  let turnHasPayload = false;
  const closeTurn = () => {
    if (turnHasPayload) turn.forEach((idx) => structuredTurnEvents.add(idx));
    turn = [];
    turnHasPayload = false;
  };
  (events || []).forEach((event, idx) => {
    if (!event) return;
    if (event.author === 'user') {
      closeTurn();
      return;
    }
    turn.push(idx);
    const payload = getEventUiPayload(event);
    if (payload) {
      cards.set(idx, payload);
      turnHasPayload = true;
    }
  });
  closeTurn();
  return { cards, structuredTurnEvents };
}

// --------------------------------------------------------------------------- adapters

function playableUrl(rawUrl) {
  if (!rawUrl) return '';
  if (rawUrl.startsWith('file://')) {
    const filename = rawUrl.split('/').pop()?.split('?')[0];
    return filename ? `/renders/${filename}` : rawUrl;
  }
  return rawUrl;
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
