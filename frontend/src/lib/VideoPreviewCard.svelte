<script>
  import { 
    Film, 
    Image as ImageIcon, 
    Download, 
    Loader2,
    Folder,
    Copy,
    Check
  } from '@lucide/svelte';
  import { downloadDirectFile } from './constants.js';

  let { media = {} } = $props();

  let downloadingMap = $state({});
  let copiedPath = $state(false);

  const localFilePath = $derived.by(() => {
    if (media.rawVideoUrl && media.rawVideoUrl.startsWith('file://')) {
      return media.rawVideoUrl.replace('file://', '');
    }
    const cand = (media.allUrls || []).find(u => u.startsWith('file://'));
    if (cand) return cand.replace('file://', '');
    if (media.videoUrl && media.videoUrl.startsWith('/renders/')) {
      return `agents/video_editor/renders/${media.videoUrl.split('/').pop()}`;
    }
    return '';
  });

  async function handleDownload(url, filename, key) {
    if (!url) return;
    downloadingMap = { ...downloadingMap, [key]: true };
    try {
      await downloadDirectFile(url, filename);
    } finally {
      setTimeout(() => {
        downloadingMap = { ...downloadingMap, [key]: false };
      }, 1000);
    }
  }

  function copyFilePath(pathText) {
    if (!pathText) return;
    navigator.clipboard.writeText(pathText);
    copiedPath = true;
    setTimeout(() => {
      copiedPath = false;
    }, 2000);
  }
</script>

{#if media?.videoUrl || media?.gifUrl || media?.posterUrl}
  <div class="video-preview-wrapper">
    <!-- Video / Media Player Container -->
    <div class="video-player-container">
      {#if media.videoUrl}
        <video 
          controls 
          playsinline 
          preload="metadata"
          poster={media.posterUrl || ''}
          class="embedded-video"
        >
          <source src={media.videoUrl} type="video/mp4" />
          <track kind="captions" />
          Your browser does not support HTML5 video playback.
        </video>
      {:else if media.gifUrl || media.posterUrl}
        <img 
          src={media.gifUrl || media.posterUrl} 
          alt="Generated speaker card preview" 
          class="embedded-image" 
        />
      {/if}
    </div>

    <!-- Direct Download Buttons -->
    <div class="download-actions-row">
      {#if media.videoUrl}
        <button 
          class="download-pill-btn primary"
          disabled={downloadingMap['video']}
          onclick={() => handleDownload(media.videoUrl, 'speaker_video_1080p.mp4', 'video')}
          title="Direct download 1080p MP4 Video"
        >
          {#if downloadingMap['video']}
            <Loader2 size={14} class="spin-icon" />
            <span>Downloading...</span>
          {:else}
            <Film size={14} />
            <span>Download MP4 Video</span>
          {/if}
        </button>
      {/if}

      {#if media.gifUrl}
        <button 
          class="download-pill-btn secondary"
          disabled={downloadingMap['gif']}
          onclick={() => handleDownload(media.gifUrl, 'speaker_card.gif', 'gif')}
          title="Direct download Animated GIF"
        >
          {#if downloadingMap['gif']}
            <Loader2 size={14} class="spin-icon" />
            <span>Downloading...</span>
          {:else}
            <ImageIcon size={14} />
            <span>Download GIF</span>
          {/if}
        </button>
      {/if}

      {#if media.posterUrl}
        <button 
          class="download-pill-btn secondary"
          disabled={downloadingMap['poster']}
          onclick={() => handleDownload(media.posterUrl, 'speaker_poster.png', 'poster')}
          title="Direct download Card Poster PNG"
        >
          {#if downloadingMap['poster']}
            <Loader2 size={14} class="spin-icon" />
            <span>Downloading...</span>
          {:else}
            <ImageIcon size={14} />
            <span>Download Poster</span>
          {/if}
        </button>
      {/if}
    </div>

    {#if localFilePath}
      <div class="local-path-badge">
        <Folder size={13} class="path-icon" />
        <span class="path-text" title={localFilePath}>{localFilePath}</span>
        <button 
          class="copy-path-btn" 
          onclick={() => copyFilePath(localFilePath)}
          title="Copy local path"
          aria-label="Copy local path"
        >
          {#if copiedPath}
            <Check size={12} color="#34a853" />
          {:else}
            <Copy size={12} />
          {/if}
        </button>
      </div>
    {/if}
  </div>
{/if}

<style>
  .video-preview-wrapper {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-top: 14px;
    width: 100%;
    animation: fadeIn 0.25s ease-out;
  }

  .video-player-container {
    display: flex;
    justify-content: flex-start;
    align-items: center;
    width: 100%;
    border-radius: 12px;
    overflow: hidden;
  }

  .embedded-video {
    max-width: 100%;
    max-height: 480px;
    width: auto;
    height: auto;
    border-radius: 12px;
    background: #000000;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
    outline: none;
  }

  .embedded-image {
    max-width: 100%;
    max-height: 480px;
    width: auto;
    height: auto;
    border-radius: 12px;
    object-fit: contain;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
  }

  .download-actions-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }

  .download-pill-btn {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 8px 16px;
    border-radius: var(--radius-full, 9999px);
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
    border: 1px solid transparent;
  }

  .download-pill-btn:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
  }

  .download-pill-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .download-pill-btn.primary {
    background: var(--agent-video, #ea4335);
    color: #ffffff;
  }

  .download-pill-btn.primary:hover:not(:disabled) {
    background: #d33426;
  }

  .download-pill-btn.secondary {
    background: var(--bg-surface-elevated, #242436);
    color: var(--text-primary, #ffffff);
    border-color: var(--border-subtle, rgba(255, 255, 255, 0.12));
  }

  .download-pill-btn.secondary:hover:not(:disabled) {
    background: var(--bg-hover, rgba(255, 255, 255, 0.1));
    border-color: var(--primary-accent, #8ab4f8);
  }

  .local-path-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.1));
    border-radius: 8px;
    font-size: 12px;
    color: var(--text-secondary, #9aa0a6);
    max-width: 100%;
    font-family: var(--font-mono, monospace);
  }

  :global(.path-icon) {
    flex-shrink: 0;
    color: var(--agent-video, #ea4335);
  }

  .path-text {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .copy-path-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    border: none;
    cursor: pointer;
    padding: 2px 4px;
    border-radius: 4px;
    color: var(--text-secondary, #9aa0a6);
    transition: all 0.15s ease;
    flex-shrink: 0;
  }

  .copy-path-btn:hover {
    color: var(--text-primary, #ffffff);
    background: rgba(255, 255, 255, 0.08);
  }
</style>
