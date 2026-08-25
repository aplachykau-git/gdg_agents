<script>
  import { Copy, Check, RefreshCw } from '@lucide/svelte';
  import { renderMarkdown } from './constants.js';

  let { variants = [], onRefine = () => {} } = $props();

  let copiedId = $state('');

  function copyToClipboard(text, id) {
    if (!navigator.clipboard) return;
    navigator.clipboard.writeText(text).then(() => {
      copiedId = id;
      setTimeout(() => {
        if (copiedId === id) copiedId = '';
      }, 2000);
    }).catch(err => {
      console.error('Failed to copy to clipboard:', err);
    });
  }
</script>

<div class="variants-deck">
  {#each variants as variant, vIdx}
    <div class="variant-item-card">
      <div class="variant-top-bar">
        <span class="variant-tag">{variant.header || 'Option'}</span>
        <div class="variant-actions">
          {#if (variant.header || '').toLowerCase() !== 'introduction'}
            <button class="variant-btn" onclick={() => copyToClipboard(variant.body, 'v_' + vIdx)}>
              {#if copiedId === 'v_' + vIdx}
                <Check size={13} />
                <span>Copied</span>
              {:else}
                <Copy size={13} />
                <span>Copy</span>
              {/if}
            </button>
            <button class="variant-btn refine-btn" onclick={() => onRefine(variant.body)}>
              <RefreshCw size={13} />
              <span>Refine</span>
            </button>
          {/if}
        </div>
      </div>
      <div class="variant-markdown markdown-body">
        {@html renderMarkdown(variant.body)}
      </div>
    </div>
  {/each}
</div>

<style>
  .variants-deck {
    display: flex;
    flex-direction: column;
    gap: 16px;
    margin-top: 10px;
    width: 100%;
  }

  .variant-item-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: 16px;
    transition: var(--transition-normal);
  }

  .variant-item-card:hover {
    border-color: var(--border-focus);
    box-shadow: var(--shadow-sm);
  }

  .variant-top-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border-subtle);
  }

  .variant-tag {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--primary-accent);
    background: var(--primary-accent-container);
    padding: 3px 8px;
    border-radius: var(--radius-full);
  }

  .variant-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .variant-btn {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 12px;
    font-weight: 500;
    padding: 4px 10px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border-subtle);
    background: var(--bg-surface-elevated);
    color: var(--text-secondary);
    cursor: pointer;
    transition: var(--transition-fast);
  }

  .variant-btn:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
    border-color: var(--border-focus);
  }

  .refine-btn:hover {
    color: var(--primary-accent);
  }
</style>
