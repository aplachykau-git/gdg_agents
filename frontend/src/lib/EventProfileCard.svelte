<script>
  // Event details card (payload type "event_profile"), shown by the Social Planner when the user
  // gives event details in the chat, asks to see or change them, or something is missing. The
  // user edits and saves here; the profile is remembered for future sessions (App.svelte).
  import { CalendarDays, Check, ChevronRight, Pencil } from '@lucide/svelte';
  import ResultCard from './ui/ResultCard.svelte';
  import SocialProfilesEditor from './ui/SocialProfilesEditor.svelte';
  import {
    DEFAULT_COUNTDOWN_PLAN,
    eventStatePayload,
    patchStudioConfig,
    profileToConfig,
    socialNetwork,
  } from './config.js';

  let { payload = {}, isBusy = false, onSend = () => {} } = $props();

  const missing = $derived(payload.missing || []);
  let editing = $state(false);
  let saved = $state(false);
  let draft = $state(null);

  $effect.pre(() => {
    if (draft === null) {
      const p = payload.profile || {};
      draft = {
        ...p,
        hashtags: (p.hashtags || []).join(' '),
        social_profiles: (p.social_profiles || []).map((s) => ({ ...s })),
        countdown: p.countdown || DEFAULT_COUNTDOWN_PLAN,
      };
      editing = missing.length > 0;
    }
  });

  const profile = $derived({
    ...(draft || {}),
    hashtags: String(draft?.hashtags || '').split(/[\s,;]+/).filter(Boolean),
    countdown: draft?.countdown === DEFAULT_COUNTDOWN_PLAN ? '' : draft?.countdown || '',
  });

  const daysLeft = $derived.by(() => {
    if (!profile.date) return null;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return Math.round((new Date(`${profile.date}T00:00:00`) - today) / 86400000);
  });
  const posting = $derived((profile.social_profiles || []).filter((p) => p.post && socialNetwork(p.network).plannable));
  const status = $derived(
    saved ? { text: 'Saved', tone: 'ok' } : missing.length ? { text: `Add ${missing.join(', ').replace('_', ' ')}`, tone: 'warn' } : payload.persist ? { text: 'Saved', tone: 'ok' } : { text: 'Current', tone: 'neutral' }
  );

  function save() {
    const config = profileToConfig(profile);
    patchStudioConfig({ ...config, eventProfileUpdatedAt: new Date().toISOString() });
    saved = true;
    editing = false;
    onSend('Saved the event details.', eventStatePayload(config));
  }

  const isMissing = (field) => missing.includes(field) && !saved;
</script>

{#if draft}
  <ResultCard accent="var(--agent-linkedin)" accentBg="var(--bg-linkedin)" icon={CalendarDays} title="Event details" subtitle={profile.name || 'Event'} status={status.text} statusTone={status.tone}>
    {#if editing}
      <div class="form">
        <label class="field">
          <span class="rc-label">Event name</span>
          <input class="input" bind:value={draft.name} placeholder="DevFest Kraków 2027" />
        </label>
        <label class="field" class:missing={isMissing('date')}>
          <span class="rc-label">Date{isMissing('date') ? ' (needed)' : ''}</span>
          <input class="input" type="date" bind:value={draft.date} />
        </label>
        <label class="field">
          <span class="rc-label">Website</span>
          <input class="input" type="url" bind:value={draft.website} placeholder="https://devfestkrakow.pl/" />
        </label>
        <label class="field">
          <span class="rc-label">Registration (optional)</span>
          <input class="input" type="url" bind:value={draft.registration_url} placeholder="https://gdg.community.dev/events/..." />
        </label>
        <label class="field wide">
          <span class="rc-label">Venue</span>
          <input class="input" bind:value={draft.venue} placeholder="Klaster Zabłocie 20.22, Kraków" />
        </label>
        <label class="field wide">
          <span class="rc-label">Highlights posts may use</span>
          <textarea class="input" rows="2" bind:value={draft.highlights} placeholder="2 stages, 15+ speakers, 4 workshops, free admission"></textarea>
        </label>
        <label class="field wide">
          <span class="rc-label">Hashtags (the first goes into every post)</span>
          <input class="input" bind:value={draft.hashtags} placeholder="#DevFestKrakow #GDGKrakow #GDG" />
        </label>
        <div class="field wide" class:missing={isMissing('social_profiles')}>
          <span class="rc-label">Social networks</span>
          <SocialProfilesEditor profiles={draft.social_profiles} highlight={isMissing('social_profiles')} onChange={(next) => (draft.social_profiles = next)} />
        </div>
        <details class="field wide">
          <summary class="rc-label"><ChevronRight size={12} class="chev" />Countdown sequence</summary>
          <textarea class="input mono" rows="6" bind:value={draft.countdown}></textarea>
          <span class="rc-muted">One line per post: "days before the event: topic".</span>
        </details>
      </div>
    {:else}
      <dl class="rc-facts">
        <dt>Date</dt>
        <dd>
          {profile.date || 'not set'}
          {#if daysLeft !== null}<span class="rc-chip {daysLeft >= 0 ? 'neutral' : 'warn'}">{daysLeft > 0 ? `${daysLeft} days to go` : daysLeft === 0 ? 'today' : 'passed'}</span>{/if}
        </dd>
        <dt>Website</dt>
        <dd>{profile.website}</dd>
        {#if profile.registration_url}<dt>Registration</dt><dd>{profile.registration_url}</dd>{/if}
        {#if profile.venue}<dt>Venue</dt><dd>{profile.venue}</dd>{/if}
        {#if profile.highlights}<dt>Highlights</dt><dd>{profile.highlights}</dd>{/if}
        <dt>Hashtags</dt>
        <dd>{profile.hashtags.join(' ')}</dd>
        <dt>Posts on</dt>
        <dd>{posting.map((p) => socialNetwork(p.network).name).join(', ') || 'no network'}</dd>
        {#if (profile.social_profiles || []).some((p) => p.url)}
          <dt>Profiles</dt>
          <dd class="links">
            {#each profile.social_profiles.filter((p) => p.url) as p}
              <a href={p.url} target="_blank" rel="noopener noreferrer">{socialNetwork(p.network).name}</a>
            {/each}
          </dd>
        {/if}
      </dl>
    {/if}

    {#snippet actions()}
      {#if editing}
        <button class="rc-btn primary" onclick={save} disabled={isBusy}><Check size={14} />Save</button>
        {#if !missing.length || saved}
          <button class="rc-btn ghost" onclick={() => (editing = false)}>Cancel</button>
        {/if}
      {:else}
        <button class="rc-btn" onclick={() => (editing = true)}><Pencil size={14} />Edit</button>
      {/if}
    {/snippet}
  </ResultCard>
{/if}

<style>
  .form {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px 14px;
  }

  @container (max-width: 520px) {
    .form {
      grid-template-columns: minmax(0, 1fr);
    }
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 5px;
    min-width: 0;
  }

  .field.wide {
    grid-column: 1 / -1;
  }

  .field.missing .rc-label {
    color: var(--status-warning);
  }

  .field.missing .input {
    border-color: var(--status-warning);
  }

  .input {
    width: 100%;
    box-sizing: border-box;
    background: var(--bg-app);
    border: 1px solid var(--border-subtle);
    color: var(--text-primary);
    padding: 7px 10px;
    border-radius: var(--radius-sm);
    font: inherit;
    font-size: 13px;
    outline: none;
    resize: vertical;
  }

  .input:focus {
    border-color: var(--primary-accent);
    box-shadow: 0 0 0 2px var(--primary-accent-container);
  }

  .input.mono {
    font-family: var(--font-family-mono);
    font-size: 12px;
  }

  details summary {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    cursor: pointer;
    list-style: none;
  }

  details summary::-webkit-details-marker {
    display: none;
  }

  details summary :global(.chev) {
    transition: transform 0.15s ease;
  }

  details[open] summary :global(.chev) {
    transform: rotate(90deg);
  }

  details[open] {
    gap: 6px;
  }

  .links {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
  }

  .links a {
    color: var(--primary-accent);
    text-decoration: none;
  }

  .rc-facts .rc-chip {
    margin-left: 6px;
  }
</style>
