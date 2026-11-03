<script>
  import {
    Video,
    Film,
    RefreshCw,
    Check,
    Edit3,
    Play,
    ChevronDown,
    ChevronUp,
    ChevronLeft,
    ChevronRight,
    RotateCcw,
    Palette,
    Lightbulb,
    Loader2,
    Lock,
  } from '@lucide/svelte';

  let { 
    scenarios = [], 
    isLocked = false,
    isBusy = false,
    onSelect = () => {}, 
    onRegenerate = () => {} 
  } = $props();

  let userSelectedId = $state(null);
  // Buttons are disabled while the agent is working; the deck stays usable afterwards
  // so the user can render another option for the same speaker.
  const isSubmitting = $derived(isBusy);
  let selectedId = $derived(userSelectedId ?? scenarios[0]?.id ?? '');
  let expandedMap = $state({});
  let customPrompts = $state({});
  let isEditing = $state(false);
  let selectedStylesMap = $state({});
  let reorderedShotsMap = $state({});
  let reorderedSyncedMap = $state({});

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
    if (isLocked || isSubmitting) return;
    userSelectedId = sc.id;
  }

  function ensureScenarioStyles(sc, idx = 0) {
    const num = sc.number || (idx + 1) || parseInt((sc.id || '').replace(/\D/g, '') || '1', 10);
    if (sc.styles && sc.styles.length >= 3) {
      const names = sc.styles.map(s => s.name || '');
      const genres = sc.styles.map(s => s.genre || '');
      const hasGenericLabels = names.every(n => /^Style\s*\d*$/i.test(n.trim()) || n.trim() === 'Style');
      const hasSameGenre = new Set(genres).size === 1 && genres[0] === sc.genre;
      const hasRepeatedGeneric = num > 1 && names.some(n =>
        /clean modern|studio commercial|cinematic 35mm|dynamic cinematic/i.test(n)
      );
      const isGeneric = hasGenericLabels || hasSameGenre || hasRepeatedGeneric;
      if (!isGeneric) {
        return sc.styles;
      }
    }
    const baseGenre = sc.genre || 'Cinematic Film';
    const shots = sc.shots || [];

    const style1Name = (sc.styles && sc.styles[0]?.name && !/^Style\s*\d*$/i.test(sc.styles[0].name)) 
      ? sc.styles[0].name 
      : (baseGenre.includes('/') ? baseGenre.split('/')[0].trim() : baseGenre);
    const style1 = (sc.styles && sc.styles[0]) ? { ...sc.styles[0], name: style1Name } : {
      id: `${sc.id}_style_1`,
      name: style1Name || 'Signature Look',
      genre: baseGenre,
      description: `Original ${baseGenre} visual treatment.`,
      shots: shots,
      omniPrompt: sc.omniPrompt
    };

    // Category A: Clean Modern Tech / Studio Commercial (Grounded Realism)
    const groundedPresets = [
      {
        name: 'Clean Modern Tech',
        genre: 'Clean Modern Tech / Studio Commercial',
        description: 'Sleek, grounded commercial aesthetic with crisp soft lighting, natural skin tones, and professional tech presence.',
        cam: 'Smooth horizontal Steadicam glide, crisp prime lens focus, balanced centered framing',
        light: 'Clean soft-diffused studio key light, subtle rim reflections, authentic natural tones'
      },
      {
        name: 'Architectural Daylight',
        genre: 'Architectural Daylight / Modern Editorial',
        description: 'Abundant natural daylight, soft airy ambient bounce, and elegant wide architectural framing.',
        cam: 'Expansive slow push-in, wide architectural glass reflections, elegant depth of field',
        light: 'Abundant natural daylight, soft airy ambient bounce, crisp modern aesthetic'
      },
      {
        name: 'Minimalist Keynote',
        genre: 'Minimalist Studio / Keynote Elegance',
        description: 'High-end keynote rim lighting, clean dark gradient backdrop, and sharp eye-level focus.',
        cam: 'Subtle cinematic slow zoom, sharp eye-level prime focus, clean editorial framing',
        light: 'High-end keynote rim lighting, clean dark gradient backdrop, crisp professional skin tones'
      },
      {
        name: 'Warm Artisanal Studio',
        genre: 'Warm Artisanal Studio / Tactile Craft',
        description: 'Warm amber lamplight, soft window bounce, natural wood and textured linen accents.',
        cam: 'Smooth handheld prime lens, gentle natural breathing, intimate framing',
        light: 'Warm amber lamplight, soft window bounce, natural wood and textured linen accents'
      },
      {
        name: 'Precision Macro Lab',
        genre: 'Precision Macro Lab / Modern Cleanroom',
        description: 'Pristine cool-white daylight bounce, delicate rim reflections, ultra-clean modern precision.',
        cam: 'Crisp horizontal slider glide, high-index prime focus, subtle glass reflections',
        light: 'Pristine cool-white daylight bounce, delicate rim reflections, ultra-clean modern precision'
      }
    ];

    // Category B: Dynamic Cinematic Realism / Contrasting Movement
    const cinematicPresets = [
      {
        name: 'Cinematic 35mm Realism',
        genre: 'Cinematic 35mm Documentary / Kodak Film',
        description: 'Warm natural ambient lighting with gentle film halation, organic camera breathing, and authentic documentary depth.',
        cam: 'Tactile handheld camera, organic breathing, subtle shallow depth of field',
        light: 'Warm natural ambient lighting with gentle film halation and subtle organic grain'
      },
      {
        name: 'High-Velocity Kinetic',
        genre: 'High-Velocity Kinetic / Dynamic Energy',
        description: 'Punchy high-contrast specular lighting, rapid kinetic tracking, and visceral motion dynamics.',
        cam: 'Rapid kinetic tracking, visceral low-angle whip-pan, sharp motion-tracking arc',
        light: 'Punchy high-contrast specular lighting, deep shadows, dynamic rim highlights'
      },
      {
        name: 'Atmospheric Neo-Noir',
        genre: 'Atmospheric Neo-Noir / Chiaroscuro',
        description: 'Chiaroscuro moody shadows with sharp directional rim light and deep cinematic contrast.',
        cam: 'Dutch angle slow tilt, anamorphic horizontal flare, reflective dark ground tracking',
        light: 'Chiaroscuro moody shadows punctuated by electric cyan and amber rim accents'
      },
      {
        name: 'Prismatic Technicolor',
        genre: 'Prismatic Technicolor / Saturated Spectrum',
        description: 'Iridescent rainbow caustics, saturated primary tones, and luminous optical bloom.',
        cam: 'Floating anamorphic lens flares, dynamic slow push-in, rich depth',
        light: 'Iridescent rainbow caustics, saturated primary tones, and luminous optical bloom'
      },
      {
        name: 'Industrial Chiaroscuro',
        genre: 'Heavy Industrial / Raw Chiaroscuro',
        description: 'High-contrast tungsten furnace glow, deep matte shadows, and dramatic rim highlights.',
        cam: 'Low-angle textured tilt, visceral slow-motion pan, gritty industrial framing',
        light: 'High-contrast tungsten furnace glow, deep matte shadows, and dramatic rim highlights'
      }
    ];

    const p2 = groundedPresets[(num - 1) % groundedPresets.length];
    const p3 = cinematicPresets[(num - 1) % cinematicPresets.length];

    const style2 = {
      id: `${sc.id}_style_2`,
      name: p2.name,
      genre: p2.genre,
      description: p2.description,
      shots: shots.map(sh => ({
        ...sh,
        camera: p2.cam,
        lightingAtmosphere: p2.light
      })),
      omniPrompt: `Cinematic 9:16 ${p2.genre}. ` + shots.map(sh => `Shot ${sh.shotNumber} (${sh.timeRange}): ${sh.action}`).join(' ')
    };

    const style3 = {
      id: `${sc.id}_style_3`,
      name: p3.name,
      genre: p3.genre,
      description: p3.description,
      shots: shots.map(sh => ({
        ...sh,
        camera: p3.cam,
        lightingAtmosphere: p3.light
      })),
      omniPrompt: `Cinematic 9:16 ${p3.genre}. ` + shots.map(sh => `Shot ${sh.shotNumber} (${sh.timeRange}): ${sh.action}`).join(' ')
    };

    return [style1, style2, style3];
  }

  function getActiveStyle(sc, idx = 0) {
    const styles = ensureScenarioStyles(sc, idx);
    const chosenId = selectedStylesMap[sc.id];
    return styles.find(s => s.id === chosenId) || styles[0];
  }

  function handleSelectStyle(scId, styleId) {
    if (isLocked || isSubmitting) return;
    selectedStylesMap = { ...selectedStylesMap, [scId]: styleId };
  }

  function getPromptValue(sc, activeStyle) {
    const key = `${sc.id}_${activeStyle.id}`;
    if (customPrompts[key] !== undefined) return customPrompts[key];
    return activeStyle.omniPrompt || sc.omniPrompt || '';
  }

  function getActiveShots(sc, activeStyle) {
    const key = `${sc.id}_${activeStyle.id}`;
    if (reorderedShotsMap[key]) return reorderedShotsMap[key];
    return (activeStyle.shots && activeStyle.shots.length > 0) ? activeStyle.shots : (sc.shots || []);
  }

  function moveShot(sc, activeStyle, shotIdx, direction) {
    if (isLocked || isSubmitting) return;
    const key = `${sc.id}_${activeStyle.id}`;
    const shotsList = [...getActiveShots(sc, activeStyle)];
    const targetIdx = shotIdx + direction;
    if (targetIdx < 0 || targetIdx >= shotsList.length) return;

    const temp = shotsList[shotIdx];
    shotsList[shotIdx] = shotsList[targetIdx];
    shotsList[targetIdx] = temp;

    const reindexed = shotsList.map((sh, idx) => {
      const start = idx * 2;
      const end = (idx + 1) * 2;
      const timeRange = `00:0${start} - 00:${end < 10 ? '0' + end : end}`;
      return {
        ...sh,
        shotNumber: idx + 1,
        timeRange
      };
    });

    reorderedShotsMap = { ...reorderedShotsMap, [key]: reindexed };

    // Dynamically rebuild and update the omni text prompt to match the new shot sequence
    const baseGenre = activeStyle.genre || sc.genre || 'Cinematic Film';
    const updatedPrompt = `Cinematic 9:16 ${baseGenre}. ` + 
      reindexed.map(sh => `Shot ${sh.shotNumber} (${sh.timeRange}): ${sh.action}${sh.camera ? ' (' + sh.camera + ')' : ''}`).join(' ');

    customPrompts = { ...customPrompts, [key]: updatedPrompt };
    reorderedSyncedMap = { ...reorderedSyncedMap, [key]: true };
  }

  function resetShotsOrder(sc, activeStyle) {
    if (isLocked || isSubmitting) return;
    const key = `${sc.id}_${activeStyle.id}`;
    const updatedShots = { ...reorderedShotsMap };
    delete updatedShots[key];
    reorderedShotsMap = updatedShots;

    const updatedPrompts = { ...customPrompts };
    delete updatedPrompts[key];
    customPrompts = updatedPrompts;

    const updatedSynced = { ...reorderedSyncedMap };
    delete updatedSynced[key];
    reorderedSyncedMap = updatedSynced;
  }

  function handleConfirmRender(sc, idx = 0) {
    if (isLocked || isSubmitting) return;
    const activeStyle = getActiveStyle(sc, idx);
    const key = `${sc.id}_${activeStyle.id}`;
    const defaultPrompt = (activeStyle.omniPrompt || sc.omniPrompt || '').trim();
    const finalPrompt = (getPromptValue(sc, activeStyle) || defaultPrompt).trim();
    // Styles synthesised in the browser are unknown to the backend, so their prompt must travel along.
    const styleKnown = (scenarios[idx]?.styles || []).some(st => st.id === activeStyle.id && st.omniPrompt);
    const edited = (customPrompts[key] !== undefined && finalPrompt !== defaultPrompt) || !styleKnown;
    const number = sc.number || idx + 1;
    let message = `Render option ${number}: ${sc.title} (${activeStyle.name} style).`;
    if (edited) {
      message += `\nEdited storyboard: "${finalPrompt}"`;
    }
    onSelect(message, {
      video_editor_ui_selection: {
        scenario_id: sc.id,
        style_id: styleKnown ? activeStyle.id : null,
        prompt: finalPrompt,
        edited,
      },
    });
  }

  function handleRegenerateClick() {
    if (isLocked || isSubmitting) return;
    onRegenerate("Please propose 5 new scenarios for the same speaker.");
  }

  function formatCompactTime(timeRange, sIdx) {
    if (!timeRange) return `${sIdx * 2}–${(sIdx + 1) * 2}s`;
    const m = timeRange.match(/00:0?(\d+)\s*-\s*00:0?(\d+)/);
    if (m) {
      return `${parseInt(m[1], 10)}–${parseInt(m[2], 10)}s`;
    }
    return timeRange.replace(/\s*-\s*/g, '–');
  }

  function cleanShotText(text) {
    if (!text) return '';
    return text.replace(/\s*\*\([^)]+\)\*\s*$/g, '').trim();
  }

  function getConceptText(sc) {
    const raw = (sc.concept || '').trim();
    if (raw && !/^A high-concept visual story/i.test(raw)) {
      return raw;
    }
    const shots = sc.shots || [];
    if (shots.length >= 3) {
      return `${shots[0].action} The narrative escalates into ${shots[shots.length - 2].action.toLowerCase()}`;
    }
    if (shots.length > 0) {
      return shots[0].action;
    }
    return '';
  }
</script>

<div class="scenarios-deck-container" class:locked-deck={isLocked}>
  <div class="deck-header">
    <div class="deck-title-row">
      <Video size={16} class="accent-icon" />
      <span class="deck-title">Video Concepts (10s)</span>
      {#if isLocked}
        <span class="deck-status-pill locked">
          <Lock size={11} />
          <span>Locked</span>
        </span>
      {/if}
    </div>
    <div class="deck-header-actions">
      <button 
        class="expand-all-btn" 
        onclick={toggleExpandAll}
        title={allExpanded ? "Collapse shots" : "Show all shots"}
      >
        <Film size={12} />
        <span>{allExpanded ? "Collapse" : "Shots"}</span>
      </button>
      {#if !isLocked}
        <button 
          class="regenerate-btn" 
          disabled={isSubmitting}
          onclick={handleRegenerateClick}
          title="Generate 5 new concepts"
        >
          <RefreshCw size={12} />
          <span>New</span>
        </button>
      {/if}
    </div>
  </div>

  <div class="scenario-cards-list">
    {#each scenarios as sc, idx (sc.id || idx)}
      {@const isSelected = selectedId === sc.id}
      {@const isExpanded = isItemExpanded(sc.id, idx)}
      {@const styles = ensureScenarioStyles(sc, idx)}
      {@const activeStyle = getActiveStyle(sc, idx)}
      {@const activeShots = getActiveShots(sc, activeStyle)}
      {@const promptKey = `${sc.id}_${activeStyle.id}`}
      {@const promptValue = getPromptValue(sc, activeStyle)}
      {@const conceptText = getConceptText(sc)}

      <div 
        class="scenario-card" 
        class:selected={isSelected}
        class:locked-selected={isLocked && isSelected}
        class:locked-unselected={isLocked && !isSelected}
      >
        <div 
          class="card-top-bar" 
          role="button"
          tabindex={isLocked ? -1 : 0}
          onclick={() => handleSelect(sc)}
          onkeydown={(e) => { if (!isLocked && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); handleSelect(sc); } }}
        >
          <div class="title-group">
            <div class="radio-indicator">
              {#if isSelected}
                <div class="radio-dot"></div>
              {/if}
            </div>
            <span class="scenario-number">#{sc.number || idx + 1}</span>
            <span class="scenario-title">{sc.title}</span>
            <span class="scenario-genre-badge">{activeStyle.name || activeStyle.genre || sc.genre}</span>
            {#if isLocked && isSelected}
              <span class="selected-for-render-tag">
                <Check size={11} />
                <span>Selected for Render</span>
              </span>
            {/if}
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

        {#if conceptText}
          <div class="scenario-concept-box">
            <span class="concept-label">Plot:</span>
            <span class="concept-text">{conceptText}</span>
          </div>
        {/if}

        {#if sc.narrativeMetaphor || sc.narrative_metaphor}
          <div class="metaphor-bridge">
            <Lightbulb size={11} class="metaphor-icon" />
            <span class="metaphor-label">Metaphor:</span>
            <span class="metaphor-text">{sc.narrativeMetaphor || sc.narrative_metaphor}</span>
          </div>
        {/if}

        <div class="style-tabs-container">
          <Palette size={11} class="style-icon" />
          <div class="style-tabs-list">
            {#each styles as st}
              {@const isStyleActive = activeStyle.id === st.id}
              <button
                type="button"
                class="style-tab-btn"
                class:active={isStyleActive}
                disabled={isLocked || isSubmitting}
                onclick={(e) => { e.stopPropagation(); handleSelectStyle(sc.id, st.id); }}
                title={st.description || st.name}
              >
                <span>{st.name}</span>
              </button>
            {/each}
          </div>
        </div>

        {#if isExpanded && activeShots && activeShots.length > 0}
          <div class="shots-timeline">
            <div class="shots-timeline-header-row">
              <div class="shots-timeline-label">
                <Film size={12} />
                <span>Timeline (10s)</span>
              </div>
              <div class="shots-timeline-actions">
                {#if reorderedSyncedMap[promptKey] && !isLocked}
                  <span class="synced-badge" title="Omni prompt updated">
                    <Check size={11} />
                    <span>Synced</span>
                  </span>
                  <button 
                    type="button"
                    class="reset-order-btn"
                    onclick={(e) => { e.stopPropagation(); resetShotsOrder(sc, activeStyle); }}
                    title="Reset to original order"
                  >
                    <RotateCcw size={11} />
                    <span>Reset</span>
                  </button>
                {/if}
              </div>
            </div>
            <div class="shots-grid">
              {#each activeShots as shot, sIdx (shot.shotNumber + '_' + sIdx + '_' + shot.timeRange)}
                <div class="shot-chip">
                  <div class="shot-chip-header">
                    <div class="shot-badge-group">
                      <span class="shot-badge">{shot.shotNumber || sIdx + 1}</span>
                      <span class="shot-time">{formatCompactTime(shot.timeRange, sIdx)}</span>
                    </div>
                    {#if !isLocked}
                      <div class="shot-reorder-btns">
                        <button 
                          type="button" 
                          class="shot-move-btn"
                          disabled={isSubmitting || sIdx === 0}
                          onclick={(e) => { e.stopPropagation(); moveShot(sc, activeStyle, sIdx, -1); }}
                          title="Move shot earlier"
                        >
                          <ChevronLeft size={11} />
                        </button>
                        <button 
                          type="button" 
                          class="shot-move-btn"
                          disabled={isSubmitting || sIdx === activeShots.length - 1}
                          onclick={(e) => { e.stopPropagation(); moveShot(sc, activeStyle, sIdx, 1); }}
                          title="Move shot later"
                        >
                          <ChevronRight size={11} />
                        </button>
                      </div>
                    {/if}
                  </div>
                  <div class="shot-action">{cleanShotText(shot.action)}</div>
                  {#if shot.camera}
                    <div class="shot-camera">{cleanShotText(shot.camera)}</div>
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
              {#if !isLocked}
                <button 
                  class="edit-toggle-btn" 
                  onclick={() => isEditing = !isEditing}
                >
                  <Edit3 size={12} />
                  <span>{isEditing ? 'Done Editing' : 'Customize Prompt'}</span>
                </button>
              {/if}
            </div>

            {#if isEditing && !isLocked}
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
              {#if isLocked}
                <div class="scenario-confirmed-badge">
                  <Check size={14} />
                  <span>Render Launched with this Scenario</span>
                </div>
              {:else}
                <button 
                  class="render-scenario-btn primary"
                  disabled={isSubmitting}
                  onclick={() => handleConfirmRender(sc, idx)}
                >
                  {#if isSubmitting}
                    <Loader2 size={14} class="spin-icon" />
                    <span>Launching Render...</span>
                  {:else}
                    <Play size={14} />
                    <span>Render Video with this Scenario</span>
                  {/if}
                </button>
              {/if}
            </div>
          </div>
        {:else if !isLocked}
          <div class="select-scenario-bar">
            <button class="select-btn" disabled={isSubmitting} onclick={() => handleSelect(sc)}>
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

  .scenario-concept-box {
    margin: 8px 0 0 24px;
    font-size: 12px;
    line-height: 1.45;
    color: var(--text-secondary, #cbd5e1);
  }

  .concept-label {
    font-weight: 600;
    color: var(--text-primary, #ffffff);
    margin-right: 4px;
  }

  .concept-text {
    color: var(--text-secondary, #cbd5e1);
  }

  .metaphor-bridge {
    display: flex;
    align-items: flex-start;
    gap: 7px;
    margin: 6px 0 0 24px;
    padding: 6px 10px;
    background: rgba(251, 188, 4, 0.08);
    border: 1px solid rgba(251, 188, 4, 0.25);
    border-radius: 6px;
    font-size: 11px;
    line-height: 1.4;
    color: var(--text-secondary, #cbd5e1);
  }

  .metaphor-label {
    font-weight: 600;
    color: var(--agent-video, #fbbc04);
  }

  :global(.metaphor-icon) {
    color: #fbbc04;
    flex-shrink: 0;
    margin-top: 2px;
  }

  .style-tabs-container {
    margin: 10px 0 0 24px;
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
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

  .shots-timeline {
    margin: 10px 0 6px 24px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .shots-timeline-label {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 10px;
    font-weight: 600;
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .shots-grid {
    display: flex;
    gap: 8px;
    overflow-x: auto;
    padding-bottom: 6px;
    scrollbar-width: thin;
  }

  .shots-grid::-webkit-scrollbar {
    height: 4px;
  }

  .shots-grid::-webkit-scrollbar-thumb {
    background: var(--border-subtle);
    border-radius: var(--radius-full);
  }

  .shot-chip {
    flex: 1 1 165px;
    min-width: 150px;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 7px 9px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    box-sizing: border-box;
  }

  .shot-chip-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 4px;
    white-space: nowrap;
  }

  .shots-timeline-header-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    flex-wrap: wrap;
  }

  .shots-timeline-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .synced-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: rgba(16, 185, 129, 0.12);
    color: var(--accent-green, #10b981);
    border: 1px solid rgba(16, 185, 129, 0.25);
    border-radius: 9999px;
    font-size: 10px;
    font-weight: 600;
    padding: 2px 7px;
    white-space: nowrap;
  }

  .reset-order-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: transparent;
    color: var(--text-tertiary, #94a3b8);
    border: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.1));
    border-radius: 9999px;
    font-size: 10px;
    padding: 2px 8px;
    cursor: pointer;
    transition: all 0.2s ease;
    white-space: nowrap;
  }

  .reset-order-btn:hover {
    color: var(--text-primary);
    background: var(--bg-hover);
    border-color: var(--primary-accent);
  }

  .shot-badge-group {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .shot-reorder-btns {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    flex-shrink: 0;
  }

  .shot-move-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    padding: 0;
    border-radius: 3px;
    border: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.12));
    background: var(--bg-surface-elevated, rgba(255, 255, 255, 0.05));
    color: var(--text-secondary, #cbd5e1);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .shot-move-btn:hover:not(:disabled) {
    background: var(--agent-video, #ea4335);
    color: #ffffff;
    border-color: var(--agent-video, #ea4335);
    transform: scale(1.05);
  }

  .shot-move-btn:disabled {
    opacity: 0.2;
    cursor: not-allowed;
  }

  .shot-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 17px;
    height: 17px;
    padding: 0 4px;
    border-radius: 4px;
    background: rgba(251, 188, 4, 0.15);
    color: var(--agent-video, #FBBC04);
    font-size: 10px;
    font-weight: 700;
    line-height: 1;
    white-space: nowrap;
  }

  .shot-time {
    font-size: 10px;
    font-family: var(--font-mono, monospace);
    color: var(--text-tertiary);
    white-space: nowrap;
    letter-spacing: -0.02em;
  }

  .shot-action {
    font-size: 11px;
    color: var(--text-primary);
    line-height: 1.35;
    word-break: break-word;
  }

  .shot-camera {
    font-size: 10px;
    color: var(--text-tertiary);
    font-style: italic;
    line-height: 1.3;
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

  .deck-status-pill.locked {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    font-weight: 600;
    color: var(--text-secondary);
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    padding: 2px 8px;
    border-radius: var(--radius-full);
  }

  .scenario-card.locked-selected {
    border-color: rgba(52, 168, 83, 0.45);
    background: var(--bg-surface-elevated);
    box-shadow: 0 0 0 1px rgba(52, 168, 83, 0.2);
  }

  .scenario-card.locked-unselected {
    opacity: 0.5;
    filter: grayscale(0.25);
  }

  .scenario-card.locked-unselected:hover {
    border-color: var(--border-subtle);
  }

  .selected-for-render-tag {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    font-weight: 600;
    color: var(--agent-receipt, #34A853);
    background: rgba(52, 168, 83, 0.1);
    border: 1px solid rgba(52, 168, 83, 0.3);
    padding: 2px 8px;
    border-radius: var(--radius-full);
  }

  .scenario-confirmed-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 7px 14px;
    border-radius: var(--radius-md);
    background: rgba(52, 168, 83, 0.12);
    border: 1px solid rgba(52, 168, 83, 0.3);
    color: var(--agent-receipt, #34A853);
    font-size: 12px;
    font-weight: 600;
  }

  :global(.spin-icon) {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  .style-tab-btn:disabled,
  .shot-move-btn:disabled,
  .select-btn:disabled,
  .render-scenario-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
