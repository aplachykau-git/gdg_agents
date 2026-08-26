<script>
  import { Settings, X, Check, Globe, Cpu, Layout } from '@lucide/svelte';
  import { DEFAULT_CONFIG } from './constants.js';

  let {
    show = false,
    config = DEFAULT_CONFIG,
    onSave = () => {},
    onClose = () => {}
  } = $props();

  let draft = $state({ ...DEFAULT_CONFIG });
  let saveStatus = $state('');
  let saveTimer = null;

  // Sync draft state whenever modal opens or external config changes
  $effect(() => {
    if (show) {
      draft = {
        ...DEFAULT_CONFIG,
        ...config
      };
      saveStatus = '';
    }
  });

  function triggerAutoSave(newValues) {
    const updated = {
      ...config,
      ...draft,
      ...newValues
    };
    onSave(updated);

    saveStatus = 'Saved';
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      saveStatus = '';
    }, 1800);
  }

  function handleTextInput(key, event) {
    const val = event.target.value;
    draft[key] = val;
    triggerAutoSave({ [key]: val });
  }

  function toggleSwitch(key) {
    const nextVal = !draft[key];
    draft[key] = nextVal;
    triggerAutoSave({ [key]: nextVal });
  }
</script>

{#if show}
  <div 
    class="modal-backdrop" 
    role="presentation"
    onclick={(e) => { if (e.target === e.currentTarget) onClose(); }} 
    onkeydown={(e) => { if (e.key === 'Escape') onClose(); }}
  >
    <div class="settings-dialog" role="dialog" aria-modal="true" aria-labelledby="settings-title">
      <!-- Header -->
      <header class="dialog-header">
        <div class="header-title-area">
          <Settings size={16} class="header-icon" />
          <h2 id="settings-title">Settings</h2>
          {#if saveStatus}
            <span class="autosave-badge">
              <Check size={12} />
              {saveStatus}
            </span>
          {/if}
        </div>
        <button class="icon-btn-close" onclick={onClose} aria-label="Close settings" title="Close (Esc)">
          <X size={16} />
        </button>
      </header>

      <!-- Body / Setting Sections -->
      <div class="dialog-body">
        <!-- Section: General / Workspace -->
        <section class="setting-group">
          <div class="group-header">
            <Globe size={14} />
            <h3>General</h3>
          </div>

          <div class="setting-row">
            <div class="setting-meta">
              <label for="setting-community-name" class="setting-title">Community Chapter</label>
              <p class="setting-desc">Primary chapter identifier used across generated posts, agendas, and reports.</p>
            </div>
            <div class="setting-control">
              <input
                id="setting-community-name"
                type="text"
                value={draft.communityName || ''}
                oninput={(e) => handleTextInput('communityName', e)}
                placeholder="e.g. GDG Krakow"
                class="ide-input"
                maxlength="50"
              />
            </div>
          </div>
        </section>

        <!-- Section: Agent Execution -->
        <section class="setting-group">
          <div class="group-header">
            <Cpu size={14} />
            <h3>Agent Execution</h3>
          </div>

          <div class="setting-row">
            <div class="setting-meta">
              <span class="setting-title">Stream Responses</span>
              <p class="setting-desc">Render agent output in real-time as tokens arrive from the reasoning engines.</p>
            </div>
            <div class="setting-control">
              <button
                type="button"
                role="switch"
                aria-checked={draft.streamResponses}
                aria-label="Toggle Stream Responses"
                class="ide-switch"
                class:active={draft.streamResponses}
                onclick={() => toggleSwitch('streamResponses')}
              >
                <span class="switch-knob"></span>
              </button>
            </div>
          </div>

          <div class="setting-row">
            <div class="setting-meta">
              <span class="setting-title">Show Tool Execution Details</span>
              <p class="setting-desc">Display intermediate function calls, OCR queries, and rendering pipeline events.</p>
            </div>
            <div class="setting-control">
              <button
                type="button"
                role="switch"
                aria-checked={draft.showToolCalls}
                aria-label="Toggle Tool Execution Details"
                class="ide-switch"
                class:active={draft.showToolCalls}
                onclick={() => toggleSwitch('showToolCalls')}
              >
                <span class="switch-knob"></span>
              </button>
            </div>
          </div>
        </section>

        <!-- Section: Interface & Layout -->
        <section class="setting-group">
          <div class="group-header">
            <Layout size={14} />
            <h3>Interface & Layout</h3>
          </div>

          <div class="setting-row">
            <div class="setting-meta">
              <span class="setting-title">Auto-scroll Timeline</span>
              <p class="setting-desc">Automatically follow newest messages and streaming tokens in the active conversation.</p>
            </div>
            <div class="setting-control">
              <button
                type="button"
                role="switch"
                aria-checked={draft.autoScroll}
                aria-label="Toggle Auto-scroll"
                class="ide-switch"
                class:active={draft.autoScroll}
                onclick={() => toggleSwitch('autoScroll')}
              >
                <span class="switch-knob"></span>
              </button>
            </div>
          </div>

          <div class="setting-row">
            <div class="setting-meta">
              <span class="setting-title">Compact View Density</span>
              <p class="setting-desc">Condense spacing between chat events for high-density multi-agent tracking.</p>
            </div>
            <div class="setting-control">
              <button
                type="button"
                role="switch"
                aria-checked={draft.compactDensity}
                aria-label="Toggle Compact View Density"
                class="ide-switch"
                class:active={draft.compactDensity}
                onclick={() => toggleSwitch('compactDensity')}
              >
                <span class="switch-knob"></span>
              </button>
            </div>
          </div>
        </section>
      </div>

      <!-- Clean Footer -->
      <footer class="dialog-footer">
        <span class="footer-hint">Settings are saved automatically to your workspace.</span>
        <button class="btn-done" onclick={onClose}>Done</button>
      </footer>
    </div>
  </div>
{/if}

<style>
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.65);
    backdrop-filter: blur(6px);
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 16px;
    animation: fadeIn 0.15s ease-out;
  }

  .settings-dialog {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    width: 100%;
    max-width: 540px;
    max-height: 85vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 16px 40px -8px rgba(0, 0, 0, 0.45), 0 0 0 1px rgba(255, 255, 255, 0.05);
    overflow: hidden;
  }

  /* Header */
  .dialog-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 18px;
    border-bottom: 1px solid var(--border-subtle);
    background: var(--bg-surface-elevated);
  }

  .header-title-area {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  :global(.header-icon) {
    color: var(--primary-accent);
  }

  .dialog-header h2 {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
    letter-spacing: -0.01em;
  }

  .autosave-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    font-weight: 500;
    color: var(--status-success);
    background: rgba(129, 201, 149, 0.12);
    padding: 2px 8px;
    border-radius: var(--radius-pill);
    animation: fadeIn 0.15s ease-out;
  }

  .icon-btn-close {
    background: transparent;
    border: none;
    color: var(--text-secondary);
    width: 28px;
    height: 28px;
    border-radius: var(--radius-sm);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: var(--transition-fast);
  }

  .icon-btn-close:hover {
    background: var(--bg-surface-variant);
    color: var(--text-primary);
  }

  /* Body */
  .dialog-body {
    padding: 16px 18px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .setting-group {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .group-header {
    display: flex;
    align-items: center;
    gap: 6px;
    color: var(--text-tertiary);
    margin-bottom: 6px;
    padding-bottom: 4px;
  }

  .group-header h3 {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-tertiary);
    margin: 0;
  }

  .setting-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 10px 12px;
    border-radius: var(--radius-sm);
    transition: background var(--transition-fast);
  }

  .setting-row:hover {
    background: var(--bg-surface-elevated);
  }

  .setting-meta {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .setting-title {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-primary);
  }

  .setting-desc {
    font-size: 11.5px;
    color: var(--text-tertiary);
    line-height: 1.35;
    margin: 0;
  }

  .setting-control {
    flex-shrink: 0;
    display: flex;
    align-items: center;
  }

  /* Input */
  .ide-input {
    width: 190px;
    background: var(--bg-app);
    border: 1px solid var(--border-subtle);
    color: var(--text-primary);
    padding: 6px 10px;
    border-radius: var(--radius-sm);
    font-size: 12.5px;
    outline: none;
    transition: var(--transition-fast);
  }

  .ide-input:focus {
    border-color: var(--primary-accent);
    box-shadow: 0 0 0 2px var(--primary-accent-container);
  }

  /* Toggle Switch (Тумблер) */
  .ide-switch {
    width: 36px;
    height: 20px;
    border-radius: var(--radius-pill);
    background: var(--bg-surface-variant);
    border: 1px solid var(--border-medium);
    padding: 0;
    position: relative;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    transition: background 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
    outline: none;
  }

  .ide-switch:focus-visible {
    box-shadow: 0 0 0 2px var(--primary-accent);
  }

  .ide-switch.active {
    background: var(--primary-accent);
    border-color: var(--primary-accent);
    box-shadow: 0 0 8px var(--gemini-active-glow);
  }

  .switch-knob {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: #ffffff;
    transform: translateX(2px);
    transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
  }

  .ide-switch.active .switch-knob {
    transform: translateX(18px);
  }

  /* Footer */
  .dialog-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 18px;
    border-top: 1px solid var(--border-subtle);
    background: var(--bg-surface-elevated);
  }

  .footer-hint {
    font-size: 11px;
    color: var(--text-tertiary);
  }

  .btn-done {
    background: var(--bg-surface-variant);
    border: 1px solid var(--border-subtle);
    color: var(--text-primary);
    padding: 5px 14px;
    border-radius: var(--radius-sm);
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: var(--transition-fast);
  }

  .btn-done:hover {
    background: var(--border-medium);
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: scale(0.98); }
    to { opacity: 1; transform: scale(1); }
  }
</style>
