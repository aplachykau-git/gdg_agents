/**
 * Google Drive in the studio, the way connected apps work in Claude: the user picks files or a
 * folder in Google's own Picker instead of pasting links, and the app only gets access to what
 * was picked (drive.file scope when an OAuth client ID is configured).
 *
 *  - pickFromDrive({ mode: 'folder' | 'files' | 'doc' })  -> [{ id, name, mimeType, url }]
 *  - driveFileToAttachment(file)                          -> staged chat attachment
 *
 * Token: a cached access token (sessionStorage, with expiry) -> Google Identity Services token
 * client when VITE_GOOGLE_OAUTH_CLIENT_ID is set (drive.file, silent refresh) -> the Firebase
 * Google sign-in popup as a fallback (its token already carries Drive scopes).
 *
 * Needs the "Google Picker API" enabled in the Cloud project and the browser API key allowed to
 * call it. Pure helpers are exported for tests and do not touch the network.
 */

const env = (typeof import.meta !== 'undefined' && import.meta.env) || {};

import { loginWithGoogle } from '../firebase.js';

export const DRIVE_FILE_SCOPE = 'https://www.googleapis.com/auth/drive.file';
const TOKEN_KEY = 'google_drive_token';
const EXPIRY_KEY = 'google_drive_token_expiry';
const MAX_TEXT_CHARS = 400_000;
const MAX_BINARY_BYTES = 15 * 1024 * 1024;

export const GOOGLE_MIME = {
  folder: 'application/vnd.google-apps.folder',
  document: 'application/vnd.google-apps.document',
  spreadsheet: 'application/vnd.google-apps.spreadsheet',
  presentation: 'application/vnd.google-apps.presentation',
};

/** Files the agents can read: Google Docs/Sheets/Slides, PDFs, images, CSV and text. */
export const PICKABLE_MIME_TYPES = [
  GOOGLE_MIME.document,
  GOOGLE_MIME.spreadsheet,
  GOOGLE_MIME.presentation,
  'application/pdf',
  'image/png',
  'image/jpeg',
  'image/webp',
  'image/heic',
  'text/csv',
  'text/plain',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
];

export function driveConfig() {
  return {
    clientId: env.VITE_GOOGLE_OAUTH_CLIENT_ID || '',
    apiKey: env.VITE_GOOGLE_PICKER_API_KEY || env.VITE_FIREBASE_API_KEY || '',
    appId: env.VITE_FIREBASE_PROJECT_NUMBER || env.VITE_FIREBASE_MESSAGING_SENDER_ID || '',
  };
}

export function isDriveAvailable() {
  const { apiKey, appId } = driveConfig();
  return typeof window !== 'undefined' && Boolean(apiKey && appId);
}

// ------------------------------------------------------------------ pure helpers (tested)

/** How to turn a Drive file into something an agent can read. */
export function readPlan(mimeType) {
  if (mimeType === GOOGLE_MIME.document) return { kind: 'export', exportMime: 'text/markdown', fallbackMime: 'text/plain', ext: '.md' };
  if (mimeType === GOOGLE_MIME.presentation) return { kind: 'export', exportMime: 'text/plain', ext: '.txt' };
  if (mimeType === GOOGLE_MIME.spreadsheet) return { kind: 'sheets', ext: '.csv.txt' };
  if (mimeType === GOOGLE_MIME.folder) return { kind: 'unsupported', reason: 'Folders cannot be attached; pick files inside it.' };
  if (mimeType?.startsWith('application/vnd.google-apps.')) return { kind: 'unsupported', reason: 'This Google file type cannot be read yet.' };
  return { kind: 'download' };
}

/** Sheets API range for a whole tab: names with spaces or symbols are quoted, quotes doubled. */
export function sheetRange(title) {
  return /^[A-Za-z0-9_]+$/.test(title) ? title : `'${String(title).replace(/'/g, "''")}'`;
}

function csvCell(value) {
  const text = value === null || value === undefined ? '' : String(value);
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function valuesToCsv(values) {
  return (values || []).map((row) => (row || []).map(csvCell).join(',')).join('\n');
}

/** Every tab of a spreadsheet as one text: "## Sheet: <name>" followed by its CSV. */
export function sheetsToText(title, tabs) {
  const parts = [`# ${title}`];
  for (const tab of tabs || []) {
    parts.push(`\n## Sheet: ${tab.title}\n${valuesToCsv(tab.values) || '(empty)'}`);
  }
  return parts.join('\n');
}

export function utf8ToBase64(text) {
  const bytes = new TextEncoder().encode(text);
  let binary = '';
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  return btoa(binary);
}

export function textAttachment(name, text, driveFile) {
  const clipped = text.length > MAX_TEXT_CHARS ? `${text.slice(0, MAX_TEXT_CHARS)}\n\n[truncated: file is longer than ${MAX_TEXT_CHARS} characters]` : text;
  return {
    name,
    type: 'text/plain',
    data: utf8ToBase64(`[Google Drive file: ${driveFile.name} (${driveFile.url || driveFile.id})]\n\n${clipped}`),
    preview: null,
    source: 'drive',
    driveId: driveFile.id,
  };
}

// ------------------------------------------------------------------ token

function storage() {
  try {
    return typeof sessionStorage !== 'undefined' ? sessionStorage : null;
  } catch {
    return null;
  }
}

export function rememberToken(token, expiresInSeconds = 3300) {
  const s = storage();
  if (!s || !token) return;
  s.setItem(TOKEN_KEY, token);
  s.setItem(EXPIRY_KEY, String(Date.now() + expiresInSeconds * 1000));
}

export function cachedToken() {
  const s = storage();
  if (!s) return '';
  const token = s.getItem(TOKEN_KEY) || '';
  const expiry = parseInt(s.getItem(EXPIRY_KEY) || '0', 10);
  // Tokens saved before expiry tracking existed are treated as expired.
  return token && expiry > Date.now() + 60_000 ? token : '';
}

const scripts = new Map();
function loadScript(src) {
  if (!scripts.has(src)) {
    scripts.set(
      src,
      new Promise((resolve, reject) => {
        const el = document.createElement('script');
        el.src = src;
        el.async = true;
        el.onload = resolve;
        el.onerror = () => {
          scripts.delete(src);
          reject(new Error(`Could not load ${src}`));
        };
        document.head.appendChild(el);
      })
    );
  }
  return scripts.get(src);
}

let tokenClient = null;
let consentGiven = false;

async function gisToken(clientId) {
  await loadScript('https://accounts.google.com/gsi/client');
  return new Promise((resolve, reject) => {
    tokenClient = window.google.accounts.oauth2.initTokenClient({
      client_id: clientId,
      scope: DRIVE_FILE_SCOPE,
      callback: (resp) => {
        if (resp.error) return reject(new Error(resp.error_description || resp.error));
        consentGiven = true;
        rememberToken(resp.access_token, Math.max(60, (resp.expires_in || 3600) - 300));
        resolve(resp.access_token);
      },
      error_callback: (err) => reject(new Error(err?.message || err?.type || 'Google sign-in was cancelled')),
    });
    tokenClient.requestAccessToken({ prompt: consentGiven ? '' : 'consent' });
  });
}

export async function getDriveToken() {
  const cached = cachedToken();
  if (cached) return cached;
  const { clientId } = driveConfig();
  if (clientId) return gisToken(clientId);
  const { accessToken } = await loginWithGoogle();
  if (!accessToken) throw new Error('Google did not return a Drive access token.');
  rememberToken(accessToken);
  return accessToken;
}

// ------------------------------------------------------------------ picker

async function loadPicker() {
  await loadScript('https://apis.google.com/js/api.js');
  await new Promise((resolve) => window.gapi.load('picker', resolve));
  return window.google.picker;
}

/**
 * Open the Google Picker. `mode`: 'files' (multi-select, readable types + upload), 'folder'
 * (one folder for generated reports), 'doc' (one Google Doc, e.g. a report template).
 * Resolves with the picked files, or [] when the user closes the dialog.
 */
export async function pickFromDrive({ mode = 'files', title = '' } = {}) {
  const [token, picker] = await Promise.all([getDriveToken(), loadPicker()]);
  const { apiKey, appId } = driveConfig();
  return new Promise((resolve) => {
    const builder = new picker.PickerBuilder().setOAuthToken(token).setDeveloperKey(apiKey).setAppId(appId).setOrigin(window.location.origin);
    if (mode === 'folder') {
      builder.addView(new picker.DocsView(picker.ViewId.FOLDERS).setIncludeFolders(true).setSelectFolderEnabled(true).setMimeTypes(GOOGLE_MIME.folder));
      builder.setTitle(title || 'Choose the folder for generated reports');
    } else if (mode === 'doc') {
      builder.addView(new picker.DocsView(picker.ViewId.DOCUMENTS));
      builder.setTitle(title || 'Choose a Google Docs template');
    } else {
      builder.addView(new picker.DocsView(picker.ViewId.DOCS).setIncludeFolders(true).setMimeTypes(PICKABLE_MIME_TYPES.join(',')));
      builder.addView(new picker.DocsView(picker.ViewId.RECENTLY_PICKED));
      builder.addView(new picker.DocsUploadView());
      builder.enableFeature(picker.Feature.MULTISELECT_ENABLED);
      builder.setTitle(title || 'Attach from Google Drive');
    }
    builder.setCallback((data) => {
      const action = data[picker.Response.ACTION];
      if (action === picker.Action.PICKED) {
        resolve(
          (data[picker.Response.DOCUMENTS] || []).map((doc) => ({
            id: doc[picker.Document.ID],
            name: doc[picker.Document.NAME],
            mimeType: doc[picker.Document.MIME_TYPE],
            url: doc[picker.Document.URL],
          }))
        );
      } else if (action === picker.Action.CANCEL) {
        resolve([]);
      }
    });
    builder.build().setVisible(true);
  });
}

// ------------------------------------------------------------------ reading files

async function driveFetch(url, token) {
  const resp = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  if (!resp.ok) {
    let detail = '';
    try {
      detail = (await resp.json())?.error?.message || '';
    } catch {
      /* not JSON */
    }
    throw new Error(`Google Drive ${resp.status}${detail ? `: ${detail}` : ''}`);
  }
  return resp;
}

async function readSpreadsheet(file, token) {
  const base = `https://sheets.googleapis.com/v4/spreadsheets/${encodeURIComponent(file.id)}`;
  const meta = await (await driveFetch(`${base}?fields=properties.title,sheets.properties.title`, token)).json();
  const titles = (meta.sheets || []).map((s) => s.properties.title);
  const ranges = titles.map((t) => `ranges=${encodeURIComponent(sheetRange(t))}`).join('&');
  const values = titles.length ? await (await driveFetch(`${base}/values:batchGet?${ranges}&valueRenderOption=FORMATTED_VALUE`, token)).json() : { valueRanges: [] };
  const tabs = titles.map((title, i) => ({ title, values: values.valueRanges?.[i]?.values || [] }));
  return sheetsToText(meta.properties?.title || file.name, tabs);
}

/** Download or export a picked file and return it as a staged chat attachment. */
export async function driveFileToAttachment(file) {
  const token = await getDriveToken();
  const plan = readPlan(file.mimeType);
  const filesUrl = `https://www.googleapis.com/drive/v3/files/${encodeURIComponent(file.id)}`;
  if (plan.kind === 'unsupported') throw new Error(`${file.name}: ${plan.reason}`);
  if (plan.kind === 'sheets') {
    return textAttachment(`${file.name}${plan.ext}`, await readSpreadsheet(file, token), file);
  }
  if (plan.kind === 'export') {
    let resp;
    try {
      resp = await driveFetch(`${filesUrl}/export?mimeType=${encodeURIComponent(plan.exportMime)}`, token);
    } catch (err) {
      if (!plan.fallbackMime) throw err;
      resp = await driveFetch(`${filesUrl}/export?mimeType=${encodeURIComponent(plan.fallbackMime)}`, token);
    }
    return textAttachment(`${file.name}${plan.ext}`, await resp.text(), file);
  }
  const blob = await (await driveFetch(`${filesUrl}?alt=media`, token)).blob();
  if (blob.size > MAX_BINARY_BYTES) throw new Error(`${file.name} is larger than 15 MB.`);
  const dataUrl = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
  const type = file.mimeType || blob.type || 'application/octet-stream';
  return {
    name: file.name,
    type,
    data: String(dataUrl).split(',')[1],
    preview: type.startsWith('image/') ? dataUrl : null,
    source: 'drive',
    driveId: file.id,
  };
}
