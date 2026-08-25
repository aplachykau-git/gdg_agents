<script>
  import { 
    Plus, 
    Sparkles, 
    CornerDownLeft, 
    FileText 
  } from '@lucide/svelte';
  import { MAX_INPUT_TOKENS } from './constants.js';

  let {
    queryText = $bindable(''),
    stagedFiles = $bindable([]),
    isLoading = false,
    textareaElement = $bindable(),
    onSend = () => {}
  } = $props();

  const currentTokens = $derived(Math.ceil((queryText || '').length * 0.25));
  const isTokenLimitExceeded = $derived(currentTokens > MAX_INPUT_TOKENS);

  function handleKeyPress(e) {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey || !e.shiftKey)) {
      e.preventDefault();
      if (isLoading || (!queryText.trim() && stagedFiles.length === 0) || isTokenLimitExceeded) {
        return;
      }
      onSend();
    }
  }

  function handleFileSelect(e) {
    const files = e.target.files;
    if (files && files.length > 0) {
      Array.from(files).forEach(file => processFile(file));
    }
    e.target.value = '';
  }

  function processFile(file) {
    const isImage = file.type.startsWith('image/');
    const reader = new FileReader();
    reader.onload = (event) => {
      const dataUrl = event.target.result;
      const base64Data = dataUrl.split(',')[1];
      stagedFiles = [
        ...stagedFiles,
        {
          name: file.name,
          type: file.type || 'application/octet-stream',
          data: base64Data,
          preview: isImage ? dataUrl : null
        }
      ];
    };
    reader.readAsDataURL(file);
  }

  function removeStagedFile(index) {
    stagedFiles = stagedFiles.filter((_, i) => i !== index);
  }
</script>

<div class="floating-prompt-wrapper">
  <div class="floating-prompt-box">
    <!-- Top Attachment & Context Strip -->
    <div class="prompt-meta-top">
      <label class="chip-action-btn" title="Add Multimodal Attachments">
        <Plus size={15} strokeWidth={2} />
        <span>Add files</span>
        <input type="file" multiple onchange={handleFileSelect} style="display: none;" />
      </label>

      <div class="token-telemetry" class:token-limit-warning={isTokenLimitExceeded}>
        <span class="token-val" class:token-val-exceeded={isTokenLimitExceeded}>{currentTokens.toLocaleString()}</span>
        <span class="token-max">/ {MAX_INPUT_TOKENS.toLocaleString()} tokens</span>
        {#if isTokenLimitExceeded}
          <span class="token-exceeded-badge">Limit Exceeded</span>
        {/if}
      </div>
    </div>

    <!-- Staged Attachments Carousel -->
    {#if stagedFiles.length > 0}
      <div class="staged-media-row">
        {#each stagedFiles as file, index}
          <div class="staged-card">
            {#if file.preview}
              <img class="staged-img" src={file.preview} alt="staged upload" />
            {:else}
              <FileText size={20} class="staged-doc-icon" />
            {/if}
            <span class="staged-filename">{file.name}</span>
            <button class="staged-del-btn" onclick={() => removeStagedFile(index)}>&times;</button>
          </div>
        {/each}
      </div>
    {/if}

    <!-- Textarea Field -->
    <textarea 
      bind:this={textareaElement}
      bind:value={queryText}
      onkeydown={handleKeyPress}
      oninput={(e) => {
        const target = e.target;
        target.style.height = 'auto';
        target.style.height = (target.scrollHeight) + 'px';
      }}
      placeholder="Type your prompt here, or press Ctrl+Enter to execute..."
      rows="1"
      disabled={isLoading}
    ></textarea>

    <!-- Bottom Action Toolbar -->
    <div class="prompt-meta-bottom">
      <div class="prompt-quick-tags">
        {#if isTokenLimitExceeded}
          <span class="tag-hint tag-error">⚠️ Please trim your prompt below {MAX_INPUT_TOKENS.toLocaleString()} tokens</span>
        {:else}
          <span class="tag-hint">Ctrl + ↵ to Run</span>
        {/if}
      </div>

      <button 
        class="btn-run-gemini" 
        onclick={onSend} 
        disabled={isLoading || (!queryText.trim() && stagedFiles.length === 0) || isTokenLimitExceeded}
      >
        <Sparkles size={16} strokeWidth={2} class={isLoading ? 'generating-sparkle' : ''} />
        <span>Run</span>
        <CornerDownLeft size={14} />
      </button>
    </div>
  </div>
</div>

<style>
  .floating-prompt-wrapper {
    padding: 12px 20px 24px;
    background: linear-gradient(180deg, transparent 0%, var(--bg-app) 35%);
    position: sticky;
    bottom: 0;
    z-index: 30;
    width: 100%;
    box-sizing: border-box;
  }

  .floating-prompt-box {
    max-width: 920px;
    width: 100%;
    margin: 0 auto;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-2xl);
    padding: 12px 18px;
    box-shadow: var(--shadow-elevation-2);
    display: flex;
    flex-direction: column;
    gap: 10px;
    transition: all 0.2s cubic-bezier(0.2, 0, 0, 1);
    box-sizing: border-box;
  }

  .floating-prompt-box:focus-within {
    border-color: rgba(138, 180, 248, 0.6);
    box-shadow: var(--shadow-elevation-3), var(--shadow-glow);
    background: var(--bg-surface-elevated);
  }

  .prompt-meta-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .chip-action-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 12px;
    border-radius: var(--radius-full);
    border: 1px solid var(--border-subtle);
    background: var(--bg-surface-elevated);
    color: var(--text-secondary);
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: var(--transition-fast);
  }

  .chip-action-btn:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
    border-color: var(--border-focus);
  }

  /* Token telemetry */
  .token-telemetry {
    font-size: 11px;
    color: var(--text-tertiary);
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .token-val {
    color: var(--text-secondary);
    font-weight: 600;
  }

  .token-val-exceeded {
    color: var(--accent-red, #ea4335);
  }

  .token-exceeded-badge {
    background: rgba(234, 67, 53, 0.15);
    color: var(--accent-red, #ea4335);
    font-size: 10px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: var(--radius-xs);
    margin-left: 4px;
  }

  /* Staged files */
  .staged-media-row {
    display: flex;
    gap: 10px;
    overflow-x: auto;
    padding: 4px 0;
  }

  .staged-card {
    position: relative;
    display: flex;
    align-items: center;
    gap: 8px;
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    padding: 6px 10px;
    border-radius: var(--radius-md);
    max-width: 200px;
  }

  .staged-img {
    width: 28px;
    height: 28px;
    object-fit: cover;
    border-radius: var(--radius-xs);
  }

  .staged-filename {
    font-size: 11px;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .staged-del-btn {
    background: none;
    border: none;
    color: var(--text-tertiary);
    font-size: 16px;
    cursor: pointer;
    line-height: 1;
    padding: 0 2px;
  }

  .staged-del-btn:hover {
    color: var(--accent-red, #ea4335);
  }

  textarea {
    width: 100%;
    background: transparent;
    border: none;
    color: var(--text-primary);
    font-size: 14px;
    line-height: 1.6;
    resize: none;
    outline: none;
    font-family: inherit;
    max-height: 200px;
    overflow-y: auto;
  }

  .prompt-meta-bottom {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .prompt-quick-tags {
    display: flex;
    align-items: center;
  }

  .tag-hint {
    font-size: 11px;
    color: var(--text-tertiary);
  }

  .tag-error {
    color: var(--accent-red, #ea4335);
    font-weight: 500;
  }

  .btn-run-gemini {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 18px;
    border-radius: var(--radius-full);
    border: none;
    background: var(--primary-accent);
    color: #0b0c0e;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: var(--transition-fast);
  }

  .btn-run-gemini:hover:not(:disabled) {
    filter: brightness(1.1);
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(138, 180, 248, 0.4);
  }

  .btn-run-gemini:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  :global(.generating-sparkle) {
    animation: spinSlow 3s linear infinite;
  }

  @keyframes spinSlow {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
</style>
