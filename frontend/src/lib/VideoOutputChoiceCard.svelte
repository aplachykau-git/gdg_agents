<script>
  // Choice step shown after speaker details + media are saved when the user has not yet
  // picked between a standalone static 4K cover photo (no video) or an animated video.
  import { Image as ImageIcon, Video } from '@lucide/svelte';
  import ResultCard from './ui/ResultCard.svelte';

  let { payload = {}, isBusy = false, onSend = () => {} } = $props();

  const speaker = $derived(payload.speaker || {});
  const mediaKind = $derived(payload.media_kind || 'image');
  const avatarUrl = $derived(payload.avatarUrl || '');
  const resolved = $derived(Boolean(payload.resolved));
  const disabled = $derived(isBusy || resolved);

  function chooseCoverOnly() {
    if (disabled) return;
    onSend('Create ONLY the static 4K cover photo (without creating or rendering any video).');
  }

  function chooseAnimatedVideo() {
    if (disabled) return;
    const msg =
      mediaKind === 'video'
        ? 'Proceed to rendering the animated speaker-card video.'
        : 'Proceed to animated video and propose 5 video scenarios.';
    onSend(msg);
  }
</script>

<ResultCard
  accent="var(--agent-video)"
  accentBg="var(--bg-video)"
  icon={Video}
  title="Choose card output"
  subtitle={speaker.name || 'Static 4K cover or animated video'}
  status={resolved ? 'Chosen' : 'Choose next step'}
  statusTone={resolved ? 'ok' : 'warn'}
>
  <div class="choice-layout" class:has-preview={Boolean(avatarUrl)}>
    {#if avatarUrl}
      <div class="portrait-preview">
        <img src={avatarUrl} alt="Outpainted 9:16 portrait preview" />
        <span class="portrait-caption">Outpainted 9:16 portrait</span>
      </div>
    {/if}
    <div class="choice-details">
      <dl class="rc-facts">
        {#if speaker.talk_title}
          <dt>Talk</dt>
          <dd>{speaker.talk_title}</dd>
        {/if}
        {#if speaker.name}
          <dt>Speaker</dt>
          <dd>{speaker.name}</dd>
        {/if}
        {#if speaker.position_company}
          <dt>Role</dt>
          <dd>{speaker.position_company}</dd>
        {/if}
      </dl>
      <p class="rc-muted choice-hint">
        Create only a static 4K cover photo (3840x2160 PNG) without any video step, or continue to animated video.
      </p>
    </div>
  </div>

  {#snippet actions()}
    <button type="button" class="rc-btn primary" {disabled} onclick={chooseCoverOnly}>
      <ImageIcon size={14} />
      <span>Create Static 4K Cover Only</span>
    </button>
    <button type="button" class="rc-btn" {disabled} onclick={chooseAnimatedVideo}>
      <Video size={14} />
      <span>Create Animated Video</span>
    </button>
  {/snippet}
</ResultCard>

<style>
  .choice-layout.has-preview {
    display: flex;
    gap: 14px;
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .choice-details {
    flex: 1 1 200px;
    min-width: 0;
  }

  .portrait-preview {
    display: flex;
    flex-direction: column;
    gap: 5px;
    flex: 0 0 auto;
    width: 112px;
  }

  .portrait-preview img {
    width: 112px;
    aspect-ratio: 9 / 16;
    object-fit: cover;
    border-radius: 10px;
    border: 1px solid var(--border);
    background: var(--bg-soft, rgba(128, 128, 128, 0.12));
  }

  .portrait-caption {
    font-size: 11px;
    color: var(--text-muted);
    text-align: center;
  }

  .choice-hint {
    margin: 10px 0 0;
  }
</style>

