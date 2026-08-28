<script>
  import {
    Calendar,
    Download,
    ExternalLink,
    Clock,
    MapPin,
    CheckCircle2,
    Sparkles,
    CalendarPlus,
    Check
  } from '@lucide/svelte';

  let { 
    eventData = {}, 
    onRefine = () => {} 
  } = $props();

  let selectedIndex = $state(0);
  let downloadedIso = $state(null);

  const dates = $derived(eventData?.dates || []);
  const activeDate = $derived(dates[selectedIndex] || dates[0]);

  function handleDownloadIcs(dateItem) {
    if (!dateItem?.icsDataUri) return;
    const link = document.createElement('a');
    link.href = dateItem.icsDataUri;
    link.download = dateItem.icsFilename || `event_${dateItem.isoDate}.ics`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    downloadedIso = dateItem.isoDate;
    setTimeout(() => {
      downloadedIso = null;
    }, 3000);
  }

  function handleSelectDate(idx) {
    selectedIndex = idx;
  }
</script>

{#if dates.length > 0 && activeDate}
  <div class="event-date-card-wrapper">
    <!-- Header Badge & Title -->
    <div class="card-top-bar">
      <div class="badge-group">
        <div class="verified-badge">
          <CheckCircle2 size={13} />
          <span>Optimal Schedule · No Holiday Conflicts</span>
        </div>
      </div>
      {#if eventData.eventTitle || eventData.location}
        <div class="event-title-row">
          {#if eventData.eventTitle}
            <h4 class="event-name">{eventData.eventTitle}</h4>
          {/if}
          {#if eventData.location}
            <div class="event-venue">
              <MapPin size={13} />
              <span>{eventData.location}</span>
            </div>
          {/if}
        </div>
      {/if}
    </div>

    <!-- Multi-date switcher if agent proposed multiple options -->
    {#if dates.length > 1}
      <div class="date-tabs-row">
        {#each dates as d, idx}
          <button
            type="button"
            class="date-tab-btn"
            class:active={selectedIndex === idx}
            onclick={() => handleSelectDate(idx)}
          >
            <span class="tab-dot" class:active-dot={selectedIndex === idx}></span>
            <span>{d.weekday}, {d.monthShort} {d.day}</span>
            {#if d.isPrimary}
              <span class="primary-pill">Optimal</span>
            {/if}
          </button>
        {/each}
      </div>
    {/if}

    <!-- Main Date Display Banner -->
    <div class="calendar-hero-box">
      <!-- Calendar Tile -->
      <div class="calendar-tile">
        <div class="tile-header">{activeDate.monthShort} {activeDate.year}</div>
        <div class="tile-day">{activeDate.day}</div>
        <div class="tile-weekday">{activeDate.weekday}</div>
      </div>

      <!-- Date Info & Timetable -->
      <div class="date-meta-details">
        <div class="primary-status-row">
          <span class="status-indicator"></span>
          <span class="status-label">{activeDate.label}</span>
        </div>
        <h3 class="full-date-heading">{activeDate.fullDateStr}</h3>
        <div class="time-meta-row">
          <Clock size={14} />
          <span>{activeDate.timeRange}</span>
        </div>
        <p class="verification-note">
          Verified against Polish public holidays and local tech meetup schedules. Perfect for maximum developer attendance.
        </p>
      </div>
    </div>

    <!-- Interactive Actions Bar -->
    <div class="actions-footer">
      <div class="export-buttons-group">
        <!-- Google Calendar Button -->
        <a
          href={activeDate.gcalUrl}
          target="_blank"
          rel="noopener noreferrer"
          class="action-btn gcal-btn"
          id="btn-add-to-google-calendar"
        >
          <CalendarPlus size={15} />
          <span>Add to Google Calendar</span>
          <ExternalLink size={13} class="btn-icon-trailing" />
        </a>

        <!-- Download .ICS Invite Button -->
        <button
          type="button"
          class="action-btn ics-btn"
          id="btn-download-ics-invite"
          onclick={() => handleDownloadIcs(activeDate)}
        >
          {#if downloadedIso === activeDate.isoDate}
            <Check size={15} class="success-icon" />
            <span>Downloaded .ICS</span>
          {:else}
            <Download size={15} />
            <span>Download .ICS File</span>
          {/if}
        </button>
      </div>

      <!-- Quick AI Workflow Next-step Button -->
      <button
        type="button"
        class="action-btn next-step-btn"
        id="btn-build-agenda-for-date"
        onclick={() => onRefine(`Great date! Let's build a detailed event agenda starting at 18:00 for ${activeDate.fullDateStr} with speakers and talk abstracts.`)}
      >
        <Sparkles size={14} />
        <span>Build Agenda for this Date</span>
      </button>
    </div>
  </div>
{/if}

<style>
  .event-date-card-wrapper {
    margin-top: 16px;
    border-radius: var(--radius-lg, 16px);
    border: 1px solid rgba(234, 67, 53, 0.28);
    background: linear-gradient(180deg, rgba(234, 67, 53, 0.06) 0%, rgba(20, 20, 25, 0.6) 100%);
    backdrop-filter: blur(12px);
    padding: 18px 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2), 0 0 0 1px rgba(234, 67, 53, 0.15) inset;
    transition: all 0.2s ease;
  }

  .card-top-bar {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .badge-group {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .verified-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 4px 10px;
    border-radius: 9999px;
    background: rgba(52, 168, 83, 0.12);
    color: #34A853;
    font-size: 11px;
    font-weight: 600;
    border: 1px solid rgba(52, 168, 83, 0.25);
  }

  .event-title-row {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .event-name {
    margin: 0;
    font-size: 16px;
    font-weight: 700;
    color: var(--text-primary, #ffffff);
    letter-spacing: -0.01em;
  }

  .event-venue {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--text-secondary, #9aa0a6);
  }

  .date-tabs-row {
    display: flex;
    gap: 8px;
    overflow-x: auto;
    padding-bottom: 4px;
  }

  .date-tab-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    border-radius: var(--radius-md, 8px);
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.1));
    color: var(--text-secondary, #9aa0a6);
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .date-tab-btn:hover {
    background: rgba(255, 255, 255, 0.08);
    color: var(--text-primary, #ffffff);
  }

  .date-tab-btn.active {
    background: rgba(234, 67, 53, 0.18);
    border-color: rgba(234, 67, 53, 0.5);
    color: #ffffff;
    font-weight: 600;
  }

  .tab-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.3);
  }

  .active-dot {
    background: #EA4335;
    box-shadow: 0 0 6px rgba(234, 67, 53, 0.8);
  }

  .primary-pill {
    padding: 1px 6px;
    border-radius: 4px;
    background: rgba(234, 67, 53, 0.3);
    color: #ffffff;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
  }

  .calendar-hero-box {
    display: flex;
    align-items: center;
    gap: 18px;
    background: rgba(0, 0, 0, 0.25);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: var(--radius-md, 12px);
    padding: 16px;
  }

  @media (max-width: 640px) {
    .calendar-hero-box {
      flex-direction: column;
      align-items: flex-start;
    }
  }

  .calendar-tile {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 86px;
    min-width: 86px;
    border-radius: 12px;
    overflow: hidden;
    background: var(--bg-surface-elevated, #24252a);
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35);
    border: 1px solid rgba(255, 255, 255, 0.12);
  }

  .tile-header {
    width: 100%;
    background: #EA4335;
    color: #ffffff;
    font-size: 11px;
    font-weight: 800;
    text-align: center;
    padding: 4px 0;
    letter-spacing: 0.08em;
  }

  .tile-day {
    font-size: 32px;
    font-weight: 800;
    color: var(--text-primary, #ffffff);
    line-height: 1.1;
    padding-top: 6px;
  }

  .tile-weekday {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-secondary, #9aa0a6);
    padding-bottom: 8px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .date-meta-details {
    display: flex;
    flex-direction: column;
    gap: 4px;
    flex: 1;
  }

  .primary-status-row {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .status-indicator {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #34A853;
  }

  .status-label {
    font-size: 11px;
    font-weight: 700;
    color: #34A853;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .full-date-heading {
    margin: 0;
    font-size: 18px;
    font-weight: 700;
    color: var(--text-primary, #ffffff);
  }

  .time-meta-row {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: #EA4335;
    font-weight: 600;
  }

  .verification-note {
    margin: 4px 0 0 0;
    font-size: 12px;
    color: var(--text-secondary, #9aa0a6);
    line-height: 1.4;
  }

  .actions-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
    padding-top: 4px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
  }

  .export-buttons-group {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .action-btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 14px;
    border-radius: var(--radius-md, 8px);
    font-size: 12.5px;
    font-weight: 600;
    cursor: pointer;
    text-decoration: none;
    transition: all 0.15s ease;
    border: none;
  }

  .gcal-btn {
    background: #EA4335;
    color: #ffffff;
    box-shadow: 0 2px 8px rgba(234, 67, 53, 0.35);
  }

  .gcal-btn:hover {
    background: #d93025;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(234, 67, 53, 0.45);
  }

  .ics-btn {
    background: rgba(255, 255, 255, 0.08);
    color: var(--text-primary, #ffffff);
    border: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.15));
  }

  .ics-btn:hover {
    background: rgba(255, 255, 255, 0.14);
    border-color: rgba(255, 255, 255, 0.25);
    transform: translateY(-1px);
  }

  .next-step-btn {
    background: rgba(66, 133, 244, 0.15);
    color: #4285F4;
    border: 1px solid rgba(66, 133, 244, 0.3);
  }

  .next-step-btn:hover {
    background: rgba(66, 133, 244, 0.25);
    border-color: rgba(66, 133, 244, 0.5);
    color: #ffffff;
    transform: translateY(-1px);
  }

  :global(.success-icon) {
    color: #34A853;
  }

  :global(.btn-icon-trailing) {
    opacity: 0.8;
  }
</style>
