<script>
  // Shared shell for every agent deliverable in the chat (QR codes, receipt summaries, post
  // plans, ...). One header / body / footer rhythm so new agents only fill the body and pick
  // their actions instead of inventing a new card layout each time.
  //
  //   <ResultCard accent="var(--agent-qr)" icon={QrCode} title="QR code" subtitle="devfestkrakow.pl">
  //     {#snippet media()}<img ... />{/snippet}
  //     ...body...
  //     {#snippet actions()}<button class="rc-btn primary">Download</button>{/snippet}
  //     {#snippet tools()}<button class="rc-btn ghost">Copy</button>{/snippet}
  //   </ResultCard>
  //
  // Buttons inside use the shared classes `rc-btn` (+ `primary` / `ghost`); small labelled facts
  // use `rc-facts` (a <dl>); status chips use `rc-chip` (+ `ok` / `warn` / `danger`).
  let {
    accent = 'var(--primary-accent)',
    accentBg = '',
    icon: Icon = null,
    title = '',
    subtitle = '',
    status = '',
    statusTone = 'ok',
    children,
    media,
    actions,
    tools,
    headerExtra,
  } = $props();
</script>

<section class="result-card" style="--rc-accent: {accent}; --rc-accent-bg: {accentBg || 'color-mix(in srgb, ' + accent + ' 14%, transparent)'}">
  <header class="rc-head">
    {#if Icon}
      <span class="rc-icon" aria-hidden="true"><Icon size={16} /></span>
    {/if}
    <div class="rc-titles">
      <span class="rc-title">{title}</span>
      {#if subtitle}<span class="rc-subtitle" title={subtitle}>{subtitle}</span>{/if}
    </div>
    {#if headerExtra}<div class="rc-head-extra">{@render headerExtra()}</div>{/if}
    {#if status}
      <span class="rc-status {statusTone}"><span class="rc-status-dot"></span>{status}</span>
    {/if}
  </header>

  <div class="rc-body" class:with-media={Boolean(media)}>
    {#if media}<div class="rc-media">{@render media()}</div>{/if}
    <div class="rc-content">{@render children?.()}</div>
  </div>

  {#if actions || tools}
    <footer class="rc-foot">
      <div class="rc-actions">{@render actions?.()}</div>
      {#if tools}<div class="rc-tools">{@render tools()}</div>{/if}
    </footer>
  {/if}
</section>

<style>
  .result-card {
    width: 100%;
    margin: 12px 0 4px;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    overflow: hidden;
    box-shadow: var(--shadow-sm);
    container-type: inline-size;
  }

  .rc-head {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    background: var(--bg-surface-elevated);
    border-bottom: 1px solid var(--border-subtle);
    min-width: 0;
  }

  .rc-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    width: 28px;
    height: 28px;
    border-radius: var(--radius-sm);
    background: var(--rc-accent-bg);
    color: var(--rc-accent);
  }

  .rc-titles {
    display: flex;
    flex-direction: column;
    min-width: 0;
    flex: 1 1 auto;
    line-height: 1.25;
  }

  .rc-title {
    font-size: 13.5px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .rc-subtitle {
    font-size: 12px;
    color: var(--text-tertiary);
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .rc-head-extra {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
  }

  .rc-status {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
    font-size: 11.5px;
    font-weight: 500;
    color: var(--status-success);
  }

  .rc-status.warn {
    color: var(--status-warning);
  }

  .rc-status.danger {
    color: var(--status-error);
  }

  .rc-status.neutral {
    color: var(--text-tertiary);
  }

  .rc-status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
  }

  .rc-body {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 14px;
  }

  .rc-body.with-media {
    flex-direction: row;
    align-items: flex-start;
  }

  .rc-media {
    flex-shrink: 0;
  }

  .rc-content {
    display: flex;
    flex-direction: column;
    gap: 12px;
    min-width: 0;
    flex: 1 1 auto;
  }

  @container (max-width: 520px) {
    .rc-body.with-media {
      flex-direction: column;
      align-items: stretch;
    }

    .rc-media {
      align-self: center;
    }

    .rc-status {
      display: none;
    }
  }

  .rc-foot {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 10px 14px;
    background: var(--bg-surface-elevated);
    border-top: 1px solid var(--border-subtle);
  }

  .rc-actions,
  .rc-tools {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }

  /* ---- shared building blocks for card bodies ---- */

  .result-card :global(.rc-btn) {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border-medium);
    background: var(--bg-surface);
    color: var(--text-primary);
    font: inherit;
    font-size: 12.5px;
    font-weight: 500;
    line-height: 1.3;
    text-decoration: none;
    cursor: pointer;
    transition: var(--transition-fast);
    white-space: nowrap;
  }

  .result-card :global(.rc-btn:hover:not(:disabled)) {
    border-color: var(--border-focus);
  }

  .result-card :global(.rc-btn.primary) {
    background: var(--primary-accent);
    border-color: transparent;
    color: #ffffff;
  }

  .result-card :global(.rc-btn.primary:hover:not(:disabled)) {
    background: var(--primary-accent-hover);
  }

  .result-card :global(.rc-btn.ghost) {
    background: transparent;
    border-color: transparent;
    color: var(--text-secondary);
  }

  .result-card :global(.rc-btn.ghost:hover:not(:disabled)) {
    color: var(--text-primary);
    background: var(--bg-surface-variant);
  }

  .result-card :global(.rc-btn:disabled) {
    opacity: 0.6;
    cursor: default;
  }

  .result-card :global(.rc-btn:focus-visible) {
    outline: 2px solid var(--border-focus);
    outline-offset: 2px;
  }

  .result-card :global(.rc-facts) {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 6px 14px;
    margin: 0;
    font-size: 12.5px;
  }

  .result-card :global(.rc-facts dt) {
    color: var(--text-tertiary);
  }

  .result-card :global(.rc-facts dd) {
    margin: 0;
    color: var(--text-primary);
    min-width: 0;
    overflow-wrap: anywhere;
  }

  .result-card :global(.rc-chip) {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    border-radius: var(--radius-pill);
    font-size: 11px;
    font-weight: 600;
    background: var(--rc-accent-bg);
    color: var(--rc-accent);
    white-space: nowrap;
  }

  .result-card :global(.rc-chip.neutral) {
    background: var(--bg-surface-variant);
    color: var(--text-secondary);
  }

  .result-card :global(.rc-chip.warn) {
    background: color-mix(in srgb, var(--status-warning) 18%, transparent);
    color: var(--status-warning);
  }

  .result-card :global(.rc-chip.danger) {
    background: color-mix(in srgb, var(--status-error) 18%, transparent);
    color: var(--status-error);
  }

  .result-card :global(.rc-chip.ok) {
    background: color-mix(in srgb, var(--status-success) 18%, transparent);
    color: var(--status-success);
  }

  .result-card :global(.rc-label) {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--text-tertiary);
  }

  .result-card :global(.rc-muted) {
    font-size: 12px;
    color: var(--text-tertiary);
  }
</style>
