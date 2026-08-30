<script>
  import { 
    FileText, 
    FileSpreadsheet, 
    Download, 
    Loader2, 
    Check, 
    Copy,
    Users,
    ExternalLink
  } from '@lucide/svelte';
  import { downloadDirectFile } from './constants.js';

  let { doc = {} } = $props();

  let isDownloading = $state(false);
  let isListCopied = $state(false);
  let isCopyingList = $state(false);

  async function handleDownload(url, filename) {
    if (!url) return;
    isDownloading = true;
    try {
      await downloadDirectFile(url, filename);
    } finally {
      setTimeout(() => {
        isDownloading = false;
      }, 1000);
    }
  }

  async function handleCopyList() {
    isCopyingList = true;
    try {
      let textToCopy = doc?.rosterText || '';
      
      // If not embedded in doc metadata, attempt to fetch from URL as fallback
      if (!textToCopy) {
        const listUrl = doc?.txtUrl || '/results/registrations_list.txt';
        try {
          const res = await fetch(listUrl);
          if (res.ok) {
            const fetched = await res.text();
            // Ensure we didn't receive the SPA index.html fallback
            if (fetched && !fetched.toLowerCase().includes('<!doctype html>') && !fetched.toLowerCase().includes('<html')) {
              textToCopy = fetched.trim();
            }
          }
        } catch (err) {
          console.warn('Direct list fetch failed:', err);
        }
      }

      if (textToCopy) {
        await navigator.clipboard.writeText(textToCopy);
        isListCopied = true;
        setTimeout(() => {
          isListCopied = false;
        }, 2500);
      } else {
        alert('Attendee list is not available in the document.');
      }
    } catch (e) {
      console.warn('Failed to copy attendee list:', e);
    } finally {
      isCopyingList = false;
    }
  }
</script>

{#if doc?.primaryUrl}
  <div class="report-card-container">
    <!-- Top Header / Document Meta -->
    <div class="doc-header-row">
      <div class="doc-icon-wrapper" class:spreadsheet={doc.fileType === 'CSV' || doc.fileType === 'XLSX'}>
        {#if doc.isRegistration}
          <Users size={22} />
        {:else if doc.fileType === 'CSV' || doc.fileType === 'XLSX'}
          <FileSpreadsheet size={22} />
        {:else}
          <FileText size={22} />
        {/if}
      </div>

      <div class="doc-meta-info">
        <div class="doc-title-line">
          <span class="doc-title">{doc.title || doc.filename || 'Expense Reimbursement Report'}</span>
          <span class="doc-type-badge">{doc.fileType || 'DOCX'}</span>
        </div>
        <div class="doc-subtitle">
          <span>{doc.typeLabel || 'Microsoft Word & Google Docs'}</span>
          <span class="dot-separator">•</span>
          <span class="status-ready">Generated & Ready</span>
        </div>
      </div>
    </div>

    <!-- Action Buttons Row -->
    <div class="doc-actions-row">
      {#if doc.isGoogleDoc || doc.gdocUrl || doc.primaryUrl?.includes('docs.google.com')}
        <a 
          class="action-btn primary-download"
          href={doc.gdocUrl || doc.primaryUrl}
          target="_blank"
          rel="noopener noreferrer"
          title="Open Report in Google Docs"
        >
          <ExternalLink size={15} />
          <span>Open in Google Docs</span>
        </a>
      {:else}
        <button 
          class="action-btn primary-download"
          disabled={isDownloading}
          onclick={() => handleDownload(doc.primaryUrl, doc.filename)}
          title="Download {doc.fileType || 'DOCX'} Document"
        >
          {#if isDownloading}
            <Loader2 size={15} class="spin-icon" />
            <span>Downloading...</span>
          {:else}
            <Download size={15} />
            <span>Download {doc.fileType || 'DOCX'}</span>
          {/if}
        </button>
      {/if}

      {#if doc.isRegistration || doc.rosterText || doc.txtUrl}
        <button 
          class="action-btn secondary-btn"
          disabled={isCopyingList}
          onclick={handleCopyList}
          title="Copy clean list of attendees to clipboard"
        >
          {#if isListCopied}
            <Check size={14} class="copied-check" />
            <span>List Copied!</span>
          {:else}
            <Copy size={14} />
            <span>Copy Attendee List</span>
          {/if}
        </button>
      {/if}

      {#if doc.csvUrl && doc.csvUrl !== doc.primaryUrl && !doc.isGoogleDoc}
        <button 
          class="action-btn secondary-btn"
          onclick={() => handleDownload(doc.csvUrl, doc.csvUrl.split('/').pop() || 'report.csv')}
          title="Download CSV Spreadsheet backup"
        >
          <FileSpreadsheet size={14} />
          <span>Download CSV</span>
        </button>
      {/if}
    </div>
  </div>
{/if}

<style>
  .report-card-container {
    display: flex;
    flex-direction: column;
    gap: 14px;
    margin-top: 14px;
    margin-bottom: 6px;
    padding: 16px 18px;
    border-radius: var(--radius-md, 12px);
    background: var(--bg-surface-elevated, #202124);
    border: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.12));
    box-shadow: var(--shadow-sm, 0 2px 8px rgba(0, 0, 0, 0.2));
    animation: fadeIn 0.25s ease-out;
  }

  .doc-header-row {
    display: flex;
    align-items: center;
    gap: 14px;
  }

  .doc-icon-wrapper {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    border-radius: 10px;
    background: rgba(26, 115, 232, 0.15);
    color: var(--gemini-primary, #1a73e8);
    flex-shrink: 0;
  }

  .doc-icon-wrapper.spreadsheet {
    background: rgba(52, 168, 83, 0.15);
    color: #34a853;
  }

  .doc-meta-info {
    display: flex;
    flex-direction: column;
    gap: 3px;
    min-width: 0;
    flex: 1;
  }

  .doc-title-line {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .doc-title {
    font-size: 14.5px;
    font-weight: 600;
    color: var(--text-primary, #ffffff);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .doc-type-badge {
    font-size: 11px;
    font-weight: 700;
    padding: 2px 7px;
    border-radius: 4px;
    background: rgba(26, 115, 232, 0.2);
    color: var(--gemini-primary, #8ab4f8);
    letter-spacing: 0.5px;
  }

  .doc-subtitle {
    font-size: 12px;
    color: var(--text-secondary, #9aa0a6);
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .dot-separator {
    opacity: 0.5;
  }

  .status-ready {
    color: #81c995;
    font-weight: 500;
  }

  .doc-actions-row {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    padding-top: 4px;
  }

  .action-btn {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 8px 16px;
    border-radius: var(--radius-full, 9999px);
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
    border: 1px solid transparent;
    text-decoration: none;
  }

  .action-btn:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 3px 10px rgba(0, 0, 0, 0.25);
  }

  .action-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .primary-download {
    background: var(--gemini-primary, #1a73e8);
    color: #ffffff;
  }

  .primary-download:hover:not(:disabled) {
    background: var(--gemini-primary-hover, #1557b0);
  }

  .secondary-btn {
    background: var(--bg-surface, #1e1e2d);
    color: var(--text-primary, #ffffff);
    border-color: var(--border-subtle, rgba(255, 255, 255, 0.12));
  }

  .secondary-btn:hover:not(:disabled) {
    background: var(--bg-hover, rgba(255, 255, 255, 0.1));
    border-color: var(--border-focus, #8ab4f8);
  }

  :global(.copied-check) {
    color: #81c995;
  }

  :global(.spin-icon) {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
  }
</style>
