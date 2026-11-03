import { cleanAuthorName } from '../agents.js';

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
  
  // Search for Subject: header in the text
  const subjectMatch = text.match(/(?:^|\n)(?:```(?:text|markdown|email)?\s*\n)?(?:\*\*|\*|#+\s*)?Subject\s*:\s*([^\n]+)\n([\s\S]+)/i);
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
      trimmed.match(/^\[(?:Download|View|Expense|Successfully|Open)[^\]]*\]\([^\)]+\)/i) ||
      trimmed.match(/^(?:https?:\/\/|\/results\/|file:\/\/)[^\s\)]+?\.(?:docx|xlsx|csv|pdf)$/i) ||
      trimmed.match(/^https?:\/\/docs\.google\.com\/document\/d\/[^\s]+$/i) ||
      // Redundant download sentences
      trimmed.match(/^(?:You can download the report|Download link|Generated Deliverables)/i) ||
      trimmed.match(/^[-*•]?\s*(?:📁|📥)\s*Download/i) ||
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

export function looksLikeLegacyCard(text, author) {
  return Boolean(
    parseResponseVariants(text, author).length > 1 ||
      isAgendaOutput(text, author) ||
      extractEventDates(text, author) ||
      extractMediaAssets(text) ||
      extractDocumentAssets(text) ||
      extractEmailDraft(text, author)
  );
}
