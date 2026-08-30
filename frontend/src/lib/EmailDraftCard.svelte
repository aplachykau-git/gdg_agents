<script>
  import { 
    Mail, 
    Copy, 
    Check, 
    RefreshCw, 
    Send
  } from '@lucide/svelte';
  import { renderMarkdown } from './constants.js';

  let { 
    emailDraft = {}, 
    onRefine = () => {} 
  } = $props();

  let copiedField = $state('');

  function copyToClipboard(text, fieldName) {
    if (!navigator.clipboard || !text) return;
    navigator.clipboard.writeText(text).then(() => {
      copiedField = fieldName;
      setTimeout(() => {
        if (copiedField === fieldName) copiedField = '';
      }, 2000);
    }).catch(err => {
      console.error('Failed to copy text:', err);
    });
  }
</script>

<div class="email-draft-container">
  {#if emailDraft.intro}
    <div class="email-intro-text markdown-body">
      {@html renderMarkdown(emailDraft.intro)}
    </div>
  {/if}

  <div class="email-card">
    <!-- Header bar -->
    <div class="email-card-header">
      <div class="email-badge">
        <Mail size={14} class="email-badge-icon" />
        <span>Email Template</span>
      </div>
      <div class="header-status">
        <span class="status-dot"></span>
        <span>Ready to send</span>
      </div>
    </div>

    <!-- Subject Row -->
    <div class="subject-box">
      <div class="subject-label-row">
        <span class="field-label">Subject</span>
        <button 
          class="mini-copy-btn" 
          onclick={() => copyToClipboard(emailDraft.subject, 'subject')}
          title="Copy Subject"
        >
          {#if copiedField === 'subject'}
            <Check size={12} />
            <span>Copied</span>
          {:else}
            <Copy size={12} />
            <span>Copy Subject</span>
          {/if}
        </button>
      </div>
      <div class="subject-content">
        {emailDraft.subject}
      </div>
    </div>

    <!-- Email Body -->
    <div class="body-box">
      <div class="body-label-row">
        <span class="field-label">Message Body</span>
        <button 
          class="mini-copy-btn" 
          onclick={() => copyToClipboard(emailDraft.body, 'body')}
          title="Copy Body"
        >
          {#if copiedField === 'body'}
            <Check size={12} />
            <span>Copied</span>
          {:else}
            <Copy size={12} />
            <span>Copy Body</span>
          {/if}
        </button>
      </div>
      <div class="body-content markdown-body">
        {@html renderMarkdown(emailDraft.body)}
      </div>
    </div>

    <!-- Actions Toolbar -->
    <div class="email-actions-toolbar">
      <div class="primary-actions">
        <!-- Open in Gmail Button -->
        <a 
          href={emailDraft.gmailUrl} 
          target="_blank" 
          rel="noopener noreferrer" 
          class="action-btn gmail-btn"
          title="Open draft in Gmail web app"
        >
          <Mail size={14} />
          <span>Open in Gmail</span>
        </a>

        <!-- System Mail App Button -->
        <a 
          href={emailDraft.mailtoUrl} 
          class="action-btn mail-client-btn"
          title="Open in default desktop mail application"
        >
          <Send size={13} />
          <span>Mail App</span>
        </a>
      </div>

      <div class="secondary-actions">
        <!-- Copy Full Email -->
        <button 
          class="action-btn copy-full-btn" 
          onclick={() => copyToClipboard(emailDraft.fullText, 'full')}
          title="Copy Subject and Body"
        >
          {#if copiedField === 'full'}
            <Check size={13} class="copied-icon" />
            <span>Copied Full</span>
          {:else}
            <Copy size={13} />
            <span>Copy Full</span>
          {/if}
        </button>

        <!-- Refine Button -->
        <button 
          class="action-btn refine-btn" 
          onclick={() => onRefine(emailDraft.fullText)}
          title="Refine this email with the agent"
        >
          <RefreshCw size={13} />
          <span>Refine</span>
        </button>
      </div>
    </div>
  </div>
</div>

<style>
  .email-draft-container {
    display: flex;
    flex-direction: column;
    gap: 10px;
    width: 100%;
    margin-top: 4px;
  }

  .email-intro-text {
    font-size: 13.5px;
    color: var(--text-primary);
  }

  .email-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-left: 3px solid var(--agent-office, #ec4899);
    border-radius: var(--radius-md);
    overflow: hidden;
    box-shadow: var(--shadow-sm);
    transition: var(--transition-normal);
  }

  .email-card:hover {
    border-color: var(--border-medium);
    border-left-color: var(--agent-office, #ec4899);
    box-shadow: var(--shadow-md);
  }

  .email-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 14px;
    background: var(--bg-surface-elevated);
    border-bottom: 1px solid var(--border-subtle);
  }

  .email-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--agent-office, #ec4899);
  }

  :global(.email-badge-icon) {
    color: var(--agent-office, #ec4899);
  }

  .header-status {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    font-weight: 500;
    color: var(--status-success, #34a853);
  }

  .status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--status-success, #34a853);
  }

  .subject-box {
    padding: 12px 14px;
    background: var(--bg-surface);
    border-bottom: 1px solid var(--border-subtle);
  }

  .subject-label-row, .body-label-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 6px;
  }

  .field-label {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-tertiary);
  }

  .mini-copy-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: transparent;
    border: none;
    color: var(--text-secondary);
    font-size: 11px;
    cursor: pointer;
    padding: 2px 6px;
    border-radius: var(--radius-xs);
    transition: var(--transition-fast);
  }

  .mini-copy-btn:hover {
    background: var(--bg-surface-elevated);
    color: var(--primary-accent);
  }

  .subject-content {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    line-height: 1.4;
    word-break: break-word;
  }

  .body-box {
    padding: 12px 14px;
    background: var(--bg-surface);
  }

  .body-content {
    font-size: 13.5px;
    line-height: 1.6;
    color: var(--text-primary);
    background: var(--bg-app);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 12px 14px;
    max-height: 400px;
    overflow-y: auto;
  }

  .body-content :global(p) {
    margin: 0 0 10px 0;
  }

  .body-content :global(p:last-child) {
    margin-bottom: 0;
  }

  .body-content :global(ul) {
    margin: 6px 0 10px 0;
    padding-left: 20px;
  }

  .email-actions-toolbar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 10px 14px;
    background: var(--bg-surface-elevated);
    border-top: 1px solid var(--border-subtle);
  }

  .primary-actions, .secondary-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .action-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    font-weight: 600;
    padding: 6px 12px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border-subtle);
    background: var(--bg-surface);
    color: var(--text-primary);
    cursor: pointer;
    text-decoration: none;
    transition: var(--transition-fast);
  }

  .action-btn:hover {
    background: var(--bg-hover);
    border-color: var(--border-focus);
  }

  .gmail-btn {
    background: #ea4335;
    color: #ffffff;
    border-color: #d93025;
  }

  .gmail-btn:hover {
    background: #d93025;
    color: #ffffff;
    box-shadow: 0 2px 6px rgba(234, 67, 53, 0.35);
  }

  .mail-client-btn:hover {
    color: var(--primary-accent);
    border-color: var(--primary-accent);
  }

  .copy-full-btn:hover {
    color: var(--primary-accent);
  }

  .refine-btn:hover {
    color: var(--agent-office, #ec4899);
    border-color: var(--agent-office, #ec4899);
  }

  :global(.copied-icon) {
    color: var(--status-success, #34a853);
  }
</style>
