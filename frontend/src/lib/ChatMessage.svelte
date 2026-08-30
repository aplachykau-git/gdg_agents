<script>
  import { 
    User, 
    Paperclip, 
    AlertCircle, 
    Workflow, 
    ArrowRight 
  } from '@lucide/svelte';
  import { 
    getAgentTheme, 
    getEventError, 
    renderMarkdown, 
    isAgendaOutput, 
    parseResponseVariants, 
    extractMediaAssets,
    cleanTextForMediaDisplay,
    extractDocumentAssets,
    cleanTextForDocumentDisplay,
    extractEmailDraft,
    extractEventDates,
    shouldShowDelegationHandoff,
    getEventAgent
  } from './constants.js';
  import AgendaTimeline from './AgendaTimeline.svelte';
  import VariantCard from './VariantCard.svelte';
  import ToolCallCard from './ToolCallCard.svelte';
  import VideoPreviewCard from './VideoPreviewCard.svelte';
  import ReportDownloadCard from './ReportDownloadCard.svelte';
  import EmailDraftCard from './EmailDraftCard.svelte';
  import EventDateCard from './EventDateCard.svelte';

  let { 
    event, 
    index = 0, 
    allEvents = [], 
    onRefine = () => {} 
  } = $props();

  const errInfo = $derived(getEventError(event));
  const eventAgent = $derived(getEventAgent(event));
  const theme = $derived(getAgentTheme(eventAgent || event?.author));
  const showHandoff = $derived(shouldShowDelegationHandoff(event, index, allEvents));
  const messageParts = $derived.by(() => {
    if (event?.content?.parts && event.content.parts.length > 0) {
      return event.content.parts;
    }
    if (event?.output?.summary) {
      return [{ text: event.output.summary }];
    }
    return [];
  });

  const hasVariants = $derived(
    messageParts.some(p => p.text && parseResponseVariants(p.text, event.author).length > 1)
  );
  const hasAgenda = $derived(
    messageParts.some(p => p.text && isAgendaOutput(p.text, event.author))
  );
  const hasEventDate = $derived(
    messageParts.some(p => p.text && extractEventDates(p.text, event.author))
  );
  const hasMedia = $derived(
    messageParts.some(p => p.text && extractMediaAssets(p.text))
  );
  const hasDoc = $derived(
    messageParts.some(p => p.text && extractDocumentAssets(p.text))
  );
  const hasEmail = $derived(
    messageParts.some(p => p.text && extractEmailDraft(p.text, event.author))
  );
  const isWide = $derived(Boolean(hasVariants || hasAgenda || hasEventDate || hasMedia || hasDoc || hasEmail));
</script>

{#if errInfo}
  <!-- Error Event Card -->
  <div class="message-row error-row">
    <div class="message-card error-card">
      <div class="error-card-header">
        <div class="error-badge-pill">
          <AlertCircle size={14} />
          <span>Execution Error ({theme.label || event.author || 'Agent'})</span>
        </div>
      </div>
      <div class="error-body">
        <p class="error-text-main">{errInfo.message}</p>
        {#if errInfo.code}
          <div class="error-code-chip">{errInfo.code}</div>
        {/if}
      </div>
    </div>
  </div>
{:else if event.author === 'user'}
  <!-- User Prompt Bubble -->
  <div class="message-row user-row">
    <div class="message-card user-card">
      <div class="card-author">
        <User size={14} />
        <span>User</span>
      </div>
      
      {#if event.content && event.content.parts}
        {#each event.content.parts as part}
          {#if part.text}
            <div class="markdown-body">{@html renderMarkdown(part.text)}</div>
          {/if}
          
          {#if part.inline_data || part.inlineData}
            {@const data = part.inline_data || part.inlineData}
            <div class="user-attached-file-badge">
              <Paperclip size={13} class="badge-paperclip" />
              <span class="badge-filename">Attached Media ({(data.mime_type || data.mimeType || 'file').replace('image/', 'img:').replace('video/', 'video:')})</span>
              <span class="badge-status-dot"></span>
              <span class="badge-status-label">Transferred</span>
            </div>
          {/if}
        {/each}
      {/if}
    </div>
  </div>
{:else}
  <!-- Agent Delegation Divider (When transferring between agents) -->
  {#if showHandoff}
    <div class="agent-delegation-divider">
      <div class="delegation-line"></div>
      <div class="delegation-badge" style="--pill-color: {theme.color}; --pill-bg: {theme.bg};">
        <Workflow size={13} class="delegation-icon" />
        <span>Task routed to <strong>{theme.label}</strong></span>
        <ArrowRight size={12} class="delegation-arrow" />
      </div>
      <div class="delegation-line"></div>
    </div>
  {/if}

  <!-- Model Response Card -->
  <div class="message-row model-row" style="--agent-color: {theme.color}; --agent-bg: {theme.bg}">
    <div class="message-card model-card" class:wide-card={isWide}>
      <div class="model-author-header">
        <div class="agent-badge-pill" style="background: {theme.bg}; color: {theme.color}; border: 1px solid {theme.color}40;">
          <span class="badge-dot" style="background: {theme.color}"></span>
          <span>{theme.label}</span>
        </div>
      </div>

      {#if messageParts.length > 0}
        {#each messageParts as part}
          {#if part.text}
            {@const emailDraft = extractEmailDraft(part.text, event.author)}
            {@const eventData = extractEventDates(part.text, event.author)}
            {@const media = extractMediaAssets(part.text)}
            {@const doc = extractDocumentAssets(part.text)}
            {#if emailDraft}
              <EmailDraftCard {emailDraft} onRefine={onRefine} />
            {:else if isAgendaOutput(part.text, event.author)}
              <AgendaTimeline 
                rawText={part.text} 
                author={event.author} 
                onRefine={(refinedText) => onRefine(refinedText)} 
              />
            {:else if eventData}
              <div class="markdown-body">{@html renderMarkdown(part.text)}</div>
              <EventDateCard {eventData} onRefine={onRefine} />
            {:else if media}
              {@const cleanedText = cleanTextForMediaDisplay(part.text)}
              {#if cleanedText}
                <div class="markdown-body">{@html renderMarkdown(cleanedText)}</div>
              {/if}
              <VideoPreviewCard {media} />
            {:else if doc}
              {@const cleanedText = cleanTextForDocumentDisplay(part.text)}
              {#if cleanedText}
                <div class="markdown-body">{@html renderMarkdown(cleanedText)}</div>
              {/if}
              <ReportDownloadCard {doc} />
            {:else}
              {@const variants = parseResponseVariants(part.text, event.author)}
              {#if variants.length === 1}
                <div class="markdown-body">{@html renderMarkdown(part.text)}</div>
              {:else}
                <VariantCard {variants} onRefine={onRefine} />
              {/if}
            {/if}
          {/if}

          <!-- Tool Call & Response Steps -->
          <ToolCallCard {part} />
        {/each}
      {/if}
    </div>
  </div>
{/if}

<style>
  .message-row {
    display: flex;
    flex-direction: column;
    margin-bottom: 20px;
    width: 100%;
    content-visibility: auto;
    contain-intrinsic-size: 120px;
  }

  .user-row {
    align-items: flex-end;
  }

  .model-row {
    align-items: flex-start;
  }

  .message-card {
    max-width: 88%;
    border-radius: var(--radius-lg);
    padding: 16px 20px;
    position: relative;
    box-shadow: var(--shadow-sm);
    word-break: break-word;
  }

  .user-card {
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    border-bottom-right-radius: 4px;
    color: var(--text-primary);
    width: fit-content;
    max-width: 88%;
  }

  .model-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-top-left-radius: 4px;
    color: var(--text-primary);
    width: fit-content;
    max-width: 88%;
    min-width: min(100%, 260px);
    transition: width 0.2s ease, max-width 0.2s ease;
  }

  .model-card.wide-card,
  :global(.model-card:has(table)),
  :global(.model-card:has(pre)) {
    width: 100%;
    max-width: 100%;
  }

  .card-author {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: 8px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .model-author-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
  }

  .agent-badge-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 3px 10px;
    border-radius: var(--radius-full);
    font-size: 12px;
    font-weight: 600;
  }

  .badge-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
  }

  /* User File Attachment Badge */
  .user-attached-file-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: var(--bg-app);
    border: 1px solid var(--border-subtle);
    padding: 4px 10px;
    border-radius: var(--radius-sm);
    font-size: 11px;
    color: var(--text-secondary);
    margin-top: 8px;
  }

  :global(.badge-paperclip) {
    color: var(--text-tertiary);
  }

  .badge-status-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--accent-green, #34a853);
  }

  .badge-status-label {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    color: var(--accent-green, #34a853);
  }

  /* Agent Delegation Handoff Divider */
  .agent-delegation-divider {
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 16px 0;
    width: 100%;
  }

  .delegation-line {
    flex: 1;
    height: 1px;
    background: var(--border-subtle);
  }

  .delegation-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    border-radius: var(--radius-full);
    font-size: 12px;
    background: var(--pill-bg, var(--primary-accent-container));
    color: var(--pill-color, var(--primary-accent));
    border: 1px solid var(--border-subtle);
  }

  :global(.delegation-icon), :global(.delegation-arrow) {
    opacity: 0.8;
  }

  /* Error Card */
  .error-row {
    align-items: center;
  }

  .error-card {
    background: rgba(234, 67, 53, 0.08);
    border: 1px solid rgba(234, 67, 53, 0.3);
    width: 100%;
  }

  .error-card-header {
    margin-bottom: 8px;
  }

  .error-badge-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: var(--accent-red, #ea4335);
    font-size: 12px;
    font-weight: 700;
  }

  .error-text-main {
    color: var(--text-primary);
    font-size: 13px;
    line-height: 1.5;
    margin: 0;
  }

  .error-code-chip {
    display: inline-block;
    background: rgba(234, 67, 53, 0.15);
    color: var(--accent-red, #ea4335);
    font-family: monospace;
    font-size: 11px;
    padding: 2px 6px;
    border-radius: var(--radius-xs);
    margin-top: 6px;
  }
</style>
