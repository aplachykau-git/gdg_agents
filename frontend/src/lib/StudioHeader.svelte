<script>
  // Top app bar: brand/home, new session, history toggle, agent picker, architecture and user menu.
  import { ChevronDown, HelpCircle, History, Layers, LogOut, Moon, Plus, Settings, Sun, Workflow } from '@lucide/svelte';
  import squareLogo from '../assets/community-ai-studio-logo.png';

  let {
    communityName = 'GDG Krakow',
    isLoading = false,
    hasSession = false,
    showSessions = false,
    showAgentGraph = false,
    activeAgent = 'root_agent',
    activeAgentTheme = { color: '', label: '' },
    apps = [],
    currentUser = null,
    isDarkMode = true,
    onHome = () => {},
    onNewSession = () => {},
    onToggleSessions = () => {},
    onAgentChange = () => {},
    onShowGraph = () => {},
    onToggleTheme = () => {},
    onShowCapabilities = () => {},
    onShowSettings = () => {},
    onLogout = () => {},
  } = $props();

  let showUserMenu = $state(false);
  let avatarLoadError = $state(false);
</script>

<svelte:window
  onkeydown={(e) => {
    if (e.key === 'Escape') showUserMenu = false;
  }}
  onclick={(e) => {
    if (showUserMenu && !e.target.closest?.('.user-menu-container')) showUserMenu = false;
  }}
/>

<header class="studio-header">
  <div class="header-left">
    <!-- Community AI Studio Brand Badge (Leftmost) -->
    <button
      class="brand-badge"
      onclick={onHome}
      data-tooltip="Home"
      aria-label="Home"
    >
      <img
        src={squareLogo}
        alt="Community AI Studio"
        class="brand-icon-img"
      />
      <div class="brand-text">
        <span class="brand-name">Community AI Studio</span>
        <span class="brand-sub">{communityName}</span>
      </div>
    </button>

    <div class="header-divider"></div>

    <!-- New Session Button (With label) -->
    <button
      class="header-btn-new-session"
      onclick={onNewSession}
      disabled={isLoading}
      data-tooltip="Start New Session"
      aria-label="Start New Session"
    >
      <Plus size={15} strokeWidth={2.2} />
      <span>New session</span>
    </button>

    <!-- Sidebar toggle (History) -->
    <button
      class="icon-btn"
      class:active={showSessions}
      onclick={onToggleSessions}
      data-tooltip="Session History"
      aria-label="Session History"
    >
      <History size={18} strokeWidth={1.75} />
    </button>
  </div>

  <div class="header-right">
    <!-- Active Agent Selector with integrated Online dot -->
    <div class="app-picker">
      <span class="picker-label">Agent:</span>
      <div
        class="select-wrapper"
        class:has-session={hasSession}
        class:is-main={activeAgent === "root_agent"}
      >
        {#if hasSession}
          <span
            class="live-status-dot"
            style="background: {activeAgentTheme.color}; box-shadow: 0 0 8px {activeAgentTheme.color}80;"
            data-tooltip="Session Active • Connected ({activeAgentTheme.label})"
            aria-label="Session Active • Connected ({activeAgentTheme.label})"
          ></span>
        {:else if activeAgent === "root_agent"}
          <span
            class="main-badge-icon"
            data-tooltip="Main Coordinator"
            aria-label="Main Coordinator"
          >
            <Layers size={12} strokeWidth={2} />
          </span>
        {/if}
        <select
          id="appSelect"
          value={activeAgent}
          onchange={(e) => onAgentChange(e.target.value)}
        >
          {#each apps as app}
            <option value={app.name}>
              {app.root_agent_name || app.name}
            </option>
          {/each}
        </select>
        <ChevronDown size={14} class="select-chevron" />
      </div>
    </div>

    <div class="header-divider"></div>

    <!-- Multi-Agent Architecture -->
    <button
      class="icon-btn"
      class:active={showAgentGraph}
      onclick={onShowGraph}
      data-tooltip="Multi-Agent Architecture"
      aria-label="Multi-Agent Architecture"
    >
      <Workflow size={18} strokeWidth={1.75} />
    </button>

    <!-- User Profile & Workspace Options Dropdown (Combined) -->
    {#if currentUser}
      <div class="user-menu-container">
        <button 
          class="user-header-profile" 
          class:active={showUserMenu}
          onclick={(e) => {
            e.stopPropagation();
            showUserMenu = !showUserMenu;
          }} 
          title="Account & Options ({currentUser.displayName || 'Google Account'})"
          aria-label="Account and options"
        >
          <div class="user-avatar-wrap">
            {#if currentUser.photoURL && !avatarLoadError}
              <img
                src={currentUser.photoURL}
                alt="User avatar"
                class="header-avatar-img"
                referrerpolicy="no-referrer"
                onerror={() => (avatarLoadError = true)}
              />
            {:else}
              <span class="header-avatar-fallback">
                {(currentUser.displayName || currentUser.email || 'U').charAt(0).toUpperCase()}
              </span>
            {/if}
          </div>
          <ChevronDown size={11} strokeWidth={2.2} class="profile-dropdown-arrow" />
        </button>

        {#if showUserMenu}
          <div class="dropdown-menu user-dropdown">
            <!-- Account info header -->
            <div class="user-dropdown-header">
              <div class="user-dropdown-top">
                {#if currentUser.photoURL && !avatarLoadError}
                  <img
                    src={currentUser.photoURL}
                    alt="Avatar"
                    class="dropdown-avatar-img"
                    referrerpolicy="no-referrer"
                    onerror={() => (avatarLoadError = true)}
                  />
                {:else}
                  <span class="dropdown-avatar-fallback">
                    {(currentUser.displayName || currentUser.email || 'U').charAt(0).toUpperCase()}
                  </span>
                {/if}
                <div class="user-dropdown-info">
                  <div class="user-dropdown-name">{currentUser.displayName || 'Google Account'}</div>
                </div>
              </div>
            </div>

            <div class="dropdown-divider"></div>

            <!-- Workspace Theme / Capabilities / Settings -->
            <button
              class="dropdown-item"
              onclick={() => {
                onToggleTheme();
                showUserMenu = false;
              }}
            >
              {#if isDarkMode}
                <Sun size={15} strokeWidth={1.75} class="dropdown-icon" />
                <span>Light Theme</span>
              {:else}
                <Moon size={15} strokeWidth={1.75} class="dropdown-icon" />
                <span>Dark Theme</span>
              {/if}
            </button>

            <button
              class="dropdown-item"
              onclick={() => {
                onShowCapabilities();
                showUserMenu = false;
              }}
            >
              <HelpCircle size={15} strokeWidth={1.75} class="dropdown-icon" />
              <span>Capabilities</span>
            </button>

            <button
              class="dropdown-item"
              onclick={() => {
                onShowSettings();
                showUserMenu = false;
              }}
            >
              <Settings size={15} strokeWidth={1.75} class="dropdown-icon" />
              <span>Settings</span>
            </button>

            <div class="dropdown-divider"></div>

            <!-- Logout -->
            <button
              class="dropdown-item dropdown-item-danger"
              onclick={() => {
                onLogout();
                showUserMenu = false;
              }}
            >
              <LogOut size={15} strokeWidth={1.75} class="dropdown-icon" />
              <span>Sign out</span>
            </button>
          </div>
        {/if}
      </div>
    {/if}
  </div>
</header>

<style>
  @keyframes fadeInMenu {
    from {
      opacity: 0;
      transform: translateY(-4px) scale(0.98);
    }
    to {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
  }

  @keyframes pulseGlow {
    0%,
    100% {
      opacity: 1;
      transform: scale(1);
    }
    50% {
      opacity: 0.4;
      transform: scale(0.85);
    }
  }

  .studio-header {
    height: 56px;
    background: var(--bg-surface);
    border-bottom: 1px solid var(--border-subtle);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 16px;
    z-index: 50;
  }

  .header-left, .header-right {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .brand-badge {
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 0;
    user-select: none;
    background: transparent;
    border: none;
    cursor: pointer;
    text-align: left;
    outline: none;
    transition: opacity 0.15s ease;
  }

  .brand-badge:hover, .brand-badge:focus, .brand-badge:active {
    background: transparent;
    border: none;
    box-shadow: none;
    outline: none;
    opacity: 0.88;
  }

  .brand-icon-img {
    width: 28px;
    height: 28px;
    border-radius: 7px;
    object-fit: cover;
    flex-shrink: 0;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.18);
  }

  .brand-text {
    display: flex;
    flex-direction: column;
    line-height: 1.15;
  }

  .brand-name {
    font-size: 13px;
    font-weight: 700;
    letter-spacing: -0.015em;
    color: var(--text-primary);
  }

  .brand-sub {
    font-size: 10.5px;
    font-weight: 500;
    color: var(--text-secondary);
    letter-spacing: 0.01em;
  }

  .header-btn-new-session {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    color: var(--text-primary);
    padding: 6px 12px;
    border-radius: var(--radius-pill);
    font-size: 12.5px;
    font-weight: 600;
    cursor: pointer;
    transition: var(--transition-fast);
  }

  .header-btn-new-session:hover:not(:disabled) {
    background: var(--primary-accent-container);
    border-color: var(--primary-accent);
    color: var(--primary-accent);
  }

  .header-btn-new-session:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .header-divider {
    width: 1px;
    height: 20px;
    background: var(--border-subtle);
    margin: 0 2px;
  }

  .app-picker {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .picker-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-tertiary);
  }

  .select-wrapper {
    position: relative;
    display: flex;
    align-items: center;
  }

  .select-wrapper select {
    appearance: none;
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    color: var(--text-primary);
    padding: 6px 30px 6px 14px;
    border-radius: var(--radius-pill);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    outline: none;
    transition: var(--transition-fast);
  }

  .select-wrapper.has-session select {
    padding-left: 24px;
  }

  .select-wrapper.is-main select {
    padding-left: 28px;
  }

  .select-wrapper select:hover {
    border-color: var(--primary-accent);
  }

  .main-badge-icon {
    position: absolute;
    left: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--primary-accent);
    pointer-events: none;
    z-index: 2;
  }

  .live-status-dot {
    position: absolute;
    left: 10px;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--accent-green, #34a853);
    box-shadow: 0 0 6px var(--accent-green, #34a853);
    pointer-events: none;
    z-index: 2;
    animation: pulseGlow 1.8s infinite ease-in-out;
  }

  .dropdown-menu {
    position: absolute;
    top: calc(100% + 8px);
    right: 0;
    min-width: 170px;
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-lg);
    padding: 6px;
    z-index: 100;
    display: flex;
    flex-direction: column;
    gap: 2px;
    animation: fadeInMenu 0.15s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .dropdown-item {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 8px 12px;
    border-radius: var(--radius-md);
    background: transparent;
    border: none;
    color: var(--text-primary);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    text-align: left;
    transition: var(--transition-fast);
  }

  .dropdown-item:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
  }

  .dropdown-item:hover :global(.dropdown-icon) {
    color: var(--primary-accent);
  }

  .dropdown-item-danger {
    color: #ef4444 !important;
  }

  .dropdown-item-danger :global(.dropdown-icon) {
    color: #ef4444 !important;
  }

  .dropdown-item-danger:hover {
    background: rgba(239, 68, 68, 0.12) !important;
    color: #ef4444 !important;
  }

  .dropdown-item-danger:hover :global(.dropdown-icon) {
    color: #ef4444 !important;
  }

  .icon-btn {
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-pill);
    border: 1px solid transparent;
    background: transparent;
    color: var(--text-secondary);
    cursor: pointer;
    transition: var(--transition-fast);
  }

  .icon-btn:hover {
    background: var(--bg-surface-elevated);
    color: var(--text-primary);
  }

  .icon-btn.active {
    background: var(--primary-accent-container);
    color: var(--primary-accent);
    border-color: var(--primary-accent);
  }

  .user-menu-container {
    position: relative;
    display: inline-flex;
    align-items: center;
  }

  .user-header-profile {
    background: var(--bg-surface-elevated, rgba(255, 255, 255, 0.04));
    border: 1px solid var(--border-subtle);
    padding: 2px 6px 2px 2px;
    border-radius: 16px;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    cursor: pointer;
    transition: var(--transition-fast);
    height: 30px;
    box-sizing: border-box;
  }

  .user-header-profile:hover, .user-header-profile.active {
    background: var(--bg-surface-variant);
    border-color: var(--primary-accent);
  }

  .user-header-profile.active :global(.profile-dropdown-arrow) {
    transform: rotate(180deg);
  }

  .user-header-profile:hover :global(.profile-dropdown-arrow) {
    color: var(--text-primary);
  }

  .user-avatar-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    overflow: hidden;
    flex-shrink: 0;
  }

  .header-avatar-img {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    object-fit: cover;
    display: block;
    flex-shrink: 0;
  }

  .header-avatar-fallback {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    background: var(--primary-accent);
    color: #ffffff;
    font-size: 11.5px;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  .user-dropdown {
    right: 0;
    top: calc(100% + 8px);
    width: 220px;
    padding: 8px;
    z-index: 1000;
  }

  .user-dropdown-header {
    padding: 6px 6px 8px;
  }

  .user-dropdown-top {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .dropdown-avatar-img {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    object-fit: cover;
    flex-shrink: 0;
  }

  .dropdown-avatar-fallback {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: var(--primary-accent);
    color: #ffffff;
    font-size: 13px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .user-dropdown-info {
    flex: 1;
    min-width: 0;
  }

  .user-dropdown-name {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

</style>
