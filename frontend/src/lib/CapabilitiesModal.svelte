<script>
  import {
    Sparkles,
    X,
    Search,
    CheckCircle2,
    Layers,
    Receipt,
    Video,
    Share2,
    Users,
    Calendar,
    Clock,
    Mail,
    MessageSquareQuote
  } from "@lucide/svelte";
  import { AGENT_CAPABILITIES_CATALOG } from "./constants.js";

  let {
    show = false,
    communityName = "GDG Krakow",
    onClose = () => {}
  } = $props();

  let searchQuery = $state("");

  const ICON_MAP = {
    layers: Layers,
    receipt: Receipt,
    video: Video,
    share: Share2,
    users: Users,
    calendar: Calendar,
    clock: Clock,
    mail: Mail
  };

  const filteredAgents = $derived(
    AGENT_CAPABILITIES_CATALOG.filter((agent) => {
      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase().trim();
      const inName = agent.name.toLowerCase().includes(q);
      const inTag = agent.tag.toLowerCase().includes(q);
      const inSummary = agent.summary.toLowerCase().includes(q);
      const inWhen = agent.whenToUse?.some((w) => w.toLowerCase().includes(q));
      const inPrompts = agent.starterPrompts?.some((p) =>
        p.toLowerCase().includes(q)
      );
      return inName || inTag || inSummary || inWhen || inPrompts;
    })
  );
</script>

{#if show}
  <div
    class="modal-backdrop"
    role="presentation"
    onclick={(e) => {
      if (e.target === e.currentTarget) onClose();
    }}
    onkeydown={(e) => {
      if (e.key === "Escape") onClose();
    }}
  >
    <div
      class="capabilities-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="capabilities-title"
    >
      <!-- Dialog Header -->
      <header class="dialog-header">
        <div class="header-main-group">
          <div class="header-badge-icon">
            <Sparkles size={18} class="sparkles-icon" />
          </div>
          <div>
            <h2 id="capabilities-title">Agent Capabilities & Prompt Guide</h2>
            <p class="header-subtitle">
              Overview of agents and how to phrase requests for {communityName}
            </p>
          </div>
        </div>
        <button
          class="btn-close-modal"
          onclick={onClose}
          aria-label="Close capabilities modal"
          title="Close (Esc)"
        >
          <X size={18} />
        </button>
      </header>

      <!-- Search Bar -->
      <div class="search-toolbar">
        <div class="search-input-wrapper">
          <Search size={15} class="search-icon" />
          <input
            type="text"
            placeholder="Search agents or tasks (e.g. receipts, video, linkedin, dates, rosters, keys)..."
            bind:value={searchQuery}
            class="search-input"
          />
          {#if searchQuery}
            <button
              class="btn-clear-search"
              onclick={() => (searchQuery = "")}
              aria-label="Clear search"
            >
              <X size={13} />
            </button>
          {/if}
        </div>
      </div>

      <!-- Agent Cards Grid -->
      <div class="dialog-body">
        {#if filteredAgents.length === 0}
          <div class="empty-results">
            <h3>No matching agents found</h3>
            <p>No agents matched "{searchQuery}". Try a different keyword.</p>
            <button class="btn-reset-filters" onclick={() => (searchQuery = "")}>
              Show All Agents
            </button>
          </div>
        {:else}
          <div class="agents-grid">
            {#each filteredAgents as agent (agent.id)}
              {@const IconComponent = ICON_MAP[agent.icon] || Layers}
              <article
                class="agent-card"
                style="--card-accent: {agent.accent}; --card-bg: {agent.bg};"
              >
                <!-- Card Header -->
                <div class="card-header">
                  <div
                    class="agent-avatar-box"
                    style="color: {agent.accent}; background: {agent.bg}; border-color: {agent.accent}40;"
                  >
                    <IconComponent size={20} strokeWidth={1.8} />
                  </div>
                  <div class="agent-name-group">
                    <div class="agent-title-row">
                      <h3>{agent.name}</h3>
                      <span class="agent-tag-badge">{agent.tag}</span>
                    </div>
                  </div>
                </div>

                <!-- Description -->
                <p class="agent-desc">{agent.summary}</p>

                <!-- When to Use -->
                <div class="card-block">
                  <span class="block-title">When to use:</span>
                  <ul class="bullet-list">
                    {#each agent.whenToUse as item}
                      <li>
                        <CheckCircle2 size={13} class="check-icon" style="color: {agent.accent};" />
                        <span>{item}</span>
                      </li>
                    {/each}
                  </ul>
                </div>

                <!-- Concrete Query Examples (Read-only reference) -->
                <div class="card-block prompts-block">
                  <div class="prompts-title-row">
                    <MessageSquareQuote size={13} style="color: {agent.accent};" />
                    <span class="block-title">Example requests:</span>
                  </div>
                  <div class="prompts-list">
                    {#each agent.starterPrompts as prompt}
                      <div class="prompt-example-card">
                        <span class="prompt-quote-mark">“</span>
                        <span class="prompt-text">{prompt}</span>
                        <span class="prompt-quote-mark">”</span>
                      </div>
                    {/each}
                  </div>
                </div>
              </article>
            {/each}
          </div>
        {/if}
      </div>

      <!-- Dialog Footer -->
      <footer class="dialog-footer">
        <span class="footer-note">
          Tip: You can also ask Main to coordinate multiple agents for complex workflows.
        </span>
        <button class="btn-done" onclick={onClose}>Close</button>
      </footer>
    </div>
  </div>
{/if}

<style>
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(8, 11, 17, 0.78);
    backdrop-filter: blur(8px);
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
    animation: modalFadeIn 0.18s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .capabilities-dialog {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-xl);
    width: 100%;
    max-width: 1100px;
    max-height: 88vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 24px 60px -12px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255, 255, 255, 0.05);
    overflow: hidden;
  }

  /* Header */
  .dialog-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 18px 24px;
    border-bottom: 1px solid var(--border-subtle);
    background: var(--bg-surface);
  }

  .header-main-group {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .header-badge-icon {
    width: 36px;
    height: 36px;
    border-radius: var(--radius-md);
    background: var(--primary-accent-container);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .header-badge-icon :global(.sparkles-icon) {
    color: var(--primary-accent);
  }

  .dialog-header h2 {
    font-size: 16px;
    font-weight: 700;
    color: var(--text-primary);
    margin: 0;
    letter-spacing: -0.01em;
  }

  .header-subtitle {
    font-size: 12.5px;
    color: var(--text-secondary);
    margin: 2px 0 0 0;
  }

  .btn-close-modal {
    background: transparent;
    border: none;
    color: var(--text-secondary);
    width: 32px;
    height: 32px;
    border-radius: var(--radius-sm);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: var(--transition-fast);
  }

  .btn-close-modal:hover {
    background: var(--bg-surface-variant);
    color: var(--text-primary);
  }

  /* Search Toolbar */
  .search-toolbar {
    padding: 12px 24px;
    background: var(--bg-surface-elevated);
    border-bottom: 1px solid var(--border-subtle);
  }

  .search-input-wrapper {
    position: relative;
    display: flex;
    align-items: center;
    width: 100%;
    max-width: 500px;
  }

  .search-input-wrapper :global(.search-icon) {
    position: absolute;
    left: 12px;
    color: var(--text-tertiary);
    pointer-events: none;
  }

  .search-input {
    width: 100%;
    background: var(--bg-app);
    border: 1px solid var(--border-subtle);
    color: var(--text-primary);
    padding: 8px 34px 8px 36px;
    border-radius: var(--radius-full);
    font-size: 13px;
    outline: none;
    transition: var(--transition-fast);
  }

  .search-input:focus {
    border-color: var(--primary-accent);
    box-shadow: 0 0 0 2px var(--primary-accent-container);
  }

  .btn-clear-search {
    position: absolute;
    right: 8px;
    background: transparent;
    border: none;
    color: var(--text-tertiary);
    cursor: pointer;
    padding: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
  }

  .btn-clear-search:hover {
    color: var(--text-primary);
    background: var(--bg-surface-variant);
  }

  /* Body & Grid */
  .dialog-body {
    padding: 24px;
    overflow-y: auto;
    flex: 1;
    background: var(--bg-app);
  }

  .agents-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 18px;
  }

  @media (max-width: 820px) {
    .agents-grid {
      grid-template-columns: 1fr;
    }
  }

  .agent-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    padding: 18px 20px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .card-header {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .agent-avatar-box {
    width: 38px;
    height: 38px;
    border-radius: var(--radius-md);
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid;
    flex-shrink: 0;
  }

  .agent-name-group {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .agent-title-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .agent-title-row h3 {
    font-size: 15px;
    font-weight: 700;
    color: var(--text-primary);
    margin: 0;
  }

  .agent-tag-badge {
    font-size: 11px;
    font-weight: 500;
    color: var(--text-secondary);
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    padding: 1px 8px;
    border-radius: var(--radius-full);
  }

  .agent-desc {
    font-size: 12.5px;
    color: var(--text-secondary);
    line-height: 1.5;
    margin: 0;
  }

  .card-block {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .block-title {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-tertiary);
  }

  .bullet-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 5px;
  }

  .bullet-list li {
    display: flex;
    align-items: flex-start;
    gap: 7px;
    font-size: 12px;
    color: var(--text-primary);
    line-height: 1.4;
  }

  .bullet-list li :global(.check-icon) {
    flex-shrink: 0;
    margin-top: 2px;
  }

  .prompts-block {
    margin-top: 4px;
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: 10px 12px;
  }

  .prompts-title-row {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 2px;
  }

  .prompts-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .prompt-example-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    color: var(--text-primary);
    padding: 7px 10px;
    border-radius: var(--radius-sm);
    font-size: 11.5px;
    line-height: 1.4;
    user-select: text;
  }

  .prompt-quote-mark {
    color: var(--text-tertiary);
    font-weight: 700;
  }

  .prompt-text {
    color: var(--text-secondary);
  }

  /* Empty State */
  .empty-results {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px 20px;
    text-align: center;
    gap: 10px;
  }

  .empty-results h3 {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
  }

  .empty-results p {
    font-size: 12.5px;
    color: var(--text-secondary);
    margin: 0;
  }

  .btn-reset-filters {
    margin-top: 8px;
    background: var(--primary-accent);
    color: #ffffff;
    border: none;
    padding: 6px 14px;
    border-radius: var(--radius-full);
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
  }

  /* Footer */
  .dialog-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 24px;
    border-top: 1px solid var(--border-subtle);
    background: var(--bg-surface-elevated);
  }

  .footer-note {
    font-size: 11.5px;
    color: var(--text-tertiary);
  }

  .btn-done {
    background: var(--primary-accent);
    color: #ffffff;
    border: none;
    padding: 6px 18px;
    border-radius: var(--radius-full);
    font-size: 12.5px;
    font-weight: 600;
    cursor: pointer;
    transition: var(--transition-fast);
  }

  .btn-done:hover {
    filter: brightness(1.1);
  }

  @keyframes modalFadeIn {
    from {
      opacity: 0;
      transform: scale(0.985);
    }
    to {
      opacity: 1;
      transform: scale(1);
    }
  }
</style>
