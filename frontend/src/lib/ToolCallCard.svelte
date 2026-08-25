<script>
  import { Check, AlertCircle } from '@lucide/svelte';
  import { 
    getFriendlyToolCall, 
    getFriendlyToolResponse, 
    isToolResponseError 
  } from './constants.js';

  let { part } = $props();
</script>

{#if part.function_call || part.functionCall}
  {@const fc = part.function_call || part.functionCall}
  <div class="activity-step-chip">
    <div class="activity-pulse-dot"></div>
    <span class="activity-label">{getFriendlyToolCall(fc.name, fc.args)}</span>
  </div>
{/if}

{#if part.function_response || part.functionResponse}
  {@const fr = part.function_response || part.functionResponse}
  {@const isErr = isToolResponseError(fr.response)}
  <div class="activity-step-chip {isErr ? 'activity-error' : 'activity-done'}">
    {#if isErr}
      <AlertCircle size={13} class="activity-error-icon" />
    {:else}
      <Check size={13} class="activity-check-icon" />
    {/if}
    <span class="activity-label">{getFriendlyToolResponse(fr.name, fr.response)}</span>
  </div>
{/if}

<style>
  .activity-step-chip {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    padding: 6px 12px;
    border-radius: var(--radius-full);
    font-size: 12px;
    font-weight: 500;
    color: var(--text-secondary);
    margin: 4px 0;
    max-width: 100%;
    animation: fadeIn 0.2s ease-out;
  }

  .activity-pulse-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--primary-accent);
    box-shadow: 0 0 8px var(--primary-accent);
    animation: pulseGlow 1.5s infinite;
  }

  .activity-done {
    border-color: rgba(52, 168, 83, 0.3);
    background: rgba(52, 168, 83, 0.08);
    color: var(--text-primary);
  }

  :global(.activity-check-icon) {
    color: var(--accent-green, #34a853);
    flex-shrink: 0;
  }

  .activity-error {
    border-color: rgba(234, 67, 53, 0.3);
    background: rgba(234, 67, 53, 0.08);
    color: var(--accent-red, #ea4335);
  }

  :global(.activity-error-icon) {
    color: var(--accent-red, #ea4335);
    flex-shrink: 0;
  }

  .activity-label {
    word-break: break-word;
    line-height: 1.4;
  }

  @keyframes pulseGlow {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.4; transform: scale(0.85); }
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(2px); }
    to { opacity: 1; transform: translateY(0); }
  }
</style>
