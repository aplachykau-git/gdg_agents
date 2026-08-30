<script>
  import { History, Trash2, Plus } from '@lucide/svelte';

  let {
    sessions = [],
    selectedSessionId = '',
    isLoading = false,
    onSelectSession = () => {},
    onNewSession = () => {},
    onDeleteSession = () => {}
  } = $props();
</script>

<aside class="studio-sidebar">
  <div class="sidebar-top-bar">
    <div class="sidebar-section-title">
      <History size={13} strokeWidth={1.75} />
      <span>SESSION HISTORY</span>
    </div>
    <button 
      class="sidebar-new-btn" 
      onclick={() => onNewSession()} 
      disabled={isLoading}
      title="Start New Session"
    >
      <Plus size={14} strokeWidth={2.2} />
      <span>New</span>
    </button>
  </div>

  <div class="sessions-stream">
    {#if sessions.length === 0}
      <div class="empty-sessions">
        <p>No recent chats.</p>
        <button class="empty-new-session-btn" onclick={() => onNewSession()} disabled={isLoading}>
          <Plus size={13} strokeWidth={2} />
          <span>Start New Session</span>
        </button>
      </div>
    {:else}
      {#each sessions as session, idx}
        <div class="session-item" class:active={selectedSessionId === session.session_id}>
          <button class="session-nav-btn" onclick={() => onSelectSession(session.session_id)}>
            <span class="session-dot" class:active-dot={selectedSessionId === session.session_id}></span>
            <div class="session-text-group">
              <span class="session-title">Chat Session #{sessions.length - idx}</span>
              <span class="session-meta">{selectedSessionId === session.session_id ? 'Current session' : 'Previous history'}</span>
            </div>
          </button>
          <button 
            class="session-del-btn" 
            onclick={() => onDeleteSession(session.session_id)} 
            title="Delete Session"
          >
            <Trash2 size={14} strokeWidth={1.75} />
          </button>
        </div>
      {/each}
    {/if}
  </div>

  <div class="sidebar-footer">
    <div class="quota-pill">
      <span class="quota-dot"></span>
      <span>Agents Runtime Active</span>
    </div>
  </div>
</aside>

<style>
  .studio-sidebar {
    width: 260px;
    background: var(--bg-surface);
    border-right: 1px solid var(--border-subtle);
    display: flex;
    flex-direction: column;
    height: 100%;
    user-select: none;
    animation: slideInLeft 0.2s ease-out;
  }

  .sidebar-top-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 14px 8px;
    border-bottom: 1px solid var(--border-subtle);
    margin-bottom: 4px;
  }

  .sidebar-section-title {
    font-size: 11px;
    font-weight: 700;
    color: var(--text-tertiary);
    letter-spacing: 0.08em;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .sidebar-new-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 8px;
    background: var(--bg-hover, rgba(255, 255, 255, 0.06));
    border: 1px solid var(--border-subtle);
    border-radius: 6px;
    color: var(--text-primary);
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .sidebar-new-btn:hover:not(:disabled) {
    background: var(--primary, #1a73e8);
    color: #ffffff;
    border-color: transparent;
  }

  .sidebar-new-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .empty-new-session-btn {
    margin-top: 10px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    background: var(--primary, #1a73e8);
    color: #ffffff;
    border: none;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: opacity 0.15s ease;
  }

  .empty-new-session-btn:hover:not(:disabled) {
    opacity: 0.9;
  }

  .sessions-stream {
    flex: 1;
    overflow-y: auto;
    padding: 8px 12px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .empty-sessions {
    padding: 32px 16px;
    text-align: center;
    color: var(--text-tertiary);
    font-size: 12px;
  }

  .empty-sessions p {
    font-weight: 600;
    margin-bottom: 4px;
  }

  .session-item {
    display: flex;
    align-items: center;
    border-radius: var(--radius-pill);
    transition: var(--transition-fast);
    background: transparent;
    padding: 0 4px;
  }

  .session-item:hover {
    background: var(--bg-hover);
  }

  .session-item.active {
    background: var(--primary-accent-container);
  }

  .session-nav-btn {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    background: none;
    border: none;
    text-align: left;
    cursor: pointer;
    color: inherit;
    min-width: 0;
  }

  .session-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--text-tertiary);
    flex-shrink: 0;
  }

  .session-dot.active-dot {
    background: var(--primary-accent);
    box-shadow: 0 0 6px var(--primary-accent);
  }

  .session-text-group {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .session-title {
    font-size: 12px;
    font-weight: 500;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .session-meta {
    font-size: 10px;
    color: var(--text-tertiary);
  }

  .session-del-btn {
    background: none;
    border: none;
    color: var(--text-tertiary);
    padding: 6px 8px;
    cursor: pointer;
    opacity: 0;
    transition: var(--transition-fast);
  }

  .session-item:hover .session-del-btn {
    opacity: 1;
  }

  .session-del-btn:hover {
    color: var(--accent-red, #ea4335);
  }

  .sidebar-footer {
    padding: 12px 16px;
    border-top: 1px solid var(--border-subtle);
  }

  .quota-pill {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    color: var(--text-tertiary);
  }

  .quota-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--accent-green, #34a853);
    box-shadow: 0 0 6px var(--accent-green, #34a853);
  }

  @keyframes slideInLeft {
    from { transform: translateX(-10px); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
  }
</style>
