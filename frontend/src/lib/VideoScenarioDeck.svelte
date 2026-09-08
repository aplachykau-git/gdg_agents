<script>
  import { 
    Video, 
    Film, 
    Sparkles, 
    RefreshCw, 
    Check, 
    Edit3, 
    Play, 
    Sliders,
    ChevronDown,
    ChevronUp
  } from '@lucide/svelte';

  let { 
    scenarios = [], 
    onSelect = () => {}, 
    onRegenerate = () => {} 
  } = $props();

  let userSelectedId = $state(null);
  let selectedId = $derived(userSelectedId ?? scenarios[0]?.id ?? '');
  let expandedMap = $state({});
  let customPrompts = $state({});
  let isEditing = $state(false);

  function isItemExpanded(id, idx) {
    if (expandedMap[id] !== undefined) return expandedMap[id];
    return idx === 0;
  }

  function toggleExpand(id, idx) {
    const current = isItemExpanded(id, idx);
    expandedMap = { ...expandedMap, [id]: !current };
  }

  function handleSelect(sc) {
    userSelectedId = sc.id;
  }

  function handleConfirmRender(sc) {
    const finalPrompt = (customPrompts[sc.id] ?? sc.omniPrompt).trim();
    onSelect(`Please render video with scenario: ${sc.title}. Creative direction: "${finalPrompt}"`);
  }

  function handleRegenerateClick() {
    onRegenerate("Please invent 3 new creative scenarios for this talk.");
  }
</script>

<div class="scenarios-deck-container">
  <div class="deck-header">
    <div class="deck-title-row">
      <Video size={18} class="accent-icon" />
      <span class="deck-title">Creative Video Concepts (5 Shots &times; 2s)</span>
    </div>
    <button 
      class="regenerate-btn" 
      onclick={handleRegenerateClick}
      title="Request new imaginative scenario concepts"
    >
      <RefreshCw size={13} />
      <span>New Scenarios</span>
    </button>
  </div>

  <p class="deck-intro">
    Choose one cinematic scenario to proceed. The character from your photo will star as the protagonist in this visual story.
  </p>

  <div class="scenario-cards-list">
    {#each scenarios as sc, idx (sc.id || idx)}
      {@const isSelected = selectedId === sc.id}
      {@const isExpanded = isItemExpanded(sc.id, idx)}
      {@const promptValue = customPrompts[sc.id] ?? sc.omniPrompt}

      <div class="scenario-card" class:selected={isSelected}>
        <div 
          class="card-top-bar" 
          role="button"
          tabindex="0"
          onclick={() => handleSelect(sc)}
          onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleSelect(sc); } }}
        >
          <div class="title-group">
            <div class="radio-indicator">
              {#if isSelected}
                <div class="radio-dot"></div>
              {/if}
            </div>
            <span class="scenario-number">Option {sc.number || idx + 1}</span>
            <span class="scenario-title">{sc.title}</span>
            <span class="scenario-genre-badge">{sc.genre}</span>
          </div>

          <button 
            type="button" 
            class="expand-toggle-btn" 
            onclick={(e) => { e.stopPropagation(); toggleExpand(sc.id); }}
            title={isExpanded ? "Collapse shots" : "Expand 5 shots"}
          >
            {#if isExpanded}
              <ChevronUp size={16} />
            {:else}
              <ChevronDown size={16} />
            {/if}
          </button>
        </div>

        <p class="scenario-concept">{sc.concept}</p>

        {#if isExpanded && sc.shots && sc.shots.length > 0}
          <div class="shots-timeline">
            <div class="shots-timeline-label">
              <Film size={13} />
              <span>Timeline Breakdown (10s total):</span>
            </div>
            <div class="shots-grid">
              {#each sc.shots as shot}
                <div class="shot-chip">
                  <div class="shot-chip-header">
                    <span class="shot-badge">Shot {shot.shotNumber}</span>
                    <span class="shot-time">{shot.timeRange}</span>
                  </div>
                  <div class="shot-action">{shot.action}</div>
                  {#if shot.camera}
                    <div class="shot-camera">{shot.camera}</div>
                  {/if}
                </div>
              {/each}
            </div>
          </div>
        {/if}

        {#if isSelected}
          <div class="scenario-action-panel">
            <div class="prompt-preview-header">
              <span class="prompt-header-title">Omni Video Prompt:</span>
              <button 
                class="edit-toggle-btn" 
                onclick={() => isEditing = !isEditing}
              >
                <Edit3 size={12} />
                <span>{isEditing ? 'Done Editing' : 'Customize Prompt'}</span>
              </button>
            </div>

            {#if isEditing}
              <textarea 
                class="prompt-textarea"
                rows="3"
                bind:value={customPrompts[sc.id]}
                placeholder="Modify shot descriptions or camera movements..."
              >{promptValue}</textarea>
            {:else}
              <div class="prompt-box">
                {promptValue}
              </div>
            {/if}

            <div class="action-buttons-row">
              <button 
                class="render-scenario-btn primary"
                onclick={() => handleConfirmRender(sc)}
              >
                <Play size={14} />
                <span>Render Video with this Scenario</span>
              </button>
            </div>
          </div>
        {:else}
          <div class="select-scenario-bar">
            <button class="select-btn" onclick={() => handleSelect(sc)}>
              <span>Select Option {sc.number || idx + 1}</span>
            </button>
          </div>
        {/if}
      </div>
    {/each}
  </div>
</div>

<style>
  .scenarios-deck-container {
    display: flex;
    flex-direction: column;
    gap: 14px;
    margin-top: 12px;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    padding: 16px 18px;
    box-shadow: var(--shadow-sm);
  }

  .deck-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--border-subtle);
  }

  .deck-title-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  :global(.deck-title-row .accent-icon) {
    color: var(--agent-video, #FBBC04);
  }

  .deck-title {
    font-size: 14px;
    font-weight: 700;
    letter-spacing: -0.01em;
    color: var(--text-primary);
  }

  .regenerate-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-full);
    padding: 4px 10px;
    cursor: pointer;
    transition: var(--transition-normal);
  }

  .regenerate-btn:hover {
    color: var(--text-primary);
    border-color: var(--border-focus);
    background: var(--bg-hover);
  }

  .deck-intro {
    font-size: 12px;
    color: var(--text-secondary);
    line-height: 1.4;
    margin: 0;
  }

  .scenario-cards-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .scenario-card {
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: 12px 14px;
    transition: var(--transition-normal);
  }

  .scenario-card:hover {
    border-color: var(--border-focus);
  }

  .scenario-card.selected {
    border-color: var(--agent-video, #FBBC04);
    box-shadow: 0 0 0 1px var(--agent-video, #FBBC04);
  }

  .card-top-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    cursor: pointer;
    user-select: none;
  }

  .title-group {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .radio-indicator {
    width: 16px;
    height: 16px;
    border-radius: 50%;
    border: 2px solid var(--border-focus);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .selected .radio-indicator {
    border-color: var(--agent-video, #FBBC04);
  }

  .radio-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--agent-video, #FBBC04);
  }

  .scenario-number {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    color: var(--text-tertiary);
  }

  .scenario-title {
    font-size: 13px;
    font-weight: 700;
    color: var(--text-primary);
  }

  .scenario-genre-badge {
    font-size: 11px;
    font-weight: 600;
    background: rgba(251, 188, 4, 0.15);
    color: var(--agent-video, #FBBC04);
    padding: 2px 7px;
    border-radius: var(--radius-full);
  }

  .expand-toggle-btn {
    background: transparent;
    border: none;
    color: var(--text-tertiary);
    cursor: pointer;
    padding: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .expand-toggle-btn:hover {
    color: var(--text-primary);
  }

  .scenario-concept {
    font-size: 12px;
    color: var(--text-secondary);
    margin: 8px 0 0 24px;
    line-height: 1.4;
  }

  .shots-timeline {
    margin: 12px 0 6px 24px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .shots-timeline-label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    font-weight: 600;
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .shots-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: 8px;
  }

  .shot-chip {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 8px 10px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .shot-chip-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .shot-badge {
    font-size: 10px;
    font-weight: 700;
    color: var(--agent-video, #FBBC04);
  }

  .shot-time {
    font-size: 10px;
    font-family: monospace;
    color: var(--text-tertiary);
  }

  .shot-action {
    font-size: 11px;
    color: var(--text-primary);
    line-height: 1.3;
  }

  .shot-camera {
    font-size: 10px;
    color: var(--text-tertiary);
    font-style: italic;
  }

  .scenario-action-panel {
    margin: 12px 0 0 24px;
    padding-top: 10px;
    border-top: 1px solid var(--border-subtle);
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .prompt-preview-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .prompt-header-title {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-tertiary);
    text-transform: uppercase;
  }

  .edit-toggle-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: transparent;
    border: none;
    color: var(--text-secondary);
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
  }

  .edit-toggle-btn:hover {
    color: var(--text-primary);
  }

  .prompt-box {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 8px 10px;
    font-size: 11px;
    color: var(--text-secondary);
    line-height: 1.4;
    font-family: monospace;
    max-height: 80px;
    overflow-y: auto;
  }

  .prompt-textarea {
    width: 100%;
    background: var(--bg-surface);
    border: 1px solid var(--border-focus);
    border-radius: var(--radius-sm);
    padding: 8px 10px;
    font-size: 11px;
    color: var(--text-primary);
    font-family: monospace;
    line-height: 1.4;
    resize: vertical;
    outline: none;
  }

  .action-buttons-row {
    display: flex;
    justify-content: flex-end;
    margin-top: 4px;
  }

  .render-scenario-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    font-weight: 700;
    padding: 7px 14px;
    border-radius: var(--radius-md);
    border: none;
    background: var(--agent-video, #FBBC04);
    color: #111827;
    cursor: pointer;
    transition: var(--transition-normal);
  }

  .render-scenario-btn:hover {
    filter: brightness(1.1);
    box-shadow: var(--shadow-sm);
  }

  .select-scenario-bar {
    margin: 8px 0 0 24px;
    display: flex;
    justify-content: flex-end;
  }

  .select-btn {
    background: transparent;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-full);
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
    color: var(--text-secondary);
    cursor: pointer;
  }

  .select-btn:hover {
    border-color: var(--border-focus);
    color: var(--text-primary);
  }
</style>
