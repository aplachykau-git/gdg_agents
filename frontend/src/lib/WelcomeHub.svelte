<script>
  // Welcome screen: agent catalog shown before a session is started.
  import { ArrowRight } from '@lucide/svelte';

  let { agents = [], onStart = () => {} } = $props();
</script>

<div class="hub-welcome-view">
  <div class="hub-container">
    <div class="hub-header">
      <p class="hub-subtitle">
        Select an agent to begin, or use the <strong>Main</strong> agent to automatically coordinate tasks.
      </p>
    </div>

    <!-- Quick 3-Step Guide -->
    <div class="workflow-steps-strip">
      <div class="step-badge">
        <span class="step-num">1</span>
        <span>Select agent or attach docs</span>
      </div>
      <div class="step-separator"></div>
      <div class="step-badge">
        <span class="step-num">2</span>
        <span>Run prompt (Ctrl+Enter)</span>
      </div>
      <div class="step-separator"></div>
      <div class="step-badge">
        <span class="step-num">3</span>
        <span>Inspect tool calls & copy outputs</span>
      </div>
    </div>

    <!-- Agents Catalog Grid -->
    <div class="agents-catalog-grid">
      {#each agents as agent}
        {@const AgentIcon = agent.icon}
        <button
          class="agent-catalog-card"
          style="--card-accent: {agent.accent}; --card-bg: {agent.bg};"
          onclick={() => {
            onStart(agent.id);
          }}
        >
          <div class="agent-card-header">
            <div class="agent-icon-box">
              <AgentIcon size={18} strokeWidth={1.75} />
            </div>
            <div class="agent-title-col">
              <strong>{agent.name}</strong>
              <span class="agent-type-tag">{agent.tag}</span>
            </div>
          </div>
          <p class="agent-card-desc">
            {agent.desc}
          </p>
          <div class="card-footer-action">
            <span>{agent.actionText}</span>
            <ArrowRight size={14} />
          </div>
        </button>
      {/each}
    </div>
  </div>
</div>

<style>
  .hub-welcome-view {
    flex: 1;
    overflow-y: auto;
    padding: 32px;
    display: flex;
    flex-direction: column;
    align-items: center;
    max-width: 1060px;
    margin: 0 auto;
    width: 100%;
  }

  .hub-container {
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    margin: auto 0;
  }

  .hub-header {
    text-align: center;
    margin-bottom: 24px;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .hub-subtitle {
    font-size: 13.5px;
    color: var(--text-secondary);
    max-width: 560px;
    line-height: 1.5;
    margin: 0;
  }

  .hub-subtitle strong {
    color: var(--text-primary);
  }

  .workflow-steps-strip {
    display: flex;
    align-items: center;
    gap: 12px;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    padding: 6px 16px;
    border-radius: var(--radius-full);
    margin-bottom: 24px;
  }

  .step-badge {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--text-secondary);
  }

  .step-num {
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-medium);
    color: var(--text-primary);
    font-size: 10.5px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .step-separator {
    width: 16px;
    height: 1px;
    background: var(--border-subtle);
  }

  .agents-catalog-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 16px;
    width: 100%;
  }

  .agent-catalog-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    padding: 18px;
    display: flex;
    flex-direction: column;
    text-align: left;
    cursor: pointer;
    transition: var(--transition-normal);
    color: inherit;
    position: relative;
  }

  .agent-catalog-card:hover {
    background: var(--bg-surface-elevated);
    border-color: var(--card-accent, var(--primary-accent));
    transform: translateY(-3px);
    box-shadow: 0 8px 24px -4px rgba(0, 0, 0, 0.35), var(--shadow-md);
  }

  .agent-card-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
  }

  .agent-icon-box {
    width: 36px;
    height: 36px;
    border-radius: var(--radius-md);
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--card-accent, var(--text-primary));
    flex-shrink: 0;
    transition: var(--transition-fast);
  }

  .agent-catalog-card:hover .agent-icon-box {
    border-color: var(--card-accent, var(--border-subtle));
    box-shadow: 0 0 12px var(--card-bg, transparent);
  }

  .agent-title-col {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .agent-title-col strong {
    font-size: 14px;
    font-weight: 700;
    color: var(--text-primary);
    line-height: 1.2;
  }

  .agent-type-tag {
    font-size: 10.5px;
    font-weight: 500;
    color: var(--text-tertiary);
    letter-spacing: 0.02em;
  }

  .agent-card-desc {
    font-size: 12.5px;
    color: var(--text-secondary);
    line-height: 1.55;
    margin-bottom: 18px;
    flex: 1;
  }

  .card-footer-action {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 11.5px;
    font-weight: 500;
    color: var(--text-secondary);
    border-top: 1px solid var(--border-subtle);
    padding-top: 12px;
    transition: var(--transition-fast);
  }

  .agent-catalog-card:hover .card-footer-action {
    color: var(--text-primary);
    border-color: var(--border-medium);
  }

  .agent-catalog-card:hover .card-footer-action :global(svg) {
    transform: translateX(3px);
    transition: transform 0.2s ease;
    color: var(--text-primary);
  }

</style>
