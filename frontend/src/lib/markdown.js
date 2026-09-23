import { marked } from 'marked';


export const ALLOWED_LINK_PROTOCOLS = new Set(['http:', 'https:']);

export function escapeHtml(value) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function safeLinkUrl(value) {
  try {
    const url = new URL(value);
    return ALLOWED_LINK_PROTOCOLS.has(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

export const markdownRenderer = {
  link({ href, title, tokens }) {
    const label = this.parser.parseInline(tokens);
    const safeUrl = safeLinkUrl(href);
    if (!safeUrl) return label;
    const titleAttribute = title ? ` title="${escapeHtml(title)}"` : '';
    return `<a href="${escapeHtml(safeUrl)}"${titleAttribute} target="_blank" rel="noopener noreferrer">${label}</a>`;
  }
};

marked.use({ renderer: markdownRenderer });

export function renderMarkdown(text) {
  if (!text) return '';
  try {
    return marked.parse(text);
  } catch (e) {
    console.error("Failed to parse markdown:", e);
    return text.replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
}
