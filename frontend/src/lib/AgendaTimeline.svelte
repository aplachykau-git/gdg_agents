<script>
  import { 
    Clock, 
    MoveUp, 
    MoveDown, 
    Plus, 
    Trash2, 
    Copy, 
    Check, 
    RefreshCw, 
    Calendar, 
    Sliders,
    Edit3,
    Eye
  } from '@lucide/svelte';

  let { rawText = '', author = 'agenda_generator', onRefine = null } = $props();

  // Baseline start time
  let baseStartTime = $state('17:30');
  let introText = $state('');
  let outroText = $state('REGISTRATION ❗\nPlease register on this page (RSVP), and bring your ID with you.');
  let items = $state([]);
  let activeTab = $state('interactive'); // 'interactive' | 'preview'
  let copied = $state(false);
  let expandedItemId = $state(null);

  // Time math helpers (5-minute granularity)
  function timeToMinutes(timeStr) {
    if (!timeStr || !timeStr.includes(':')) return 17 * 60 + 30;
    const [h, m] = timeStr.split(':').map(Number);
    return (h || 0) * 60 + (m || 0);
  }

  function minutesToTime(totalMinutes) {
    const h = Math.floor(totalMinutes / 60) % 24;
    const m = Math.round((totalMinutes % 60) / 5) * 5; // Snap to 5 mins
    const finalH = (h + Math.floor(m / 60)) % 24;
    const finalM = m % 60;
    return `${String(finalH).padStart(2, '0')}:${String(finalM).padStart(2, '0')}`;
  }

  // Parse raw text from agent into structured items
  function parseAgendaText(text) {
    if (!text) return;

    let cleanText = text;
    // Extract intro paragraph before "AGENDA"
    const agendaKeywordIdx = cleanText.search(/AGENDA/i);
    if (agendaKeywordIdx !== -1) {
      const beforeAgenda = cleanText.substring(0, agendaKeywordIdx).trim();
      // Remove ### Agenda headers
      introText = beforeAgenda.replace(/###\s*Agenda/gi, '').trim();
      cleanText = cleanText.substring(agendaKeywordIdx);
    } else {
      introText = '';
    }

    // Extract registration footer if present
    const regKeywordIdx = cleanText.search(/REGISTRATION\s*❗/i);
    if (regKeywordIdx !== -1) {
      outroText = cleanText.substring(regKeywordIdx).trim();
      cleanText = cleanText.substring(0, regKeywordIdx);
    }

    // Parse individual lines with emojis and times
    const lines = cleanText.split('\n').map(l => l.trim()).filter(Boolean);
    const parsedItems = [];
    let currentItem = null;

    const timeLineRegex = /^([\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]\s*)?(\d{1,2}:\d{2})\s*[-–—]\s*(.*)$/u;

    for (const line of lines) {
      if (/^AGENDA$/i.test(line)) continue;

      const match = line.match(timeLineRegex);
      if (match) {
        if (currentItem) {
          parsedItems.push(currentItem);
        }

        const emoji = (match[1] || '🎤').trim();
        const time = match[2];
        const rest = match[3];

        let title = rest;
        let speaker = '';

        // Check if rest contains Speaker Name - Talk Title (e.g. "John Doe - Building with AI")
        if (rest.includes(' - ')) {
          const parts = rest.split(' - ');
          speaker = parts[0].trim();
          title = parts.slice(1).join(' - ').trim();
        } else if (rest.toLowerCase().includes('registration')) {
          title = rest;
          speaker = '';
        } else if (rest.toLowerCase().includes('opening') || rest.toLowerCase().includes('welcome')) {
          title = rest;
          speaker = '';
        } else if (rest.toLowerCase().includes('break') || rest.toLowerCase().includes('networking')) {
          title = rest;
          speaker = '';
        }

        let type = 'talk';
        if (emoji.includes('🎟️') || title.toLowerCase().includes('registration')) type = 'registration';
        else if (emoji.includes('🚀') || title.toLowerCase().includes('opening')) type = 'opening';
        else if (emoji.includes('🍕') || emoji.includes('☕') || title.toLowerCase().includes('break')) type = 'break';
        else if (emoji.includes('🎉') || title.toLowerCase().includes('networking')) type = 'closing';

        currentItem = {
          id: `item_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`,
          emoji,
          startTime: time,
          duration: 30, // Default duration placeholder, will be auto-calculated
          title,
          speaker,
          details: '',
          bio: '',
          type
        };
      } else if (currentItem) {
        if (line.toLowerCase().startsWith("speaker's bio:") || line.toLowerCase().startsWith("speaker bio:") || line.toLowerCase().startsWith("bio:")) {
          currentItem.bio = line.replace(/^speaker(?:'s)?\s*bio:\s*/i, '').trim();
        } else if (line && !line.toUpperCase().includes('AGENDA')) {
          if (!currentItem.details) {
            currentItem.details = line;
          } else {
            currentItem.details += '\n' + line;
          }
        }
      }
    }

    if (currentItem) {
      parsedItems.push(currentItem);
    }

    if (parsedItems.length > 0) {
      baseStartTime = parsedItems[0].startTime || '17:30';

      // Calculate initial durations based on time differences
      for (let i = 0; i < parsedItems.length; i++) {
        if (i < parsedItems.length - 1) {
          const startM = timeToMinutes(parsedItems[i].startTime);
          const nextM = timeToMinutes(parsedItems[i + 1].startTime);
          let diff = nextM - startM;
          if (diff <= 0) diff = 30;
          // Snap diff to 5 minutes
          parsedItems[i].duration = Math.max(5, Math.round(diff / 5) * 5);
        } else {
          // Last item duration default
          parsedItems[i].duration = parsedItems[i].type === 'break' ? 20 : (parsedItems[i].type === 'opening' ? 10 : 40);
        }
      }
      items = parsedItems;
      recalculateSchedule();
    }
  }

  // Recalculate all slot times sequentially snapping to 5-minute boundaries
  function recalculateSchedule() {
    let currentM = timeToMinutes(baseStartTime);

    items = items.map((item) => {
      const snappedDuration = Math.max(5, Math.round((item.duration || 5) / 5) * 5);
      const startStr = minutesToTime(currentM);
      const endM = currentM + snappedDuration;
      const endStr = minutesToTime(endM);

      currentM = endM;
      return {
        ...item,
        startTime: startStr,
        endTime: endStr,
        duration: snappedDuration
      };
    });
  }

  // Initial load
  $effect(() => {
    if (rawText && items.length === 0) {
      parseAgendaText(rawText);
    }
  });

  // Stepper functions for 5-minute increments
  function adjustDuration(index, deltaMinutes) {
    if (!items[index]) return;
    const current = items[index].duration || 5;
    const nextVal = Math.max(5, current + deltaMinutes);
    items[index].duration = nextVal;
    recalculateSchedule();
  }

  function moveItem(index, direction) {
    const targetIdx = index + direction;
    if (targetIdx < 0 || targetIdx >= items.length) return;
    const newItems = [...items];
    const temp = newItems[index];
    newItems[index] = newItems[targetIdx];
    newItems[targetIdx] = temp;
    items = newItems;
    recalculateSchedule();
  }

  function removeItem(index) {
    items = items.filter((_, i) => i !== index);
    recalculateSchedule();
  }

  function addItem(type = 'talk') {
    const templates = {
      talk: { emoji: '🎤', title: 'New Speaker Session', speaker: 'Speaker Name', duration: 40, type: 'talk' },
      break: { emoji: '🍕', title: 'Break & Networking', speaker: '', duration: 20, type: 'break' },
      custom: { emoji: '💬', title: 'Q&A & Community Announcements', speaker: '', duration: 15, type: 'custom' }
    };
    const tpl = templates[type] || templates.talk;
    items = [
      ...items,
      {
        id: `item_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`,
        emoji: tpl.emoji,
        startTime: '19:00',
        duration: tpl.duration,
        title: tpl.title,
        speaker: tpl.speaker,
        details: '',
        bio: '',
        type: tpl.type
      }
    ];
    recalculateSchedule();
  }

  // Generate clean export text
  const formattedAgendaText = $derived.by(() => {
    let out = '';
    if (introText) {
      out += `${introText}\n\n`;
    }
    out += 'AGENDA\n\n';

    items.forEach(item => {
      const speakerPart = item.speaker ? `${item.speaker} - ` : '';
      out += `${item.emoji} ${item.startTime} - ${speakerPart}${item.title}\n`;
      if (item.details) {
        out += `${item.details}\n`;
      }
      if (item.bio) {
        out += `Speaker's bio: ${item.bio}\n`;
      }
      out += '\n';
    });

    if (outroText) {
      out += `${outroText}\n`;
    }
    return out.trim();
  });

  function copyAgenda() {
    if (!navigator.clipboard) return;
    navigator.clipboard.writeText(formattedAgendaText).then(() => {
      copied = true;
      setTimeout(() => { copied = false; }, 2000);
    });
  }

  function triggerRefine() {
    if (onRefine) {
      onRefine(formattedAgendaText);
    }
  }

  // Get total duration in minutes
  const totalMinutes = $derived.by(() => {
    return items.reduce((acc, item) => acc + (item.duration || 0), 0);
  });

  const finishTime = $derived.by(() => {
    if (items.length === 0) return '17:30';
    return items[items.length - 1].endTime || '20:30';
  });

  function getTypeColor(type) {
    switch (type) {
      case 'registration': return 'var(--agent-registration)';
      case 'opening': return 'var(--agent-root)';
      case 'talk': return 'var(--agent-agenda)';
      case 'break': return 'var(--agent-video)';
      default: return 'var(--primary-accent)';
    }
  }
</script>

<div class="agenda-timeline-card">
  <!-- Top Navigation & View Switcher -->
  <div class="agenda-top-bar">
    <div class="agenda-title-group">
      <div class="agenda-icon-badge">
        <Calendar size={16} />
      </div>
      <div>
        <h4 class="agenda-title">Interactive Event Agenda</h4>
        <span class="agenda-subtitle">Timeline with 5-minute snapping & dynamic recalculation</span>
      </div>
    </div>

    <div class="agenda-actions-group">
      <div class="view-mode-tabs">
        <button 
          class="tab-btn" 
          class:active={activeTab === 'interactive'} 
          onclick={() => activeTab = 'interactive'}
        >
          <Sliders size={13} />
          <span>Visual Timeline</span>
        </button>
        <button 
          class="tab-btn" 
          class:active={activeTab === 'preview'} 
          onclick={() => activeTab = 'preview'}
        >
          <Eye size={13} />
          <span>Copyable Text</span>
        </button>
      </div>

      <button class="action-pill-btn" onclick={copyAgenda} title="Copy formatted agenda for Meetup/Luma">
        {#if copied}
          <Check size={13} />
          <span>Copied!</span>
        {:else}
          <Copy size={13} />
          <span>Copy Agenda</span>
        {/if}
      </button>

      {#if onRefine}
        <button class="action-pill-btn refine" onclick={triggerRefine} title="Send adjusted agenda back to agent">
          <RefreshCw size={13} />
          <span>Refine</span>
        </button>
      {/if}
    </div>
  </div>

  <!-- Proportional Visual Timeline Bar -->
  {#if items.length > 0}
    <div class="timeline-visual-bar-wrap">
      <div class="timeline-meta-row">
        <span class="timeline-time-badge start">
          <Clock size={12} />
          <span>{baseStartTime} Start</span>
        </span>
        <span class="timeline-summary-text">
          {items.length} sessions &bull; {Math.floor(totalMinutes / 60)}h {totalMinutes % 60}m total
        </span>
        <span class="timeline-time-badge finish">
          <Clock size={12} />
          <span>{finishTime} Finish</span>
        </span>
      </div>

      <div class="timeline-bar-track">
        {#each items as item}
          {@const widthPct = Math.max(4, (item.duration / totalMinutes) * 100)}
          <div 
            class="timeline-bar-segment" 
            style="width: {widthPct}%; background: {getTypeColor(item.type)};"
            title="{item.startTime} - {item.endTime} ({item.duration}m): {item.title}"
          >
            <span class="segment-label">{item.emoji} {item.duration}m</span>
          </div>
        {/each}
      </div>
    </div>
  {/if}

  <!-- Interactive Timeline Content -->
  {#if activeTab === 'interactive'}
    <div class="timeline-editor-view">
      <!-- Baseline Start Controller -->
      <div class="baseline-control-bar">
        <div class="baseline-left">
          <Clock size={14} />
          <span class="baseline-label">Event Doors Open:</span>
          <select 
            bind:value={baseStartTime} 
            onchange={recalculateSchedule} 
            class="time-select"
          >
            <option value="17:00">17:00</option>
            <option value="17:15">17:15</option>
            <option value="17:30">17:30 (Default GDG)</option>
            <option value="17:45">17:45</option>
            <option value="18:00">18:00</option>
            <option value="18:30">18:30</option>
            <option value="19:00">19:00</option>
          </select>
        </div>
        <div class="quick-add-group">
          <button class="add-slot-btn" onclick={() => addItem('talk')}>
            <Plus size={12} />
            <span>+ Talk (40m)</span>
          </button>
          <button class="add-slot-btn" onclick={() => addItem('break')}>
            <Plus size={12} />
            <span>+ Break (20m)</span>
          </button>
        </div>
      </div>

      <!-- Schedule Slots Stack -->
      <div class="slots-stack">
        {#each items as item, idx}
          {@const isExpanded = expandedItemId === item.id}
          <div class="slot-card" class:slot-expanded={isExpanded} style="--slot-accent: {getTypeColor(item.type)}">
            <!-- Slot Header / Main Row -->
            <div class="slot-main-row">
              <!-- Reorder Controls -->
              <div class="reorder-col">
                <button 
                  class="reorder-btn" 
                  disabled={idx === 0} 
                  onclick={() => moveItem(idx, -1)} 
                  title="Move up"
                >
                  <MoveUp size={12} />
                </button>
                <button 
                  class="reorder-btn" 
                  disabled={idx === items.length - 1} 
                  onclick={() => moveItem(idx, 1)} 
                  title="Move down"
                >
                  <MoveDown size={12} />
                </button>
              </div>

              <!-- Time Badge -->
              <div class="slot-time-pill">
                <span class="time-start">{item.startTime}</span>
                <span class="time-divider">&rarr;</span>
                <span class="time-end">{item.endTime}</span>
              </div>

              <!-- Emoji & Title Area -->
              <div class="slot-info-col">
                <div class="slot-title-line">
                  <span class="slot-emoji">{item.emoji}</span>
                  {#if item.speaker}
                    <input 
                      type="text" 
                      class="slot-speaker-input" 
                      bind:value={item.speaker} 
                      placeholder="Speaker Name"
                      oninput={recalculateSchedule} 
                    />
                    <span class="speaker-sep">&bull;</span>
                  {/if}
                  <input 
                    type="text" 
                    class="slot-title-input" 
                    bind:value={item.title} 
                    placeholder="Session Title"
                    oninput={recalculateSchedule} 
                  />
                </div>
              </div>

              <!-- Duration Stepper (5-minute step) -->
              <div class="slot-duration-stepper">
                <button 
                  class="step-btn" 
                  onclick={() => adjustDuration(idx, -5)} 
                  disabled={item.duration <= 5}
                  title="Decrease by 5 minutes"
                >
                  -5m
                </button>
                <span class="duration-display">{item.duration}m</span>
                <button 
                  class="step-btn" 
                  onclick={() => adjustDuration(idx, 5)} 
                  title="Increase by 5 minutes"
                >
                  +5m
                </button>
              </div>

              <!-- Actions -->
              <div class="slot-actions">
                <button 
                  class="icon-action-btn" 
                  onclick={() => expandedItemId = isExpanded ? null : item.id} 
                  title={isExpanded ? "Collapse details" : "Edit details & bio"}
                >
                  <Edit3 size={13} />
                </button>
                <button 
                  class="icon-action-btn delete" 
                  onclick={() => removeItem(idx)} 
                  title="Delete session block"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            </div>

            <!-- Expandable Details & Bio Editor -->
            {#if isExpanded}
              <div class="slot-expanded-body">
                <div class="field-group">
                  <span class="field-label">Talk Description / Details:</span>
                  <textarea 
                    class="field-textarea" 
                    bind:value={item.details} 
                    placeholder="Provide talk summary or topics covered..."
                    rows="2"
                  ></textarea>
                </div>
                <div class="field-group">
                  <span class="field-label">Speaker Biography:</span>
                  <textarea 
                    class="field-textarea" 
                    bind:value={item.bio} 
                    placeholder="Speaker background and role..."
                    rows="2"
                  ></textarea>
                </div>
              </div>
            {/if}
          </div>
        {/each}
      </div>
    </div>
  {:else}
    <!-- Copyable Text Preview -->
    <div class="agenda-text-preview">
      <pre class="raw-preview-block">{formattedAgendaText}</pre>
    </div>
  {/if}
</div>

<style>
  .agenda-timeline-card {
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: 14px;
    margin: 10px 0;
    display: flex;
    flex-direction: column;
    gap: 12px;
    box-shadow: var(--shadow-elevation-1);
  }

  .agenda-top-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 10px;
    border-bottom: 1px solid var(--border-subtle);
    padding-bottom: 10px;
  }

  .agenda-title-group {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .agenda-icon-badge {
    width: 32px;
    height: 32px;
    border-radius: var(--radius-sm);
    background: var(--bg-agenda);
    color: var(--agent-agenda);
    border: 1px solid rgba(52, 211, 153, 0.3);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .agenda-title {
    font-size: var(--font-size-body-md);
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
  }

  .agenda-subtitle {
    font-size: var(--font-size-body-sm);
    color: var(--text-tertiary);
  }

  .agenda-actions-group {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .view-mode-tabs {
    display: flex;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-pill);
    padding: 2px;
  }

  .tab-btn {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 4px 10px;
    font-size: var(--font-size-body-sm);
    border: none;
    background: transparent;
    color: var(--text-secondary);
    border-radius: var(--radius-pill);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .tab-btn.active {
    background: var(--primary-accent);
    color: var(--text-inverse);
    font-weight: 500;
  }

  .action-pill-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 5px 12px;
    font-size: var(--font-size-body-sm);
    font-weight: 500;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    color: var(--text-primary);
    border-radius: var(--radius-pill);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .action-pill-btn:hover {
    background: var(--bg-surface-variant);
    border-color: var(--border-medium);
  }

  .action-pill-btn.refine {
    background: var(--bg-agenda);
    color: var(--agent-agenda);
    border-color: rgba(52, 211, 153, 0.3);
  }

  .action-pill-btn.refine:hover {
    background: rgba(52, 211, 153, 0.2);
  }

  /* Visual Timeline Bar */
  .timeline-visual-bar-wrap {
    display: flex;
    flex-direction: column;
    gap: 6px;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 8px 12px;
  }

  .timeline-meta-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: var(--font-size-body-sm);
  }

  .timeline-time-badge {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    border-radius: var(--radius-pill);
    font-weight: 600;
    font-size: var(--font-size-label);
  }

  .timeline-time-badge.start {
    background: rgba(56, 189, 248, 0.15);
    color: var(--agent-root);
  }

  .timeline-time-badge.finish {
    background: rgba(52, 211, 153, 0.15);
    color: var(--agent-agenda);
  }

  .timeline-summary-text {
    color: var(--text-secondary);
    font-size: var(--font-size-label);
  }

  .timeline-bar-track {
    display: flex;
    height: 18px;
    border-radius: var(--radius-pill);
    overflow: hidden;
    background: var(--bg-surface-elevated);
    gap: 2px;
  }

  .timeline-bar-segment {
    display: flex;
    align-items: center;
    justify-content: center;
    color: #121314;
    font-size: 10px;
    font-weight: 700;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    transition: width 0.2s ease;
  }

  .segment-label {
    padding: 0 4px;
  }

  /* Editor View */
  .timeline-editor-view {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .baseline-control-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 6px 12px;
  }

  .baseline-left {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: var(--font-size-body-sm);
    color: var(--text-secondary);
  }

  .time-select {
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    color: var(--text-primary);
    padding: 3px 8px;
    border-radius: var(--radius-xs);
    font-size: var(--font-size-body-sm);
    font-weight: 600;
  }

  .quick-add-group {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .add-slot-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 4px 8px;
    font-size: var(--font-size-label);
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    color: var(--text-primary);
    border-radius: var(--radius-pill);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .add-slot-btn:hover {
    background: var(--bg-surface-variant);
    border-color: var(--border-medium);
  }

  /* Slots Stack */
  .slots-stack {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .slot-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-left: 3px solid var(--slot-accent);
    border-radius: var(--radius-sm);
    padding: 6px 10px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    transition: border-color 0.15s ease;
  }

  .slot-card:hover {
    border-color: var(--border-medium);
  }

  .slot-main-row {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .reorder-col {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .reorder-btn {
    background: transparent;
    border: none;
    color: var(--text-tertiary);
    cursor: pointer;
    padding: 1px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 2px;
  }

  .reorder-btn:hover:not(:disabled) {
    color: var(--text-primary);
    background: var(--bg-surface-elevated);
  }

  .reorder-btn:disabled {
    opacity: 0.2;
    cursor: not-allowed;
  }

  .slot-time-pill {
    display: flex;
    align-items: center;
    gap: 4px;
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    padding: 3px 8px;
    border-radius: var(--radius-xs);
    font-family: var(--font-family-mono);
    font-size: var(--font-size-label);
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
  }

  .time-divider {
    color: var(--text-tertiary);
  }

  .slot-info-col {
    flex: 1;
    display: flex;
    align-items: center;
  }

  .slot-title-line {
    display: flex;
    align-items: center;
    gap: 6px;
    width: 100%;
  }

  .slot-emoji {
    font-size: 1.1rem;
  }

  .slot-speaker-input, .slot-title-input {
    background: transparent;
    border: 1px solid transparent;
    color: var(--text-primary);
    font-size: var(--font-size-body-sm);
    padding: 3px 6px;
    border-radius: var(--radius-xs);
    outline: none;
    transition: all 0.15s ease;
  }

  .slot-speaker-input {
    font-weight: 600;
    max-width: 160px;
  }

  .slot-title-input {
    flex: 1;
  }

  .slot-speaker-input:focus, .slot-title-input:focus {
    background: var(--bg-surface-elevated);
    border-color: var(--border-focus);
  }

  .speaker-sep {
    color: var(--text-tertiary);
  }

  /* Duration Stepper */
  .slot-duration-stepper {
    display: flex;
    align-items: center;
    gap: 4px;
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-pill);
    padding: 2px 4px;
  }

  .step-btn {
    background: transparent;
    border: none;
    color: var(--text-secondary);
    font-size: var(--font-size-label);
    font-weight: 700;
    padding: 2px 6px;
    border-radius: var(--radius-pill);
    cursor: pointer;
  }

  .step-btn:hover:not(:disabled) {
    background: var(--bg-surface-variant);
    color: var(--text-primary);
  }

  .step-btn:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }

  .duration-display {
    font-family: var(--font-family-mono);
    font-size: var(--font-size-label);
    font-weight: 600;
    color: var(--text-primary);
    min-width: 32px;
    text-align: center;
  }

  .slot-actions {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .icon-action-btn {
    background: transparent;
    border: none;
    color: var(--text-tertiary);
    cursor: pointer;
    padding: 4px;
    border-radius: var(--radius-xs);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .icon-action-btn:hover {
    background: var(--bg-surface-elevated);
    color: var(--text-primary);
  }

  .icon-action-btn.delete:hover {
    background: rgba(244, 63, 94, 0.15);
    color: var(--agent-planner);
  }

  /* Expanded Details & Bio */
  .slot-expanded-body {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 8px 10px;
    background: var(--bg-surface-elevated);
    border-radius: var(--radius-xs);
    margin-top: 4px;
    border: 1px solid var(--border-subtle);
  }

  .field-group {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .field-label {
    font-size: var(--font-size-label);
    font-weight: 600;
    color: var(--text-tertiary);
    text-transform: uppercase;
  }

  .field-textarea {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-xs);
    color: var(--text-primary);
    font-family: var(--font-family-base);
    font-size: var(--font-size-body-sm);
    padding: 6px 8px;
    resize: vertical;
    outline: none;
  }

  .field-textarea:focus {
    border-color: var(--border-focus);
  }

  /* Raw Preview Block */
  .agenda-text-preview {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 12px;
  }

  .raw-preview-block {
    font-family: var(--font-family-mono);
    font-size: var(--font-size-body-sm);
    white-space: pre-wrap;
    word-break: break-word;
    color: var(--text-primary);
    line-height: 1.6;
    margin: 0;
  }
</style>
