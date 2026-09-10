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
    ChevronUp,
    Palette
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
  let selectedStylesMap = $state({});

  let allExpanded = $state(true);

  function isItemExpanded(id, idx) {
    if (expandedMap[id] !== undefined) return expandedMap[id];
    return allExpanded;
  }

  function toggleExpandAll() {
    allExpanded = !allExpanded;
    expandedMap = {};
  }

  function toggleExpand(id, idx) {
    const current = isItemExpanded(id, idx);
    expandedMap = { ...expandedMap, [id]: !current };
  }

  function handleSelect(sc) {
    userSelectedId = sc.id;
  }

  function ensureScenarioStyles(sc) {
    if (sc.styles && sc.styles.length >= 3) {
      return sc.styles;
    }
    const baseGenre = sc.genre || 'Cinematic Film';
    const shots = sc.shots || [];

    const style1Name = (sc.styles && sc.styles[0]?.name) || (baseGenre.includes('/') ? baseGenre.split('/')[0].trim() : baseGenre);
    const style1 = (sc.styles && sc.styles[0]) ? sc.styles[0] : {
      id: `${sc.id}_style_1`,
      name: style1Name || 'Signature Look',
      genre: baseGenre,
      description: `Original ${baseGenre} visual treatment.`,
      shots: shots,
      omniPrompt: sc.omniPrompt
    };

    const isPop = /pop|wes anderson|quirky|pastel|whimsical|fashion|comedy/i.test(baseGenre);
    const isRetro = /retro|vintage|analog|70s|80s|noir/i.test(baseGenre);
    const isCyber = /cyber|neon|matrix/i.test(baseGenre);

    let style2Name = 'Pastel Pop-Art';
    let style2Genre = 'Stylized Pop-Art / Symmetrical Commercial';
    let style2Desc = 'Playful symmetrical framing, vibrant pastel color blocking, and punchy witty energy.';
    let s2Cam = 'Snappy 90-degree whip-pan, dead-center symmetrical framing, rapid playful snap-in';
    let s2Light = 'Shadowless pastel mint and coral lighting with vivid retro saturation';

    if (isCyber) {
      style2Name = 'Solarpunk Daylight';
      style2Genre = 'Solarpunk / Architectural Daylight';
      style2Desc = 'Clean architectural daylight, lush greenery, and soft airy reflections.';
      s2Cam = 'Airy Steadicam tracking shot with soft natural flare';
      s2Light = 'Clean radiant daylight with soft atmospheric haze';
    } else if (isPop) {
      style2Name = 'High-Gloss Studio Ad';
      style2Genre = 'High-Gloss Studio Commercial / Editorial';
      style2Desc = 'Pristine white studio rim-lighting with soft diffused color fills and seamless rotational tracking.';
      s2Cam = 'Silky crane movement, seamless rotational studio tracking';
      s2Light = 'Pristine white studio rim-lighting with soft diffused color fills';
    }

    const style2 = (sc.styles && sc.styles[1]) ? sc.styles[1] : {
      id: `${sc.id}_style_2`,
      name: style2Name,
      genre: style2Genre,
      description: style2Desc,
      shots: shots.map(sh => ({
        ...sh,
        camera: s2Cam,
        lightingAtmosphere: s2Light
      })),
      omniPrompt: `Cinematic 9:16 ${style2Genre}. ` + shots.map(sh => `Shot ${sh.shotNumber} (${sh.timeRange}): ${sh.action}`).join(' ')
    };

    const style3Name = isRetro ? 'Monochrome Noir' : 'Warm 35mm Film';
    const style3Genre = isRetro ? 'Monochrome Film Noir / Arthouse' : 'Warm 35mm Analog / Kodak Cinema';
    const style3 = (sc.styles && sc.styles[2]) ? sc.styles[2] : {
      id: `${sc.id}_style_3`,
      name: style3Name,
      genre: style3Genre,
      description: isRetro 
        ? 'Dramatic black-and-white contrast, expressive chiaroscuro shadows, and bold silver-screen texture.'
        : 'Warm tungsten amber glow, tactile 35mm film grain, and soft golden-hour halation.',
      shots: shots.map(sh => ({
        ...sh,
        camera: `${sh.camera || 'Medium shot'}, vintage optical prime lens`,
        lightingAtmosphere: isRetro ? 'Chiaroscuro high-contrast black & white lighting' : 'Warm tungsten glow with subtle 35mm grain'
      })),
      omniPrompt: `Cinematic 9:16 ${style3Genre}. ` + shots.map(sh => `Shot ${sh.shotNumber} (${sh.timeRange}): ${sh.action}`).join(' ')
    };

    return [style1, style2, style3];
  }

  function getActiveStyle(sc) {
    const styles = ensureScenarioStyles(sc);
    const chosenId = selectedStylesMap[sc.id];
    return styles.find(s => s.id === chosenId) || styles[0];
  }

  function handleSelectStyle(scId, styleId) {
    selectedStylesMap = { ...selectedStylesMap, [scId]: styleId };
  }

  function getPromptValue(sc, activeStyle) {
    const key = `${sc.id}_${activeStyle.id}`;
    if (customPrompts[key] !== undefined) return customPrompts[key];
    return activeStyle.omniPrompt || sc.omniPrompt || '';
  }

  function handleConfirmRender(sc) {
    const activeStyle = getActiveStyle(sc);
    const finalPrompt = (getPromptValue(sc, activeStyle) || activeStyle.omniPrompt || sc.omniPrompt || '').trim();
    onSelect(`Please render video with scenario: ${sc.title} (${activeStyle.name} style). Creative direction: "${finalPrompt}"`);
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
    <div class="deck-header-actions">
      <button 
        class="expand-all-btn" 
        onclick={toggleExpandAll}
        title={allExpanded ? "Collapse 5-shot breakdowns" : "Show all 5 shots for all options"}
      >
        <Film size={13} />
        <span>{allExpanded ? "Collapse Shots" : "Show All 5 Shots"}</span>
      </button>
      <button 
        class="regenerate-btn" 
        onclick={handleRegenerateClick}
        title="Request 3 new imaginative scenario concepts"
      >
        <RefreshCw size={13} />
        <span>Regenerate (3 New Concepts)</span>
      </button>
    </div>
  </div>

  <p class="deck-intro">
    Choose one cinematic storyline and visual style (3 styles per scenario). All alternative concepts detail 5 progressive shots (2 seconds each).
  </p>

  <div class="scenario-cards-list">
    {#each scenarios as sc, idx (sc.id || idx)}
      {@const isSelected = selectedId === sc.id}
      {@const isExpanded = isItemExpanded(sc.id, idx)}
      {@const styles = ensureScenarioStyles(sc)}
      {@const activeStyle = getActiveStyle(sc)}
      {@const activeShots = (activeStyle.shots && activeStyle.shots.length > 0) ? activeStyle.shots : (sc.shots || [])}
      {@const promptKey = `${sc.id}_${activeStyle.id}`}
      {@const promptValue = getPromptValue(sc, activeStyle)}

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
            <span class="scenario-genre-badge">{activeStyle.name || activeStyle.genre || sc.genre}</span>
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

        <div class="style-tabs-container">
          <div class="style-tabs-label">
            <Palette size={12} />
            <span>Style Variations:</span>
          </div>
          <div class="style-tabs-list">
            {#each styles as st}
              {@const isStyleActive = activeStyle.id === st.id}
              <button
                type="button"
                class="style-tab-btn"
                class:active={isStyleActive}
                onclick={(e) => { e.stopPropagation(); handleSelectStyle(sc.id, st.id); }}
                title={st.description || st.name}
              >
                <span>{st.name}</span>
              </button>
            {/each}
          </div>
        </div>
        {#if activeStyle.description && activeStyle.description !== sc.concept}
          <p class="style-description">{activeStyle.description}</p>
        {/if}

        {#if isExpanded && activeShots && activeShots.length > 0}
          <div class="shots-timeline">
            <div class="shots-timeline-label">
              <Film size={13} />
              <span>Timeline Breakdown (5 Shots &times; 2s = 10s):</span>
            </div>
            <div class="shots-grid">
              {#each activeShots as shot}
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
              <span class="prompt-header-title">Omni Video Prompt ({activeStyle.name}):</span>
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
                bind:value={customPrompts[promptKey]}
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

  .deck-header-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .expand-all-btn,
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

  .expand-all-btn:hover,
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

  .style-tabs-container {
    margin: 10px 0 0 24px;
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .style-tabs-label {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    font-weight: 600;
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .style-tabs-list {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: var(--bg-surface);
    padding: 3px;
    border-radius: var(--radius-full);
    border: 1px solid var(--border-subtle);
  }

  .style-tab-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 10px;
    border-radius: var(--radius-full);
    border: none;
    background: transparent;
    color: var(--text-secondary);
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
    transition: var(--transition-normal);
    white-space: nowrap;
  }

  .style-tab-btn:hover {
    color: var(--text-primary);
    background: var(--bg-hover);
  }

  .style-tab-btn.active {
    background: var(--agent-video, #FBBC04);
    color: #111827;
    font-weight: 700;
    box-shadow: var(--shadow-sm);
  }

  .style-description {
    font-size: 11px;
    font-style: italic;
    color: var(--text-tertiary);
    margin: 4px 0 0 24px;
    line-height: 1.35;
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
    grid-template-columns: repeat(5, minmax(140px, 1fr));
    gap: 8px;
    overflow-x: auto;
    padding-bottom: 6px;
  }

  .shots-grid::-webkit-scrollbar {
    height: 4px;
  }

  .shots-grid::-webkit-scrollbar-thumb {
    background: var(--border-subtle);
    border-radius: var(--radius-full);
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
