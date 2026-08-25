<script>
  import { 
    Film, 
    Image as ImageIcon, 
    Download, 
    Check, 
    Play, 
    Sparkles, 
    ExternalLink, 
    Loader2,
    Maximize2
  } from '@lucide/svelte';
  import { downloadDirectFile, renderMarkdown } from './constants.js';

  let { media, rawText = '' } = $props();

  let activeTab = $state(media.videoUrl ? 'video' : (media.gifUrl ? 'gif' : 'poster'));
  let downloadingMap = $state({});
  let videoElement = $state();
  let isPlaying = $state(false);

  async function handleDownload(url, filename, key) {
    if (!url) return;
    downloadingMap = { ...downloadingMap, [key]: true };
    try {
      await downloadDirectFile(url, filename);
    } finally {
      setTimeout(() => {
        downloadingMap = { ...downloadingMap, [key]: false };
      }, 1200);
    }
  }

  function toggleFullscreen() {
    if (!videoElement) return;
    if (videoElement.requestFullscreen) {
      videoElement.requestFullscreen();
    } else if (videoElement.webkitRequestFullscreen) {
      videoElement.webkitRequestFullscreen();
    }
  }
</script>

<div class="a2ui-video-container">
  <!-- Top Header Banner -->
  <div class="video-card-header">
    <div class="header-badge-row">
      <div class="a2ui-chip">
        <Sparkles size={13} class="chip-sparkle" />
        <span>A2UI Interactive Video Player</span>
      </div>
      <div class="format-spec-tag">9:16 Vertical • 1080p</div>
    </div>

    {#if media.speakerName || media.talkTitle}
      <div class="speaker-meta-hero">
        {#if media.speakerName}
          <h3 class="hero-speaker-name">{media.speakerName}</h3>
        {/if}
        {#if media.company}
          <div class="hero-company-tag">{media.company}</div>
        {/if}
        {#if media.talkTitle}
          <p class="hero-talk-title">"{media.talkTitle}"</p>
        {/if}
      </div>
    {/if}
  </div>

  <!-- Format Switcher Tabs -->
  <div class="media-tabs-bar">
    {#if media.videoUrl}
      <button 
        class="media-tab-btn" 
        class:active={activeTab === 'video'} 
        onclick={() => activeTab = 'video'}
      >
        <Film size={14} />
        <span>1080p Video</span>
      </button>
    {/if}

    {#if media.gifUrl}
      <button 
        class="media-tab-btn" 
        class:active={activeTab === 'gif'} 
        onclick={() => activeTab = 'gif'}
      >
        <ImageIcon size={14} />
        <span>Animated GIF</span>
      </button>
    {/if}

    {#if media.posterUrl}
      <button 
        class="media-tab-btn" 
        class:active={activeTab === 'poster'} 
        onclick={() => activeTab = 'poster'}
      >
        <ImageIcon size={14} />
        <span>Card Poster</span>
      </button>
    {/if}

    {#if media.avatarUrl}
      <button 
        class="media-tab-btn" 
        class:active={activeTab === 'avatar'} 
        onclick={() => activeTab = 'avatar'}
      >
        <ImageIcon size={14} />
        <span>Outpainted Avatar</span>
      </button>
    {/if}
  </div>

  <!-- Interactive Media Viewport Area -->
  <div class="media-stage-wrapper">
    {#if activeTab === 'video' && media.videoUrl}
      <div class="video-player-box">
        <video 
          bind:this={videoElement}
          src={media.videoUrl} 
          controls 
          autoplay 
          loop 
          muted 
          playsinline 
          class="stage-video"
          poster={media.posterUrl || ''}
          onplay={() => isPlaying = true}
          onpause={() => isPlaying = false}
        >
          <track kind="captions" />
        </video>
        <button class="fullscreen-overlay-btn" onclick={toggleFullscreen} title="Fullscreen View">
          <Maximize2 size={16} />
        </button>
      </div>
    {:else if activeTab === 'gif' && media.gifUrl}
      <div class="image-preview-box">
        <img src={media.gifUrl} alt="Animated Speaker Card GIF" class="stage-image" />
      </div>
    {:else if activeTab === 'poster' && media.posterUrl}
      <div class="image-preview-box">
        <img src={media.posterUrl} alt="High Resolution Card Poster" class="stage-image" />
      </div>
    {:else if activeTab === 'avatar' && media.avatarUrl}
      <div class="image-preview-box avatar-box">
        <img src={media.avatarUrl} alt="Outpainted Portrait Avatar" class="stage-image stage-avatar" />
      </div>
    {/if}
  </div>

  <!-- Action Toolbar: Direct Downloads with Status -->
  <div class="media-download-toolbar">
    <div class="toolbar-title">
      <Download size={14} />
      <span>Download Generated Assets:</span>
    </div>

    <div class="download-buttons-grid">
      {#if media.videoUrl}
        <button 
          class="download-btn btn-mp4"
          disabled={downloadingMap['video']}
          onclick={() => handleDownload(media.videoUrl, `${media.speakerName || 'speaker'}_video_1080p.mp4`, 'video')}
          title="Direct download 1080p MP4 Video"
        >
          {#if downloadingMap['video']}
            <Loader2 size={15} class="spin-icon" />
            <span>Downloading MP4...</span>
          {:else}
            <Film size={15} />
            <span>Download MP4 Video</span>
          {/if}
        </button>
      {/if}

      {#if media.gifUrl}
        <button 
          class="download-btn btn-gif"
          disabled={downloadingMap['gif']}
          onclick={() => handleDownload(media.gifUrl, `${media.speakerName || 'speaker'}_card.gif`, 'gif')}
          title="Direct download Animated GIF"
        >
          {#if downloadingMap['gif']}
            <Loader2 size={15} class="spin-icon" />
            <span>Downloading GIF...</span>
          {:else}
            <ImageIcon size={15} />
            <span>Download GIF</span>
          {/if}
        </button>
      {/if}

      {#if media.posterUrl}
        <button 
          class="download-btn btn-poster"
          disabled={downloadingMap['poster']}
          onclick={() => handleDownload(media.posterUrl, `${media.speakerName || 'speaker'}_poster.png`, 'poster')}
          title="Direct download Card Poster PNG"
        >
          {#if downloadingMap['poster']}
            <Loader2 size={15} class="spin-icon" />
            <span>Downloading Poster...</span>
          {:else}
            <ImageIcon size={15} />
            <span>Download Poster (PNG)</span>
          {/if}
        </button>
      {/if}

      {#if media.avatarUrl}
        <button 
          class="download-btn btn-avatar"
          disabled={downloadingMap['avatar']}
          onclick={() => handleDownload(media.avatarUrl, `${media.speakerName || 'speaker'}_avatar.png`, 'avatar')}
          title="Direct download Outpainted Avatar PNG"
        >
          {#if downloadingMap['avatar']}
            <Loader2 size={15} class="spin-icon" />
            <span>Downloading Avatar...</span>
          {:else}
            <ImageIcon size={15} />
            <span>Download Avatar (PNG)</span>
          {/if}
        </button>
      {/if}
    </div>
  </div>
</div>

<style>
  .a2ui-video-container {
    background: var(--bg-surface-elevated, #1a1a24);
    border: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.1));
    border-radius: var(--radius-lg, 16px);
    overflow: hidden;
    margin-top: 14px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
    display: flex;
    flex-direction: column;
    width: 100%;
    animation: fadeIn 0.3s ease-out;
  }

  .video-card-header {
    padding: 16px 20px;
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.04) 0%, transparent 100%);
    border-bottom: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.08));
  }

  .header-badge-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
  }

  .a2ui-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(234, 67, 53, 0.15);
    color: var(--agent-video, #ea4335);
    border: 1px solid rgba(234, 67, 53, 0.3);
    padding: 4px 12px;
    border-radius: var(--radius-full, 9999px);
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  :global(.chip-sparkle) {
    animation: spinSlow 6s linear infinite;
  }

  .format-spec-tag {
    font-size: 11px;
    color: var(--text-secondary, #9aa0a6);
    font-weight: 500;
    background: var(--bg-surface, #121218);
    padding: 3px 10px;
    border-radius: var(--radius-full, 9999px);
    border: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.06));
  }

  .speaker-meta-hero {
    margin-top: 6px;
  }

  .hero-speaker-name {
    font-size: 18px;
    font-weight: 700;
    color: var(--text-primary, #ffffff);
    margin: 0 0 4px 0;
  }

  .hero-company-tag {
    font-size: 12px;
    color: var(--agent-video, #ea4335);
    font-weight: 600;
    margin-bottom: 4px;
  }

  .hero-talk-title {
    font-size: 13px;
    color: var(--text-secondary, #bdc1c6);
    margin: 0;
    font-style: italic;
  }

  /* Format Switcher Tabs */
  .media-tabs-bar {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 10px 16px;
    background: rgba(0, 0, 0, 0.2);
    border-bottom: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.06));
    overflow-x: auto;
  }

  .media-tab-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    border-radius: var(--radius-full, 9999px);
    border: 1px solid transparent;
    background: transparent;
    color: var(--text-secondary, #9aa0a6);
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
    white-space: nowrap;
  }

  .media-tab-btn:hover {
    background: var(--bg-hover, rgba(255, 255, 255, 0.06));
    color: var(--text-primary, #ffffff);
  }

  .media-tab-btn.active {
    background: var(--agent-video, #ea4335);
    color: #ffffff;
    box-shadow: 0 2px 8px rgba(234, 67, 53, 0.35);
  }

  /* Media Stage Viewport */
  .media-stage-wrapper {
    display: flex;
    justify-content: center;
    align-items: center;
    background: #000000;
    padding: 24px 16px;
    min-height: 380px;
    max-height: 520px;
  }

  .video-player-box {
    position: relative;
    max-height: 480px;
    display: flex;
    justify-content: center;
    align-items: center;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
  }

  .stage-video {
    max-height: 480px;
    max-width: 100%;
    aspect-ratio: 9 / 16;
    border-radius: 12px;
    background: #000000;
    outline: none;
  }

  .fullscreen-overlay-btn {
    position: absolute;
    top: 12px;
    right: 12px;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(8px);
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.2);
    width: 34px;
    height: 34px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    opacity: 0.8;
    transition: all 0.2s ease;
  }

  .fullscreen-overlay-btn:hover {
    opacity: 1;
    transform: scale(1.1);
    background: rgba(0, 0, 0, 0.85);
  }

  .image-preview-box {
    max-height: 480px;
    display: flex;
    justify-content: center;
    align-items: center;
  }

  .stage-image {
    max-height: 480px;
    max-width: 100%;
    aspect-ratio: 9 / 16;
    border-radius: 12px;
    object-fit: contain;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
  }

  .avatar-box .stage-avatar {
    aspect-ratio: 1 / 1;
    border-radius: 50%;
    max-height: 320px;
  }

  /* Download Toolbar */
  .media-download-toolbar {
    padding: 16px 20px;
    background: var(--bg-surface, #121218);
    border-top: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.08));
  }

  .toolbar-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary, #9aa0a6);
    margin-bottom: 12px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .download-buttons-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 10px;
  }

  .download-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 10px 16px;
    border-radius: var(--radius-full, 9999px);
    font-size: 13px;
    font-weight: 600;
    border: 1px solid transparent;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .download-btn:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.3);
  }

  .download-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .btn-mp4 {
    background: var(--agent-video, #ea4335);
    color: #ffffff;
    border-color: rgba(234, 67, 53, 0.4);
  }

  .btn-mp4:hover:not(:disabled) {
    background: #d33426;
  }

  .btn-gif {
    background: rgba(234, 67, 53, 0.12);
    color: var(--agent-video, #ea4335);
    border-color: rgba(234, 67, 53, 0.3);
  }

  .btn-gif:hover:not(:disabled) {
    background: rgba(234, 67, 53, 0.22);
  }

  .btn-poster, .btn-avatar {
    background: var(--bg-surface-elevated, #1f1f2e);
    color: var(--text-primary, #ffffff);
    border-color: var(--border-subtle, rgba(255, 255, 255, 0.15));
  }

  .btn-poster:hover:not(:disabled), .btn-avatar:hover:not(:disabled) {
    background: var(--bg-hover, rgba(255, 255, 255, 0.12));
    border-color: var(--primary-accent, #8ab4f8);
  }

  :global(.spin-icon) {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  @keyframes spinSlow {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(6px); }
    to { opacity: 1; transform: translateY(0); }
  }
</style>
