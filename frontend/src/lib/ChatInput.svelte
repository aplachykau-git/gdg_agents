<script>
  import { 
    Plus, 
    Square, 
    ArrowRight, 
    FileText,
    AlertCircle
  } from '@lucide/svelte';
  import { MAX_INPUT_TOKENS } from './constants.js';

  let {
    queryText = $bindable(''),
    stagedFiles = $bindable([]),
    isLoading = false,
    textareaElement = $bindable(),
    onSend = () => {},
    onStop = () => {}
  } = $props();

  const currentTokens = $derived(Math.ceil((queryText || '').length * 0.25));
  const isTokenLimitExceeded = $derived(currentTokens > MAX_INPUT_TOKENS);
  const canSend = $derived(
    !isLoading &&
    (queryText.trim().length > 0 || stagedFiles.length > 0) &&
    !isTokenLimitExceeded
  );

  function handleKeyPress(e) {
    if (e.key === 'Escape' && isLoading) {
      e.preventDefault();
      onStop();
      return;
    }
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey || !e.shiftKey)) {
      e.preventDefault();
      if (!canSend) {
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
        <Plus size={15} strokeWidth={2} class="chip-icon" />
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
            <button class="staged-del-btn" onclick={() => removeStagedFile(index)} aria-label="Remove attachment">&times;</button>
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
      placeholder="Type your prompt here..."
      rows="1"
      disabled={isLoading}
    ></textarea>

    <!-- Bottom Action Toolbar -->
    <div class="prompt-meta-bottom">
      <div class="prompt-quick-tags">
        {#if isTokenLimitExceeded}
          <span class="tag-hint tag-error">
            <AlertCircle size={12} class="tag-alert-icon" />
            Please trim your prompt below {MAX_INPUT_TOKENS.toLocaleString()} tokens
          </span>
        {/if}
      </div>

      <button 
        class="btn-run-gemini" 
        class:btn-stop-generating={isLoading}
        onclick={isLoading ? onStop : onSend} 
        disabled={!isLoading && !canSend}
        title={isLoading ? "Stop generation" : (canSend ? "Send prompt (Ctrl+Enter)" : "Type a prompt or attach files to send")}
        aria-label={isLoading ? "Stop generation" : "Send prompt"}
      >
        {#if isLoading}
          <Square size={13} fill="currentColor" strokeWidth={0} class="stop-square-icon" />
        {:else}
          <ArrowRight size={17} strokeWidth={2.2} class="run-arrow-icon" />
        {/if}
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
    animation: promptWrapperEntrance 0.35s cubic-bezier(0.16, 1, 0.3, 1) both;
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
    transition: border-color 0.25s cubic-bezier(0.2, 0, 0, 1),
                box-shadow 0.25s cubic-bezier(0.2, 0, 0, 1),
                background 0.25s cubic-bezier(0.2, 0, 0, 1),
                transform 0.25s cubic-bezier(0.2, 0, 0, 1);
    box-sizing: border-box;
    animation: promptBoxEntrance 0.45s cubic-bezier(0.16, 1, 0.3, 1) both,
               promptAmbientPulse 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.1s both;
  }

  .floating-prompt-box:focus-within {
    border-color: var(--border-focus);
    box-shadow: var(--shadow-elevation-3), var(--shadow-glow);
    background: var(--bg-surface-elevated);
    transform: translateY(-1px);
  }

  .prompt-meta-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    animation: promptChildSlideDown 0.35s cubic-bezier(0.16, 1, 0.3, 1) 0.06s both;
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
    transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1),
                background 0.15s ease,
                border-color 0.15s ease,
                color 0.15s ease,
                box-shadow 0.15s ease;
  }

  .chip-action-btn :global(.chip-icon) {
    transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
  }

  .chip-action-btn:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
    border-color: var(--border-focus);
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
  }

  .chip-action-btn:hover :global(.chip-icon) {
    transform: rotate(90deg);
  }

  .chip-action-btn:active {
    transform: scale(0.96) translateY(0);
  }

  /* Token telemetry */
  .token-telemetry {
    font-size: 11px;
    color: var(--text-tertiary);
    display: flex;
    align-items: center;
    gap: 4px;
    transition: color 0.2s ease;
  }

  .token-val {
    color: var(--text-secondary);
    font-weight: 600;
    transition: color 0.2s ease;
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
    animation: badgePopIn 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) both;
  }

  /* Staged files */
  .staged-media-row {
    display: flex;
    gap: 10px;
    overflow-x: auto;
    padding: 4px 0;
    animation: stagedRowSlide 0.25s cubic-bezier(0.16, 1, 0.3, 1) both;
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
    animation: stagedCardPopIn 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) both;
    transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
  }

  .staged-card:hover {
    transform: translateY(-1px);
    border-color: var(--border-medium);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  }

  .staged-img {
    width: 28px;
    height: 28px;
    object-fit: cover;
    border-radius: var(--radius-xs);
    transition: transform 0.2s ease;
  }

  .staged-card:hover .staged-img {
    transform: scale(1.05);
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
    transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1), color 0.15s ease;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  .staged-del-btn:hover {
    color: var(--accent-red, #ea4335);
    transform: scale(1.2) rotate(90deg);
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
    animation: promptChildFadeIn 0.35s cubic-bezier(0.16, 1, 0.3, 1) 0.1s both;
  }

  .prompt-meta-bottom {
    display: flex;
    align-items: center;
    justify-content: space-between;
    animation: promptChildSlideUp 0.35s cubic-bezier(0.16, 1, 0.3, 1) 0.14s both;
  }

  .prompt-quick-tags {
    display: flex;
    align-items: center;
  }

  .tag-hint {
    font-size: 11px;
    color: var(--text-tertiary);
    transition: color 0.2s ease;
  }

  .tag-error {
    color: var(--accent-red, #ea4335);
    font-weight: 500;
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }

  .btn-run-gemini {
    width: 36px;
    height: 36px;
    padding: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    border: 1px solid transparent;
    cursor: pointer;
    flex-shrink: 0;
    transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1),
                box-shadow 0.2s ease,
                background 0.2s ease,
                border-color 0.2s ease,
                color 0.2s ease,
                filter 0.2s ease,
                background 0.2s ease,
                opacity 0.2s ease;
    animation: promptBtnPopIn 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) 0.18s both;
  }

  .btn-run-gemini:not(:disabled) {
    background: var(--primary-gradient, var(--primary-accent));
    color: #ffffff;
    border-color: transparent;
    box-shadow: 0 2px 10px rgba(37, 99, 235, 0.3);
  }

  .btn-run-gemini :global(.run-arrow-icon) {
    transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1), color 0.2s ease;
  }

  .btn-run-gemini:hover:not(:disabled) {
    filter: brightness(1.1);
    transform: translateY(-1px) scale(1.06);
    box-shadow: 0 4px 14px rgba(37, 99, 235, 0.45);
  }

  .btn-run-gemini:hover:not(:disabled) :global(.run-arrow-icon) {
    transform: translateX(2px);
  }

  .btn-run-gemini:active:not(:disabled) {
    transform: translateY(0) scale(0.95);
    box-shadow: 0 2px 6px rgba(37, 99, 235, 0.3);
  }

  .btn-run-gemini:disabled {
    background: var(--bg-surface-elevated);
    color: var(--text-tertiary);
    border: 1px solid var(--border-subtle);
    box-shadow: none;
    cursor: not-allowed;
    pointer-events: none;
    opacity: 0.6;
  }

  .btn-run-gemini:disabled :global(.run-arrow-icon) {
    color: var(--text-tertiary);
    opacity: 0.75;
    transform: none;
  }

  /* Stop Generation Mode (Red Square) */
  .btn-run-gemini.btn-stop-generating {
    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
    box-shadow: 0 2px 12px rgba(239, 68, 68, 0.45);
    color: #ffffff;
    opacity: 1;
    cursor: pointer;
    border-radius: var(--radius-md, 8px);
  }

  .btn-run-gemini.btn-stop-generating:hover {
    filter: brightness(1.12);
    box-shadow: 0 4px 16px rgba(239, 68, 68, 0.65);
    transform: translateY(-1px) scale(1.08);
  }

  .btn-run-gemini.btn-stop-generating:active {
    transform: translateY(0) scale(0.94);
    box-shadow: 0 2px 6px rgba(239, 68, 68, 0.4);
  }

  .btn-run-gemini :global(.stop-square-icon) {
    animation: stopSquarePop 0.25s cubic-bezier(0.34, 1.56, 0.64, 1) both;
  }

  @keyframes stopSquarePop {
    0% {
      transform: scale(0.4);
      opacity: 0;
    }
    100% {
      transform: scale(1);
      opacity: 1;
    }
  }

  /* =========================================================================
   * Micro-animation Keyframes
   * ========================================================================= */
  @keyframes promptWrapperEntrance {
    0% {
      opacity: 0;
    }
    100% {
      opacity: 1;
    }
  }

  @keyframes promptBoxEntrance {
    0% {
      opacity: 0;
      transform: translateY(18px) scale(0.98);
      filter: blur(4px);
    }
    60% {
      filter: blur(0);
    }
    100% {
      opacity: 1;
      transform: translateY(0) scale(1);
      filter: blur(0);
    }
  }

  @keyframes promptAmbientPulse {
    0% {
      box-shadow: var(--shadow-elevation-2);
    }
    45% {
      box-shadow: var(--shadow-elevation-2), 0 0 16px rgba(59, 130, 246, 0.28);
    }
    100% {
      box-shadow: var(--shadow-elevation-2);
    }
  }

  @keyframes promptChildSlideDown {
    0% {
      opacity: 0;
      transform: translateY(-6px);
    }
    100% {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @keyframes promptChildFadeIn {
    0% {
      opacity: 0;
      transform: translateY(3px);
    }
    100% {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @keyframes promptChildSlideUp {
    0% {
      opacity: 0;
      transform: translateY(6px);
    }
    100% {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @keyframes promptBtnPopIn {
    0% {
      opacity: 0;
      transform: scale(0.85);
    }
    100% {
      opacity: 1;
      transform: scale(1);
    }
  }

  @keyframes stagedCardPopIn {
    0% {
      opacity: 0;
      transform: scale(0.84) translateY(6px);
    }
    100% {
      opacity: 1;
      transform: scale(1) translateY(0);
    }
  }

  @keyframes stagedRowSlide {
    0% {
      opacity: 0;
      transform: translateY(-4px);
    }
    100% {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @keyframes badgePopIn {
    0% {
      opacity: 0;
      transform: scale(0.7);
    }
    70% {
      transform: scale(1.08);
    }
    100% {
      opacity: 1;
      transform: scale(1);
    }
  }

  @keyframes spinSlow {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  /* Accessibility: Prefers Reduced Motion */
  @media (prefers-reduced-motion: reduce) {
    .floating-prompt-wrapper,
    .floating-prompt-box,
    .prompt-meta-top,
    textarea,
    .prompt-meta-bottom,
    .btn-run-gemini,
    .staged-card,
    .staged-media-row,
    .token-exceeded-badge {
      animation: none !important;
      transition: none !important;
      transform: none !important;
      filter: none !important;
    }
  }
</style>
