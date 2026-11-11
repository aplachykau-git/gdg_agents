<script>
  // Rounded QR code from the qr_code_generator agent: preview + flat SVG / PNG downloads.
  import { Check, Copy, Download, ExternalLink, Loader2, QrCode } from '@lucide/svelte';
  import { downloadDirectFile } from './constants.js';
  import ResultCard from './ui/ResultCard.svelte';

  let { qr = {} } = $props();

  let downloading = $state('');
  let copied = $state(false);

  const host = $derived.by(() => {
    try {
      const url = new URL(qr.link);
      return (url.host + url.pathname).replace(/\/$/, '');
    } catch {
      return qr.link || '';
    }
  });
  const isUrl = $derived(/^https?:\/\//i.test(qr.link || ''));

  async function download(kind) {
    const url = kind === 'svg' ? qr.svgUrl : qr.pngUrl;
    if (!url) return;
    downloading = kind;
    try {
      await downloadDirectFile(url, `${qr.filename}.${kind}`);
    } finally {
      setTimeout(() => (downloading = ''), 600);
    }
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(qr.link);
      copied = true;
      setTimeout(() => (copied = false), 2000);
    } catch (e) {
      console.warn('Copy failed', e);
    }
  }
</script>

{#if qr?.pngUrl || qr?.svgUrl}
  <ResultCard accent="var(--agent-qr)" accentBg="var(--bg-qr)" icon={QrCode} title="QR code" subtitle={host} status="Ready">
    {#snippet media()}
      <div class="qr-preview" class:transparent={qr.transparent}>
        <img src={qr.pngUrl || qr.svgUrl} alt="QR code for {qr.link}" width="140" height="140" loading="lazy" />
      </div>
    {/snippet}

    <dl class="rc-facts">
      <dt>Link</dt>
      <dd class="qr-link">{qr.link}</dd>
      <dt>Colours</dt>
      <dd class="qr-colours">
        <span class="swatch" style="background: {qr.color}"></span>{qr.color}
        <span class="on">on</span>
        {#if qr.transparent}
          <span class="swatch checker"></span>transparent
        {:else}
          <span class="swatch" style="background: {qr.background}"></span>{qr.background}
        {/if}
      </dd>
      <dt>Files</dt>
      <dd>SVG vector for print and design, PNG 1024 px for slides and posts</dd>
    </dl>

    {#snippet actions()}
      <button class="rc-btn primary" disabled={!!downloading} onclick={() => download('svg')} title="Flat vector for print and design">
        {#if downloading === 'svg'}<Loader2 size={14} class="spin-icon" />{:else}<Download size={14} />{/if}
        SVG
      </button>
      <button class="rc-btn" disabled={!!downloading} onclick={() => download('png')} title="1024 px PNG for slides and posts">
        {#if downloading === 'png'}<Loader2 size={14} class="spin-icon" />{:else}<Download size={14} />{/if}
        PNG
      </button>
    {/snippet}

    {#snippet tools()}
      <button class="rc-btn ghost" onclick={copyLink} title="Copy link">
        {#if copied}<Check size={14} />Copied{:else}<Copy size={14} />Copy link{/if}
      </button>
      {#if isUrl}
        <a class="rc-btn ghost" href={qr.link} target="_blank" rel="noopener noreferrer" title="Open link">
          <ExternalLink size={14} />Open
        </a>
      {/if}
    {/snippet}
  </ResultCard>
{/if}

<style>
  .qr-preview {
    width: 140px;
    height: 140px;
    padding: 8px;
    box-sizing: border-box;
    border-radius: var(--radius-sm);
    background: #ffffff;
    border: 1px solid var(--border-subtle);
  }

  .qr-preview.transparent,
  .swatch.checker {
    background-color: #ffffff;
    background-image: linear-gradient(45deg, #e8eaed 25%, transparent 25%),
      linear-gradient(-45deg, #e8eaed 25%, transparent 25%),
      linear-gradient(45deg, transparent 75%, #e8eaed 75%),
      linear-gradient(-45deg, transparent 75%, #e8eaed 75%);
    background-size: 12px 12px;
    background-position: 0 0, 0 6px, 6px -6px, -6px 0;
  }

  .qr-preview img {
    display: block;
    width: 100%;
    height: 100%;
  }

  .qr-link {
    font-family: var(--font-family-mono);
    font-size: 12px;
  }

  .qr-colours {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    font-family: var(--font-family-mono);
    font-size: 12px;
  }

  .on {
    color: var(--text-tertiary);
    font-family: var(--font-family-base);
  }

  .swatch {
    width: 12px;
    height: 12px;
    border-radius: 3px;
    border: 1px solid var(--border-medium);
  }
</style>
