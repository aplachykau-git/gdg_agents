<script>
  import { 
    User, 
    Paperclip, 
    AlertCircle, 
    Workflow, 
    ArrowRight,
    Film,
    Sparkles
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
    getEventAgent,
    hasVideoScenarios,
    extractVideoScenarios,
    areScenariosComplete
  } from './constants.js';
  import AgendaTimeline from './AgendaTimeline.svelte';
  import VariantCard from './VariantCard.svelte';
  import ToolCallCard from './ToolCallCard.svelte';
  import VideoPreviewCard from './VideoPreviewCard.svelte';
  import ReportDownloadCard from './ReportDownloadCard.svelte';
  import EmailDraftCard from './EmailDraftCard.svelte';
  import EventDateCard from './EventDateCard.svelte';
  import VideoScenarioDeck from './VideoScenarioDeck.svelte';

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

  // Helper to find scenarios from tool response in preceding events of this turn
  function findPrecedingScenarios(currentIdx, eventsList) {
    if (!eventsList || currentIdx <= 0) return null;
    for (let i = currentIdx - 1; i >= 0; i--) {
      const ev = eventsList[i];
      if (!ev) continue;
      if (ev.author === 'user') break; // Stop at previous user prompt
      const parts = ev.content?.parts || [];
      for (const p of parts) {
        const fr = p.function_response || p.functionResponse;
        if (fr && fr.response) {
          if (Array.isArray(fr.response.scenarios) && fr.response.scenarios.length > 0) {
            return fr.response.scenarios;
          }
          if (typeof fr.response.message === 'string' && hasVideoScenarios(fr.response.message)) {
            return fr.response.message;
          }
        }
      }
    }
    return null;
  }

  // Check if a subsequent event in the same turn will render scenarios
  function willSubsequentEventRenderScenarios(currentIdx, eventsList) {
    if (!eventsList || currentIdx >= eventsList.length - 1) return false;
    for (let i = currentIdx + 1; i < eventsList.length; i++) {
      const ev = eventsList[i];
      if (!ev || ev.author === 'user') break;
      const parts = ev.content?.parts || [];
      for (const p of parts) {
        if (p.text && p.text.trim()) return true;
      }
    }
    return false;
  }

  // Resolved scenarios for this event card
  const activeScenarios = $derived.by(() => {
    // 1. Direct scenarios in text
    if (messageParts.some(p => p.text && hasVideoScenarios(p.text))) {
      const p = messageParts.find(p => p.text && hasVideoScenarios(p.text));
      return extractVideoScenarios(p.text);
    }
    // 2. If this is a model text message, see if a preceding tool response in this turn had scenarios
    const isModelText = messageParts.some(p => p.text && p.text.trim());
    if (isModelText) {
      const preceding = findPrecedingScenarios(index, allEvents);
      if (preceding && (Array.isArray(preceding) ? preceding.length > 0 : true)) {
        return extractVideoScenarios(preceding);
      }
    }
    // 3. If this is a tool response event itself, only render if no subsequent model text event exists
    const hasToolResponseScenarios = messageParts.some(p => {
      const fr = p.function_response || p.functionResponse;
      return fr?.response?.scenarios?.length > 0 || (fr?.response?.message && hasVideoScenarios(fr.response.message));
    });
    if (hasToolResponseScenarios && !willSubsequentEventRenderScenarios(index, allEvents)) {
      for (const p of messageParts) {
        const fr = p.function_response || p.functionResponse;
        if (fr?.response?.scenarios?.length > 0) return extractVideoScenarios(fr.response.scenarios);
        if (fr?.response?.message && hasVideoScenarios(fr.response.message)) return extractVideoScenarios(fr.response.message);
      }
    }
    return null;
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
  const hasScenarios = $derived(Boolean(activeScenarios && activeScenarios.length > 0));
  const isWide = $derived(Boolean(hasVariants || hasAgenda || hasEventDate || hasMedia || hasDoc || hasEmail || hasScenarios));

  // Determine if this scenario deck is locked (i.e. subsequent turn took place or render launched)
  const isDeckLocked = $derived.by(() => {
    if (!allEvents || index >= allEvents.length - 1) return false;
    for (let i = index + 1; i < allEvents.length; i++) {
      const ev = allEvents[i];
      if (!ev) continue;
      // If user sent a subsequent message in this conversation
      if (ev.author === 'user') return true;
      // If subsequent event rendered video or confirmed draft
      const parts = ev.content?.parts || [];
      for (const p of parts) {
        if (p.text && extractMediaAssets(p.text)) return true;
        const fr = p.function_response || p.functionResponse;
        if (fr?.response?.assets || (fr?.response?.status === 'success' && fr?.response?.draft)) return true;
      }
    }
    return false;
  });
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
              <VideoPreviewCard {media} onRefine={onRefine} />
            {:else if doc}
              {@const cleanedText = cleanTextForDocumentDisplay(part.text)}
              {#if cleanedText}
                <div class="markdown-body">{@html renderMarkdown(cleanedText)}</div>
              {/if}
              <ReportDownloadCard {doc} />
            {:else if hasVideoScenarios(part.text)}
              <!-- Handled by activeScenarios below -->
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

        {#if activeScenarios && activeScenarios.length > 0}
          {#if areScenariosComplete(activeScenarios)}
            <VideoScenarioDeck 
              scenarios={activeScenarios} 
              isLocked={isDeckLocked}
              onSelect={(msg) => onRefine(msg)} 
              onRegenerate={(msg) => onRefine(msg)} 
            />
          {:else}
            <div class="scenario-progress-card">
              <div class="scenario-progress-header">
                <div class="scenario-progress-icon-wrap">
                  <Film size={18} class="accent-icon" />
                </div>
                <div class="scenario-progress-meta">
                  <div class="scenario-progress-title-row">
                    <span class="scenario-progress-title">Directing 5-Shot Storyboards...</span>
                    <span class="scenario-progress-pill">
                      <Sparkles size={11} />
                      <span>AI Directing</span>
                    </span>
                  </div>
                  <p class="scenario-progress-desc">
                    {#if activeScenarios[0]?.shots?.length > 0}
                      Assembling 10s multi-shot timeline ({activeScenarios[0].shots.length} / 5 shots formed)...
                    {:else}
                      Scouting radical genres and dramatizing narrative metaphors...
                    {/if}
                  </p>
                </div>
              </div>
              <div class="scenario-progress-track">
                <div 
                  class="scenario-progress-fill" 
                  style="width: {Math.max(20, Math.min(95, ((activeScenarios[0]?.shots?.length || 1) / 5) * 100))}%"
                ></div>
              </div>
              <div class="scenario-progress-steps">
                <span class="progress-step-item done">✓ 1. Multi-Axis Genre Scout</span>
                <span class="progress-step-item active">⏳ 2. 5-Shot Storyboards ({activeScenarios[0]?.shots?.length || 0}/5)</span>
                <span class="progress-step-item">3. Style Variations</span>
              </div>
            </div>
          {/if}
        {/if}
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

  /* Scenario Progress Indicator */
  .scenario-progress-card {
    margin-top: 14px;
    background: var(--bg-surface-elevated, #1a1a2e);
    border: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.1));
    border-left: 3px solid var(--agent-video, #ea4335);
    border-radius: 12px;
    padding: 16px 18px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    box-shadow: 0 4px 18px rgba(0, 0, 0, 0.25);
    animation: fadeIn 0.25s ease-out;
  }

  .scenario-progress-header {
    display: flex;
    align-items: flex-start;
    gap: 12px;
  }

  .scenario-progress-icon-wrap {
    width: 36px;
    height: 36px;
    border-radius: 9px;
    background: rgba(234, 67, 53, 0.12);
    border: 1px solid rgba(234, 67, 53, 0.25);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--agent-video, #ea4335);
    flex-shrink: 0;
  }

  .scenario-progress-meta {
    flex: 1;
    min-width: 0;
  }

  .scenario-progress-title-row {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .scenario-progress-title {
    font-size: 14px;
    font-weight: 700;
    color: var(--text-primary, #ffffff);
  }

  .scenario-progress-pill {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: rgba(234, 67, 53, 0.15);
    color: var(--agent-video, #ea4335);
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 9999px;
  }

  .scenario-progress-desc {
    margin: 4px 0 0 0;
    font-size: 12px;
    color: var(--text-secondary, #94a3b8);
  }

  .scenario-progress-track {
    width: 100%;
    height: 5px;
    background: rgba(255, 255, 255, 0.08);
    border-radius: 9999px;
    overflow: hidden;
  }

  .scenario-progress-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--agent-video, #ea4335), #f59e0b);
    border-radius: 9999px;
    transition: width 0.35s ease;
  }

  .scenario-progress-steps {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 11px;
    flex-wrap: wrap;
  }

  .progress-step-item {
    color: var(--text-muted, #64748b);
  }

  .progress-step-item.done {
    color: var(--accent-green, #10b981);
    font-weight: 600;
  }

  .progress-step-item.active {
    color: var(--agent-video, #ea4335);
    font-weight: 600;
  }
</style>
