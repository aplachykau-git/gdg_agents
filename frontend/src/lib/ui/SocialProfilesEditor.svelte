<script>
  // Editable list of the community's social profiles: network, profile link, "Posts" toggle
  // (only for networks the countdown planner can post on), remove; plus "Add a network".
  import { AlertCircle, Check, Plus, X } from '@lucide/svelte';
  import { SOCIAL_NETWORKS, profileUrlWarning, socialNetwork } from '../config.js';

  let { profiles = [], onChange = () => {}, highlight = false } = $props();

  const unused = $derived(SOCIAL_NETWORKS.filter((n) => !profiles.some((p) => p.network === n.id)));
  const nonePosting = $derived(!profiles.some((p) => p.post && socialNetwork(p.network).plannable));

  function update(index, patch) {
    onChange(profiles.map((p, i) => (i === index ? { ...p, ...patch } : p)));
  }

  function remove(index) {
    onChange(profiles.filter((_, i) => i !== index));
  }

  function add(id) {
    if (!id) return;
    onChange([...profiles, { network: id, url: '', post: socialNetwork(id).plannable }]);
  }
</script>

<div class="sp" class:sp-highlight={highlight}>
  <ul class="sp-list">
    {#each profiles as profile, i (profile.network)}
      {@const net = socialNetwork(profile.network)}
      {@const warning = profileUrlWarning(profile.network, profile.url)}
      <li class="sp-row">
        <span class="sp-net"><span class="sp-dot net-{profile.network}"></span>{net.name}</span>
        <input
          type="url"
          class="sp-input"
          class:sp-invalid={warning}
          value={profile.url || ''}
          placeholder={net.placeholder}
          aria-label="{net.name} profile link"
          oninput={(e) => update(i, { url: e.target.value })}
        />
        {#if net.plannable}
          <button
            type="button"
            class="sp-chip"
            class:sp-on={profile.post}
            aria-pressed={profile.post}
            title="Plan countdown posts on {net.name}"
            onclick={() => update(i, { post: !profile.post })}
          >
            {#if profile.post}<Check size={12} />{/if}Posts
          </button>
        {:else}
          <span class="sp-links-only" title="Mentioned in posts as a link; no posts are planned here">link only</span>
        {/if}
        <button type="button" class="sp-remove" onclick={() => remove(i)} aria-label="Remove {net.name}" title="Remove">
          <X size={14} />
        </button>
        {#if warning}
          <span class="sp-warning"><AlertCircle size={12} />{warning}</span>
        {/if}
      </li>
    {/each}
  </ul>

  {#if nonePosting}
    <p class="sp-none"><AlertCircle size={12} />No network has "Posts" on, so the countdown plan has nowhere to publish.</p>
  {/if}

  {#if unused.length}
    <label class="sp-add">
      <Plus size={13} />
      <select
        class="sp-input"
        aria-label="Add a network"
        value=""
        onchange={(e) => {
          add(e.target.value);
          e.target.value = '';
        }}
      >
        <option value="" disabled>Add a network...</option>
        {#each unused as n}
          <option value={n.id}>{n.name}{n.plannable ? '' : ' (link only)'}</option>
        {/each}
      </select>
    </label>
  {/if}
</div>

<style>
  .sp {
    display: flex;
    flex-direction: column;
    gap: 8px;
    container-type: inline-size;
  }

  .sp-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .sp-row {
    display: grid;
    grid-template-columns: 140px minmax(0, 1fr) 74px 28px;
    align-items: center;
    gap: 8px;
  }

  @container (max-width: 480px) {
    .sp-row {
      grid-template-columns: minmax(0, 1fr) 74px 28px;
    }

    .sp-net,
    .sp-warning {
      grid-column: 1 / -1;
    }
  }

  .sp-net {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    font-size: 12.5px;
    color: var(--text-primary);
    min-width: 0;
  }

  .sp-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
    background: var(--text-tertiary);
  }

  .net-linkedin { background: #0a66c2; }
  .net-instagram { background: #e1306c; }
  .net-facebook { background: #1877f2; }
  .net-x, .net-threads { background: var(--text-primary); }
  .net-bluesky { background: #1185fe; }
  .net-mastodon { background: #6364ff; }
  .net-youtube { background: #ff0000; }
  .net-tiktok { background: #25f4ee; }
  .net-discord { background: #5865f2; }
  .net-telegram { background: #26a5e4; }
  .net-gdg { background: #34a853; }

  .sp-input {
    width: 100%;
    box-sizing: border-box;
    background: var(--bg-app);
    border: 1px solid var(--border-subtle);
    color: var(--text-primary);
    padding: 6px 10px;
    border-radius: var(--radius-sm);
    font: inherit;
    font-size: 12.5px;
    outline: none;
  }

  .sp-input:focus {
    border-color: var(--primary-accent);
    box-shadow: 0 0 0 2px var(--primary-accent-container);
  }

  .sp-input.sp-invalid {
    border-color: var(--status-warning);
  }

  .sp-chip {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    padding: 5px 10px;
    border-radius: var(--radius-pill);
    border: 1px solid var(--border-medium);
    background: transparent;
    color: var(--text-secondary);
    font: inherit;
    font-size: 12px;
    cursor: pointer;
  }

  .sp-chip.sp-on {
    border-color: var(--primary-accent);
    background: var(--primary-accent-container);
    color: var(--text-primary);
  }

  .sp-links-only {
    font-size: 11px;
    color: var(--text-tertiary);
    text-align: center;
  }

  .sp-remove {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: none;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--text-tertiary);
    cursor: pointer;
  }

  .sp-remove:hover {
    background: var(--bg-surface-variant);
    color: var(--text-primary);
  }

  .sp-warning {
    grid-column: 2 / -1;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    color: var(--status-warning);
  }

  .sp-none {
    display: flex;
    align-items: center;
    gap: 6px;
    margin: 0;
    font-size: 11.5px;
    color: var(--status-warning);
  }

  .sp-highlight .sp-none {
    font-weight: 600;
  }

  .sp-add {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--text-tertiary);
    max-width: 260px;
  }
</style>
