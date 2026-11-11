<script>
  // Countdown post plan (payload type "post_plan"): dated slots, the network chosen for each post
  // and why, the written texts with copy buttons, and exports for Sheets (CSV) and Calendar (.ics).
  import { AlertTriangle, CalendarClock, CalendarPlus, Check, ChevronRight, Copy, FileSpreadsheet, Image, Wand2 } from '@lucide/svelte';
  import ResultCard from './ui/ResultCard.svelte';
  import { PLATFORM_LABELS, postPlanIcs, postPlanText } from './ui/payloads.js';

  let { plan = {} } = $props();

  const slots = $derived(plan.slots || []);
  let activeTab = $state({});
  let copiedKey = $state('');

  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const dayParts = (iso) => {
    const [y, m, d] = (iso || '').split('-').map((n) => parseInt(n, 10));
    return { day: d || '', month: MONTHS[(m || 1) - 1], year: y };
  };

  const warnings = $derived(slots.reduce((n, s) => n + Object.values(s.posts || {}).reduce((k, p) => k + (p.warnings?.length || 0), 0), 0));
  const missing = $derived((plan.missing || []).length);
  const status = $derived(
    missing ? { text: `${missing} not written`, tone: 'warn' } : warnings ? { text: `${warnings} to check`, tone: 'warn' } : { text: 'Ready', tone: 'ok' }
  );
  const range = $derived.by(() => {
    if (!slots.length) return '';
    const a = dayParts(slots[0].date);
    const b = dayParts(slots[slots.length - 1].date);
    return `${a.day} ${a.month} – ${b.day} ${b.month} ${b.year}`;
  });
  const total = $derived(Object.values(plan.counts || {}).reduce((a, b) => a + b, 0));
  const subtitle = $derived([plan.event?.name, `${total} posts`, range].filter(Boolean).join(' · '));

  function tabFor(slot) {
    return activeTab[slot.id] || slot.channels?.[0]?.platform;
  }

  async function copy(text, key) {
    try {
      await navigator.clipboard.writeText(text || '');
      copiedKey = key;
      setTimeout(() => (copiedKey = ''), 2000);
    } catch (e) {
      console.warn('Copy failed', e);
    }
  }

  function download(content, filename, type) {
    const url = URL.createObjectURL(new Blob([content], { type }));
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  const fileStem = $derived(`countdown_${(plan.event?.name || 'event').toLowerCase().replace(/[^a-z0-9]+/gi, '_')}`);
</script>

<ResultCard accent="var(--agent-linkedin)" accentBg="var(--bg-linkedin)" icon={CalendarClock} title="Countdown plan" {subtitle} status={status.text} statusTone={status.tone}>
  <div class="overview">
    {#each Object.entries(plan.counts || {}) as [platform, count]}
      {#if count}
        <span class="net-chip {platform}"><span class="net-dot"></span>{PLATFORM_LABELS[platform] || platform} · {count}</span>
      {/if}
    {/each}
    {#if plan.event?.website}
      <a class="rc-muted site" href={plan.event.website} target="_blank" rel="noopener noreferrer">{plan.event.website.replace(/^https?:\/\//, '').replace(/\/$/, '')}</a>
    {/if}
  </div>

  {#if (plan.skipped || []).length}
    <p class="rc-muted skipped">
      Already passed, not planned: {plan.skipped.map((s) => `${s.days} days (${s.theme})`).join(', ')}.
    </p>
  {/if}

  <ol class="timeline">
    {#each slots as slot, i (slot.id)}
      {@const d = dayParts(slot.date)}
      {@const tab = tabFor(slot)}
      {@const post = slot.posts?.[tab]}
      {@const channel = slot.channels.find((c) => c.platform === tab)}
      <li class="slot">
        <details open={i < 2}>
          <summary>
            <span class="date-block">
              <span class="date-day">{d.day}</span>
              <span class="date-month">{d.month}</span>
            </span>
            <span class="slot-main">
              <span class="slot-label">{slot.label} · {slot.weekday}</span>
              <span class="slot-theme">{slot.theme}</span>
            </span>
            <span class="slot-nets">
              {#each slot.channels as c}
                <span class="net-dot-only {c.platform}" title={PLATFORM_LABELS[c.platform] || c.platform}></span>
              {/each}
            </span>
            <ChevronRight size={14} class="chev" />
          </summary>

          <div class="slot-body">
            {#if slot.channels.length > 1}
              <div class="tabs" role="tablist">
                {#each slot.channels as c}
                  <button
                    type="button"
                    role="tab"
                    class="tab {c.platform}"
                    class:active={tab === c.platform}
                    aria-selected={tab === c.platform}
                    onclick={() => (activeTab = { ...activeTab, [slot.id]: c.platform })}
                  >
                    <span class="net-dot"></span>{PLATFORM_LABELS[c.platform]}
                    <span class="tab-format">{c.format}</span>
                  </button>
                {/each}
              </div>
            {:else if channel}
              <div class="single-net"><span class="net-chip {channel.platform}"><span class="net-dot"></span>{PLATFORM_LABELS[channel.platform]}</span><span class="rc-muted">{channel.format}</span></div>
            {/if}

            {#if post}
              <div class="post">
                <p class="post-text">{post.text}</p>
                <button class="rc-btn ghost copy-post" onclick={() => copy(post.text, `${slot.id}-${tab}`)} title="Copy post">
                  {#if copiedKey === `${slot.id}-${tab}`}<Check size={13} />Copied{:else}<Copy size={13} />Copy{/if}
                </button>
              </div>
              <div class="post-meta">
                <span class="rc-muted">{post.chars} / {plan.rules?.[tab]?.max_chars || '—'} characters</span>
                {#if post.visual}<span class="visual"><Image size={12} />{post.visual}</span>{/if}
              </div>
              {#if post.fixes?.length}
                <p class="rc-muted fixes"><Wand2 size={12} />Auto: {post.fixes.join(', ')}</p>
              {/if}
              {#each post.warnings || [] as w}
                <p class="warning"><AlertTriangle size={12} />{w}</p>
              {/each}
            {:else}
              <p class="rc-muted">Not written yet. Ask the planner to write it.</p>
            {/if}

            {#if channel?.reason}
              <p class="rc-muted reason">Why {PLATFORM_LABELS[tab]}: {channel.reason}</p>
            {/if}
          </div>
        </details>
      </li>
    {/each}
  </ol>

  {#snippet actions()}
    <button class="rc-btn primary" onclick={() => copy(postPlanText(plan), 'all')}>
      {#if copiedKey === 'all'}<Check size={14} />Copied{:else}<Copy size={14} />Copy all{/if}
    </button>
    <button class="rc-btn" onclick={() => download(plan.csv || '', `${fileStem}.csv`, 'text/csv;charset=utf-8')} title="Import into Google Sheets or Excel">
      <FileSpreadsheet size={14} />CSV for Sheets
    </button>
    <button class="rc-btn" onclick={() => download(postPlanIcs(plan), `${fileStem}.ics`, 'text/calendar;charset=utf-8')} title="Posting reminders at 10:00 on each date">
      <CalendarPlus size={14} />Calendar
    </button>
  {/snippet}
</ResultCard>

<style>
  .overview {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
  }

  .site {
    margin-left: auto;
    color: var(--text-tertiary);
    text-decoration: none;
  }

  .site:hover {
    color: var(--primary-accent);
  }

  .skipped {
    margin: 0;
  }

  .net-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 3px 10px;
    border-radius: var(--radius-pill);
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    font-size: 12px;
    color: var(--text-primary);
  }

  .net-dot,
  .net-dot-only {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--net-color, var(--text-tertiary));
    flex-shrink: 0;
  }

  .linkedin {
    --net-color: #0a66c2;
  }

  .instagram {
    --net-color: #e1306c;
  }

  .facebook {
    --net-color: #1877f2;
  }

  .x,
  .threads {
    --net-color: var(--text-primary);
  }

  .bluesky {
    --net-color: #1185fe;
  }

  .mastodon {
    --net-color: #6364ff;
  }

  .timeline {
    list-style: none;
    margin: 0;
    padding: 0;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    overflow: hidden;
  }

  .slot + .slot {
    border-top: 1px solid var(--border-subtle);
  }

  summary {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 12px;
    cursor: pointer;
    list-style: none;
  }

  summary::-webkit-details-marker {
    display: none;
  }

  summary:hover {
    background: var(--bg-surface-elevated);
  }

  summary :global(.chev) {
    flex-shrink: 0;
    color: var(--text-tertiary);
    transition: transform 0.15s ease;
  }

  details[open] > summary :global(.chev) {
    transform: rotate(90deg);
  }

  .date-block {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    width: 44px;
    height: 44px;
    border-radius: var(--radius-sm);
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    line-height: 1.05;
  }

  .date-day {
    font-size: 16px;
    font-weight: 700;
    color: var(--text-primary);
  }

  .date-month {
    font-size: 10.5px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-tertiary);
  }

  .slot-main {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
    flex: 1 1 auto;
  }

  .slot-label {
    font-size: 11.5px;
    font-weight: 600;
    color: var(--agent-linkedin);
  }

  .slot-theme {
    font-size: 13.5px;
    font-weight: 600;
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .slot-nets {
    display: flex;
    gap: 4px;
  }

  .slot-body {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 0 12px 12px 68px;
  }

  @container (max-width: 520px) {
    .slot-body {
      padding-left: 12px;
    }
  }

  .tabs {
    display: flex;
    gap: 4px;
    border-bottom: 1px solid var(--border-subtle);
  }

  .tab {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    border: none;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
    background: none;
    color: var(--text-secondary);
    font: inherit;
    font-size: 12.5px;
    cursor: pointer;
  }

  .tab.active {
    color: var(--text-primary);
    border-bottom-color: var(--net-color);
  }

  .tab-format {
    font-size: 11px;
    color: var(--text-tertiary);
  }

  .single-net {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .post {
    position: relative;
    padding: 10px 12px;
    border-radius: var(--radius-sm);
    background: var(--bg-app);
    border: 1px solid var(--border-subtle);
  }

  .post-text {
    margin: 0;
    padding-right: 64px;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    font-size: 13px;
    line-height: 1.55;
    color: var(--text-primary);
  }

  .copy-post {
    position: absolute;
    top: 6px;
    right: 6px;
  }

  .post-meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px 14px;
  }

  .visual {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 12px;
    color: var(--text-secondary);
  }

  .fixes,
  .warning,
  .reason {
    display: flex;
    align-items: flex-start;
    gap: 6px;
    margin: 0;
  }

  .fixes :global(svg),
  .warning :global(svg) {
    flex-shrink: 0;
    margin-top: 2px;
  }

  .warning {
    font-size: 12px;
    color: var(--status-warning);
  }
</style>
