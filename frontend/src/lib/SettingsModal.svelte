<script>
  import { 
    Settings, 
    X, 
    Check, 
    Globe, 
    HardDrive, 
    AlertCircle, 
    FileText, 
    ExternalLink, 
    Copy, 
    ChevronDown, 
    ChevronRight,
    Info,
    Video,
    AlertTriangle
  } from '@lucide/svelte';
  import { 
    DEFAULT_CONFIG, 
    DEFAULT_TEMPLATE_URL,
    DEFAULT_TEMPLATE_ID,
    extractDriveFolderId, 
    validateDriveFolderInput,
    extractGoogleDocId,
    validateGoogleDocTemplateInput
  } from './constants.js';

  let {
    show = false,
    config = DEFAULT_CONFIG,
    onSave = () => {},
    onClose = () => {}
  } = $props();

  let draft = $state({ ...DEFAULT_CONFIG });
  let saveStatus = $state('');
  let driveFolderError = $state('');
  let driveFolderInputRaw = $state('');
  let templateError = $state('');
  let templateInputRaw = $state('');
  let isTemplateGuideOpen = $state(false);
  let emailCopied = $state(false);
  let saveTimer = null;

  // Sync draft state whenever modal opens or external config changes
  $effect(() => {
    if (show) {
      draft = {
        ...DEFAULT_CONFIG,
        ...config
      };
      driveFolderInputRaw = config?.googleDriveFolderId || '';
      driveFolderError = '';
      templateInputRaw = config?.googleDocsTemplateId || '';
      templateError = '';
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

  function handleToggle(key) {
    const currentVal = draft[key] !== undefined ? draft[key] : (DEFAULT_CONFIG[key] ?? false);
    const newVal = !currentVal;
    draft[key] = newVal;
    triggerAutoSave({ [key]: newVal });
  }

  function handleDone() {
    const folderVal = (driveFolderInputRaw || '').trim();
    const templateVal = (templateInputRaw || '').trim();
    const resolvedFolder = extractDriveFolderId(folderVal) || folderVal;
    const resolvedTemplate = extractGoogleDocId(templateVal) || templateVal;

    const finalDraft = {
      ...config,
      ...draft,
      googleDriveFolderId: resolvedFolder,
      googleDocsTemplateId: resolvedTemplate
    };
    onSave(finalDraft);
    onClose();
  }

  function handleTextInput(key, event) {
    let rawVal = event.target.value;
    if (key === 'googleDriveFolderId') {
      driveFolderInputRaw = rawVal;
      const validation = validateDriveFolderInput(rawVal);
      if (!validation.valid && rawVal.trim().length > 0) {
        driveFolderError = validation.error;
      } else {
        driveFolderError = '';
      }
      const resolvedId = (validation.valid && validation.folderId) ? validation.folderId : rawVal.trim();
      draft.googleDriveFolderId = resolvedId;
      triggerAutoSave({ googleDriveFolderId: resolvedId });
    } else if (key === 'googleDocsTemplateId') {
      templateInputRaw = rawVal;
      const validation = validateGoogleDocTemplateInput(rawVal);
      if (!validation.valid && rawVal.trim().length > 0) {
        templateError = validation.error;
      } else {
        templateError = '';
      }
      const resolvedId = (validation.valid && validation.docId) ? validation.docId : rawVal.trim();
      draft.googleDocsTemplateId = resolvedId;
      triggerAutoSave({ googleDocsTemplateId: resolvedId });
    } else {
      draft[key] = rawVal;
      triggerAutoSave({ [key]: rawVal });
    }
  }

  async function copyServiceAccountEmail() {
    if (draft.serviceAccountEmail) {
      try {
        await navigator.clipboard.writeText(draft.serviceAccountEmail);
        emailCopied = true;
        setTimeout(() => {
          emailCopied = false;
        }, 2000);
      } catch (err) {
        console.error('Failed to copy email:', err);
      }
    }
  }
</script>

{#if show}
  <div 
    class="modal-backdrop" 
    role="presentation"
    onclick={(e) => { if (e.target === e.currentTarget) handleDone(); }} 
    onkeydown={(e) => { if (e.key === 'Escape') handleDone(); }}
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
        <button class="icon-btn-close" onclick={handleDone} aria-label="Close settings" title="Close (Esc)">
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

        <!-- Section: Video Generation Settings -->
        <section class="setting-group">
          <div class="group-header">
            <Video size={14} />
            <h3>Video Generation Settings</h3>
          </div>

          <div class="setting-row">
            <div class="setting-meta">
              <label for="setting-render-4k" class="setting-title">4K Ultra-HD Rendering</label>
              <p class="setting-desc">Renders high-bitrate 4K vertical video files alongside standard 1080p.</p>
            </div>
            <div class="setting-control">
              <button
                id="setting-render-4k"
                type="button"
                role="switch"
                aria-label="Toggle 4K Ultra-HD Rendering"
                aria-checked={draft.render4k ?? true}
                class="toggle-switch"
                class:toggle-active={draft.render4k ?? true}
                onclick={() => handleToggle('render4k')}
              >
                <span class="toggle-handle"></span>
              </button>
            </div>
          </div>

          <div class="setting-row">
            <div class="setting-meta">
              <label for="setting-render-gif" class="setting-title">Animated GIF Generation</label>
              <p class="setting-desc">Creates animated GIF previews for speaker cards and email newsletters.</p>
            </div>
            <div class="setting-control">
              <button
                id="setting-render-gif"
                type="button"
                role="switch"
                aria-label="Toggle Animated GIF Generation"
                aria-checked={draft.renderGif ?? true}
                class="toggle-switch"
                class:toggle-active={draft.renderGif ?? true}
                onclick={() => handleToggle('renderGif')}
              >
                <span class="toggle-handle"></span>
              </button>
            </div>
          </div>

          <div class="setting-row setting-row-highlight">
            <div class="setting-meta">
              <div class="setting-title-with-badge">
                <label for="setting-enable-video" class="setting-title">Omni / Veo Video AI Loops</label>
                <span class="cost-badge">Paid API Tokens</span>
              </div>
              <p class="setting-desc">Generates dynamic generative AI background animations via Omni / Veo models.</p>
              {#if draft.enableVideoGeneration}
                <div class="cost-warning-alert">
                  <AlertTriangle size={13} />
                  <span>Notice: Generative AI video models consume paid API credits per generation.</span>
                </div>
              {/if}
            </div>
            <div class="setting-control">
              <button
                id="setting-enable-video"
                type="button"
                role="switch"
                aria-label="Toggle Omni and Veo Video AI Loops"
                aria-checked={draft.enableVideoGeneration ?? false}
                class="toggle-switch"
                class:toggle-active={draft.enableVideoGeneration ?? false}
                onclick={() => handleToggle('enableVideoGeneration')}
              >
                <span class="toggle-handle"></span>
              </button>
            </div>
          </div>
        </section>

        <!-- Section: Google Drive & Docs Storage -->
        <section class="setting-group">
          <div class="group-header">
            <HardDrive size={14} />
            <h3>Google Drive & Docs Storage</h3>
          </div>

          <div class="setting-row">
            <div class="setting-meta">
              <label for="setting-drive-folder" class="setting-title">Target Folder URL / ID</label>
              <p class="setting-desc">Folder on Google Drive where generated expense reports and docs are stored.</p>
            </div>
            <div class="setting-control setting-control-column">
              <input
                id="setting-drive-folder"
                type="text"
                value={driveFolderInputRaw}
                oninput={(e) => handleTextInput('googleDriveFolderId', e)}
                placeholder="https://drive.google.com/drive/folders/... or Folder ID"
                class="ide-input ide-input-wide"
                class:input-invalid={driveFolderError}
              />
              {#if driveFolderError}
                <div class="input-error-msg">
                  <AlertCircle size={12} />
                  <span>{driveFolderError}</span>
                </div>
              {:else if draft.googleDriveFolderId && draft.googleDriveFolderId !== driveFolderInputRaw}
                <div class="input-success-msg">
                  <Check size={12} />
                  <span>Resolved Folder ID: <code>{draft.googleDriveFolderId}</code></span>
                </div>
              {/if}
            </div>
          </div>

          <div class="setting-row">
            <div class="setting-meta">
              <label for="setting-doc-template" class="setting-title">Custom Template URL / ID</label>
              <p class="setting-desc">Custom Google Docs template. Leave empty to use the default GDG template.</p>
            </div>
            <div class="setting-control setting-control-column">
              <input
                id="setting-doc-template"
                type="text"
                value={templateInputRaw}
                oninput={(e) => handleTextInput('googleDocsTemplateId', e)}
                placeholder="https://docs.google.com/document/d/... (optional)"
                class="ide-input ide-input-wide"
                class:input-invalid={templateError}
              />
              {#if templateError}
                <div class="input-error-msg">
                  <AlertCircle size={12} />
                  <span>{templateError}</span>
                </div>
              {:else if draft.googleDocsTemplateId && draft.googleDocsTemplateId !== templateInputRaw}
                <div class="input-success-msg">
                  <Check size={12} />
                  <span>Resolved Template ID: <code>{draft.googleDocsTemplateId}</code></span>
                </div>
              {/if}
            </div>
          </div>

          <!-- Collapsible Template Guide Accordion -->
          <div class="template-guide-container">
            <button 
              type="button" 
              class="guide-toggle-btn" 
              onclick={() => isTemplateGuideOpen = !isTemplateGuideOpen}
              aria-expanded={isTemplateGuideOpen}
            >
              <div class="guide-toggle-left">
                <FileText size={14} class="guide-icon" />
                <span class="guide-toggle-title">How to use your custom Google Docs template</span>
              </div>
              {#if isTemplateGuideOpen}
                <ChevronDown size={15} />
              {:else}
                <ChevronRight size={15} />
              {/if}
            </button>

            {#if isTemplateGuideOpen}
              <div class="guide-content-panel">
                <div class="guide-step">
                  <span class="step-num">1</span>
                  <div class="step-details">
                    <strong>Get the base template</strong>
                    <p>Open the standard expense template in Google Docs and make a copy to your Google Drive.</p>
                    <a href={DEFAULT_TEMPLATE_URL} target="_blank" rel="noreferrer" class="btn-guide-action">
                      <ExternalLink size={13} />
                      <span>Open Default Template</span>
                    </a>
                  </div>
                </div>

                <div class="guide-step">
                  <span class="step-num">2</span>
                  <div class="step-details">
                    <strong>Keep template placeholders intact</strong>
                    <p>When adjusting logos, typography, or styling, do not remove the existing placeholder tags so the agent can automatically fill in your expense tables, dates, and receipts.</p>
                  </div>
                </div>

                <div class="guide-step">
                  <span class="step-num">3</span>
                  <div class="step-details">
                    <strong>Template Access</strong>
                    <p>Ensure the custom template is in your own Google Drive or set to <em>"Anyone with the link can view"</em> so the agent can duplicate and populate it for your events.</p>
                  </div>
                </div>
              </div>
            {/if}
          </div>
        </section>
      </div>

      <!-- Clean Footer -->
      <footer class="dialog-footer">
        <span class="footer-hint">Settings are saved automatically to your workspace.</span>
        <button class="btn-done" onclick={handleDone}>Done</button>
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
    max-width: 520px;
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
    background: var(--bg-surface);
  }

  .header-title-area {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .header-title-area :global(.header-icon) {
    color: var(--primary-accent);
  }

  .header-title-area h2 {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
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
    gap: 18px;
  }

  .setting-group {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .group-header {
    display: flex;
    align-items: center;
    gap: 6px;
    color: var(--text-tertiary);
    margin-bottom: 4px;
    padding-bottom: 4px;
    border-bottom: 1px solid var(--border-subtle);
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
    padding: 8px 10px;
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

  .setting-control-column {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 5px;
  }

  /* Toggle Switch */
  .toggle-switch {
    width: 38px;
    height: 22px;
    border-radius: 12px;
    background: var(--bg-surface-elevated, #2a2b2e);
    border: 1px solid var(--border-medium, #444);
    padding: 2px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    transition: background var(--transition-fast), border-color var(--transition-fast);
    outline: none;
    position: relative;
  }

  .toggle-switch:focus-visible {
    box-shadow: 0 0 0 2px var(--primary-accent-container);
  }

  .toggle-switch.toggle-active {
    background: var(--primary-accent, #4285F4);
    border-color: var(--primary-accent, #4285F4);
  }

  .toggle-handle {
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: #ffffff;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.35);
    transition: transform var(--transition-fast);
    transform: translateX(0);
  }

  .toggle-switch.toggle-active .toggle-handle {
    transform: translateX(16px);
  }

  .setting-title-with-badge {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .cost-badge {
    font-size: 10px;
    font-weight: 600;
    color: var(--status-warning, #f59e0b);
    background: rgba(245, 158, 11, 0.12);
    border: 1px solid rgba(245, 158, 11, 0.25);
    padding: 1px 6px;
    border-radius: var(--radius-pill);
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .cost-warning-alert {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 6px;
    padding: 6px 8px;
    background: rgba(245, 158, 11, 0.08);
    border: 1px solid rgba(245, 158, 11, 0.2);
    border-radius: var(--radius-sm);
    color: #f59e0b;
    font-size: 11px;
    line-height: 1.35;
  }

  /* Input */
  .ide-input {
    width: 200px;
    background: var(--bg-app);
    border: 1px solid var(--border-subtle);
    color: var(--text-primary);
    padding: 6px 10px;
    border-radius: var(--radius-sm);
    font-size: 12.5px;
    outline: none;
    transition: var(--transition-fast);
  }

  .ide-input-wide {
    width: 240px;
  }

  .ide-input:focus {
    border-color: var(--primary-accent);
    box-shadow: 0 0 0 2px var(--primary-accent-container);
  }

  .ide-input.input-invalid {
    border-color: #ef4444;
  }

  .ide-input.input-invalid:focus {
    box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.2);
  }

  .input-error-msg {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    color: #ef4444;
    max-width: 240px;
    text-align: right;
    line-height: 1.3;
  }

  .input-success-msg {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    color: #34a853;
    max-width: 240px;
    text-align: right;
  }

  .input-success-msg code {
    font-family: var(--font-mono, monospace);
    background: rgba(52, 168, 83, 0.12);
    padding: 1px 4px;
    border-radius: 4px;
  }

  /* Template Guide Accordion */
  .template-guide-container {
    margin-top: 10px;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    background: var(--bg-surface);
    overflow: hidden;
  }

  .guide-toggle-btn {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 14px;
    background: transparent;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
    transition: var(--transition-fast);
    text-align: left;
  }

  .guide-toggle-btn:hover {
    background: var(--bg-surface-elevated);
    color: var(--text-primary);
  }

  .guide-toggle-left {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .guide-toggle-left :global(.guide-icon) {
    color: var(--primary-accent);
  }

  .guide-toggle-title {
    font-weight: 500;
  }

  .guide-content-panel {
    padding: 14px 16px;
    background: var(--bg-app);
    border-top: 1px solid var(--border-subtle);
    display: flex;
    flex-direction: column;
    gap: 14px;
    animation: fadeIn 0.15s ease-out;
  }

  .guide-step {
    display: flex;
    align-items: flex-start;
    gap: 12px;
  }

  .step-num {
    flex-shrink: 0;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: var(--primary-accent-container);
    color: var(--primary-accent-text);
    font-size: 11px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .step-details {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .step-details strong {
    font-size: 12.5px;
    color: var(--text-primary);
  }

  .step-details p {
    font-size: 11.5px;
    color: var(--text-secondary);
    margin: 0;
    line-height: 1.4;
  }

  .btn-guide-action {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    margin-top: 6px;
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    color: var(--primary-accent);
    padding: 5px 10px;
    border-radius: var(--radius-sm);
    font-size: 11.5px;
    font-weight: 500;
    text-decoration: none;
    width: fit-content;
    transition: var(--transition-fast);
  }

  .btn-guide-action:hover {
    background: var(--primary-accent-container);
    color: var(--primary-accent-text);
    border-color: var(--primary-accent);
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
