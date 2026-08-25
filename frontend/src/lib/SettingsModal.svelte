<script>
  import { Settings, Sparkles, Building, Check, AlertCircle } from '@lucide/svelte';

  let {
    show = false,
    config = { communityName: 'GDG Krakow' },
    onSave = () => {},
    onClose = () => {}
  } = $props();

  let draftCommunityName = $state('GDG Krakow');
  let isSavedNotice = $state(false);

  // Validation rules
  const trimmed = $derived((draftCommunityName || '').trim());
  const validationError = $derived.by(() => {
    if (!draftCommunityName || trimmed === '') {
      return 'Community name cannot be empty.';
    }
    if (trimmed.length < 4) {
      return `Name is too short (min 4 characters, currently ${trimmed.length}).`;
    }
    if (draftCommunityName.length > 30) {
      return `Name is too long (max 30 characters, currently ${draftCommunityName.length}).`;
    }
    return '';
  });

  const isValid = $derived(validationError === '');

  // Sync draft state whenever modal opens or config changes
  $effect(() => {
    if (show) {
      draftCommunityName = config.communityName || 'GDG Krakow';
      isSavedNotice = false;
    }
  });

  function handleSave() {
    if (!isValid) return;
    const updated = {
      ...config,
      communityName: trimmed
    };
    onSave(updated);
    isSavedNotice = true;
    setTimeout(() => {
      onClose();
    }, 400);
  }
</script>

{#if show}
  <div 
    class="modal-backdrop" 
    role="button" 
    tabindex="-1" 
    onclick={(e) => { if (e.target === e.currentTarget) onClose(); }} 
    onkeydown={(e) => { if (e.key === 'Escape') onClose(); }}
  >
    <div class="modal-card">
      <header class="modal-header">
        <div class="modal-title-group">
          <div class="settings-icon-box">
            <Settings size={18} />
          </div>
          <div>
            <h2>Studio Settings</h2>
            <span class="modal-sub">Customize Community Studio variables and defaults</span>
          </div>
        </div>
        <button class="modal-close-btn" onclick={onClose} title="Close">&times;</button>
      </header>

      <div class="modal-body">
        <!-- Community Section -->
        <div class="settings-section">
          <div class="section-title">
            <Building size={16} class="section-icon" />
            <span>Community & Chapter</span>
          </div>
          
          <div class="setting-item">
            <div class="label-row">
              <label for="communityName" class="setting-label">Community Name</label>
              <span class="char-counter" class:counter-error={!isValid}>
                {draftCommunityName.length} / 30
              </span>
            </div>
            <p class="setting-desc">Primary chapter identifier used across post generators, meeting minutes, and agenda formatting.</p>
            
            <div class="input-wrapper">
              <input 
                id="communityName" 
                type="text" 
                maxlength="35"
                bind:value={draftCommunityName} 
                placeholder="e.g. GDG Krakow"
                class="settings-text-input"
                class:input-error={!isValid}
              />
            </div>

            {#if !isValid}
              <div class="validation-error-msg">
                <AlertCircle size={13} />
                <span>{validationError}</span>
              </div>
            {:else}
              <span class="preview-badge">
                Active Chapter: <strong>{trimmed}</strong>
              </span>
            {/if}
          </div>
        </div>

        <!-- Future Settings Placeholder Slot -->
        <div class="settings-section future-section">
          <div class="section-title">
            <Sparkles size={16} class="section-icon" />
            <span>Agent Orchestration Defaults</span>
          </div>
          <p class="setting-desc">Additional preferences, language defaults, and agent configurations will be configured here.</p>
        </div>
      </div>

      <footer class="modal-actions">
        {#if isSavedNotice}
          <div class="saved-indicator">
            <Check size={14} />
            <span>Settings saved!</span>
          </div>
        {/if}
        <div class="action-buttons">
          <button class="btn-secondary" onclick={onClose}>Cancel</button>
          <button 
            class="btn-primary" 
            onclick={handleSave} 
            disabled={!isValid}
            title={!isValid ? validationError : 'Save Settings'}
          >
            Save Changes
          </button>
        </div>
      </footer>
    </div>
  </div>
{/if}

<style>
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(11, 12, 14, 0.8);
    backdrop-filter: blur(4px);
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
    animation: fadeIn 0.2s ease-out;
  }

  .modal-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-xl);
    max-width: 580px;
    width: 100%;
    max-height: 85vh;
    display: flex;
    flex-direction: column;
    box-shadow: var(--shadow-elevation-3);
    overflow: hidden;
  }

  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 20px 24px;
    border-bottom: 1px solid var(--border-subtle);
  }

  .modal-title-group {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .settings-icon-box {
    width: 36px;
    height: 36px;
    border-radius: var(--radius-md);
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--primary-accent);
  }

  .modal-header h2 {
    font-size: 16px;
    font-weight: 700;
    color: var(--text-primary);
    margin: 0;
  }

  .modal-sub {
    font-size: 11px;
    color: var(--text-tertiary);
  }

  .modal-close-btn {
    background: none;
    border: none;
    color: var(--text-secondary);
    font-size: 24px;
    cursor: pointer;
    line-height: 1;
    padding: 4px;
  }

  .modal-close-btn:hover {
    color: var(--text-primary);
  }

  .modal-body {
    padding: 24px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .settings-section {
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    padding: 18px 20px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .future-section {
    opacity: 0.85;
    border-style: dashed;
  }

  .section-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    font-weight: 700;
    color: var(--text-primary);
  }

  :global(.section-icon) {
    color: var(--primary-accent);
  }

  .setting-item {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .label-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .setting-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .char-counter {
    font-size: 11px;
    color: var(--text-tertiary);
    font-family: var(--font-family-mono, monospace);
  }

  .counter-error {
    color: var(--accent-red, #ea4335);
    font-weight: 600;
  }

  .setting-desc {
    font-size: 12px;
    color: var(--text-secondary);
    line-height: 1.4;
    margin: 0;
  }

  .input-wrapper {
    margin-top: 4px;
  }

  .settings-text-input {
    width: 100%;
    background: var(--bg-app);
    border: 1px solid var(--border-subtle);
    color: var(--text-primary);
    padding: 8px 14px;
    border-radius: var(--radius-pill);
    font-size: 13px;
    outline: none;
    transition: var(--transition-fast);
    box-sizing: border-box;
  }

  .settings-text-input:focus {
    border-color: var(--primary-accent);
    box-shadow: 0 0 0 2px var(--primary-accent-container);
  }

  .settings-text-input.input-error {
    border-color: var(--accent-red, #ea4335);
    box-shadow: 0 0 0 2px rgba(234, 67, 53, 0.15);
  }

  .validation-error-msg {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    color: var(--accent-red, #ea4335);
    margin-top: 4px;
    font-weight: 500;
  }

  .preview-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    color: var(--text-tertiary);
    margin-top: 4px;
  }

  .preview-badge strong {
    color: var(--primary-accent);
  }

  .modal-actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 10px;
    padding: 16px 24px;
    border-top: 1px solid var(--border-subtle);
    background: var(--bg-surface);
  }

  .saved-indicator {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: var(--accent-green, #34a853);
    font-size: 12px;
    font-weight: 600;
    animation: fadeIn 0.2s ease-out;
  }

  .action-buttons {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-left: auto;
  }

  .btn-secondary {
    background: transparent;
    border: 1px solid var(--border-subtle);
    color: var(--text-secondary);
    padding: 8px 16px;
    border-radius: var(--radius-pill);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: var(--transition-fast);
  }

  .btn-secondary:hover {
    background: var(--bg-surface-elevated);
    color: var(--text-primary);
  }

  .btn-primary {
    background: var(--primary-gradient, var(--primary-accent));
    color: #ffffff;
    border: none;
    padding: 8px 20px;
    border-radius: var(--radius-pill);
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 2px 8px rgba(37, 99, 235, 0.25);
    transition: var(--transition-fast);
  }

  .btn-primary:hover:not(:disabled) {
    filter: brightness(1.1);
  }

  .btn-primary:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: scale(0.98); }
    to { opacity: 1; transform: scale(1); }
  }
</style>
