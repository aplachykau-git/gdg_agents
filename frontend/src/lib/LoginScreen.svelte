<script>
  import {
    Workflow,
    Sparkles,
    CalendarCheck,
    ArrowRight
  } from '@lucide/svelte';
  import studioLogo from '../assets/community-ai-studio.png';

  let {
    onLogin = () => {},
    isLoggingIn = false,
    errorMessage = ''
  } = $props();

  const HIGHLIGHTS = [
    {
      icon: Workflow,
      title: 'Autonomous Multi-Agent Routing',
      desc: 'Coordinates specialized reasoning engines to solve complex community workflows.'
    },
    {
      icon: Sparkles,
      title: 'Creative Media & Content Generation',
      desc: 'Cinematic speaker videos, LinkedIn announcements, and structured agendas.'
    },
    {
      icon: CalendarCheck,
      title: 'Operations & Financial Automation',
      desc: 'Smart attendee roster management, conflict-free scheduling, and expense OCR.'
    }
  ];
</script>

<div class="login-page">
  <!-- Subtle Animated Ambient Glows -->
  <div class="ambient-glow glow-blue"></div>
  <div class="ambient-glow glow-green"></div>
  <div class="ambient-glow glow-yellow"></div>
  <div class="ambient-glow glow-red"></div>

  <div class="login-card">
    <img src={studioLogo} alt="Community AI Studio" class="login-brand-logo" />
    <p class="brand-tagline">
      Autonomous multi-agent platform for event coordination, creative media generation, and community operations.
    </p>

    <!-- 3 Core Capabilities List -->
    <div class="features-list">
      {#each HIGHLIGHTS as item}
        {@const IconComp = item.icon}
        <div class="feature-item">
          <div class="feature-icon-box">
            <IconComp size={16} strokeWidth={1.8} />
          </div>
          <div class="feature-text">
            <strong class="feature-title">{item.title}</strong>
            <p class="feature-desc">{item.desc}</p>
          </div>
        </div>
      {/each}
    </div>

    {#if errorMessage}
      <div class="auth-error-banner" role="alert">
        <span>{errorMessage}</span>
      </div>
    {/if}

    <button 
      class="btn-google-signin" 
      onclick={onLogin} 
      disabled={isLoggingIn}
      aria-label="Sign in with Google"
    >
      {#if isLoggingIn}
        <div class="btn-spinner"></div>
        <span>Signing in...</span>
      {:else}
        <svg class="google-svg-logo" viewBox="0 0 24 24" width="18" height="18">
          <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
          <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
          <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>
          <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>
        </svg>
        <span class="btn-text">Sign in with Google</span>
        <ArrowRight size={14} class="btn-arrow" />
      {/if}
    </button>
  </div>
</div>

<style>
  .login-page {
    position: fixed;
    inset: 0;
    width: 100vw;
    height: 100vh;
    background: #080b11;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
    box-sizing: border-box;
    overflow: hidden;
    user-select: none;
    font-family: var(--font-sans, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif);
  }

  /* Ambient Glowing Backdrop Lights */
  .ambient-glow {
    position: absolute;
    width: 380px;
    height: 380px;
    border-radius: 50%;
    filter: blur(110px);
    opacity: 0.16;
    pointer-events: none;
    animation: floatOrb 14s infinite alternate ease-in-out;
  }

  .glow-blue {
    top: 12%;
    left: 22%;
    background: #4285F4;
  }

  .glow-green {
    top: 18%;
    right: 22%;
    background: #34A853;
    animation-delay: -3.5s;
  }

  .glow-yellow {
    bottom: 18%;
    left: 26%;
    background: #FBBC05;
    animation-delay: -7s;
  }

  .glow-red {
    bottom: 14%;
    right: 26%;
    background: #EA4335;
    animation-delay: -10.5s;
  }

  @keyframes floatOrb {
    0% { transform: scale(1) translate(0, 0); }
    50% { transform: scale(1.1) translate(20px, -15px); }
    100% { transform: scale(0.94) translate(-15px, 20px); }
  }

  /* Glassmorphism Card */
  .login-card {
    position: relative;
    z-index: 10;
    background: rgba(18, 24, 38, 0.82);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 
      0 24px 60px -12px rgba(0, 0, 0, 0.65),
      inset 0 1px 0 rgba(255, 255, 255, 0.12);
    border-radius: 18px;
    width: 100%;
    max-width: 450px;
    padding: 36px 32px 32px;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    box-sizing: border-box;
    animation: popIn 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  }

  @keyframes popIn {
    from { opacity: 0; transform: scale(0.97) translateY(6px); }
    to { opacity: 1; transform: scale(1) translateY(0); }
  }

  .login-brand-logo {
    height: 48px;
    width: auto;
    max-width: 260px;
    object-fit: contain;
    margin: 0 0 12px;
    display: block;
  }

  .brand-tagline {
    font-size: 13px;
    color: #94a3b8;
    line-height: 1.5;
    margin: 0 0 22px;
    max-width: 380px;
  }

  /* 3 Core Highlights */
  .features-list {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-bottom: 24px;
  }

  .feature-item {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 10px;
    padding: 10px 12px;
    text-align: left;
    transition: background 0.15s ease, border-color 0.15s ease;
  }

  .feature-item:hover {
    background: rgba(255, 255, 255, 0.06);
    border-color: rgba(255, 255, 255, 0.12);
  }

  .feature-icon-box {
    width: 30px;
    height: 30px;
    border-radius: 8px;
    background: rgba(66, 133, 244, 0.12);
    color: #8ab4f8;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    margin-top: 1px;
  }

  .feature-text {
    flex: 1;
    min-width: 0;
  }

  .feature-title {
    display: block;
    font-size: 12.5px;
    font-weight: 600;
    color: #f1f5f9;
    margin-bottom: 2px;
  }

  .feature-desc {
    font-size: 11.5px;
    color: #94a3b8;
    line-height: 1.4;
    margin: 0;
  }

  /* Error Banner */
  .auth-error-banner {
    background: rgba(239, 68, 68, 0.12);
    border: 1px solid rgba(239, 68, 68, 0.35);
    color: #f87171;
    font-size: 12px;
    padding: 9px 14px;
    border-radius: 8px;
    margin-bottom: 18px;
    width: 100%;
    box-sizing: border-box;
  }

  /* Sign in Button */
  .btn-google-signin {
    width: 100%;
    height: 46px;
    background: #ffffff;
    color: #1e293b;
    border: none;
    border-radius: 10px;
    font-size: 13.5px;
    font-weight: 600;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    cursor: pointer;
    box-shadow: 
      0 4px 14px rgba(0, 0, 0, 0.25),
      0 1px 2px rgba(0, 0, 0, 0.1);
    transition: all 0.15s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .btn-google-signin:hover:not(:disabled) {
    background: #f8fafc;
    box-shadow: 0 6px 20px rgba(66, 133, 244, 0.3);
    transform: translateY(-1px);
  }

  .btn-google-signin:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }

  .google-svg-logo {
    flex-shrink: 0;
  }

  .btn-text {
    letter-spacing: -0.01em;
  }

  :global(.btn-arrow) {
    color: #64748b;
    transition: transform 0.15s ease;
  }

  .btn-google-signin:hover:not(:disabled) :global(.btn-arrow) {
    transform: translateX(3px);
    color: #1e293b;
  }

  .btn-spinner {
    width: 16px;
    height: 16px;
    border: 2px solid rgba(0, 0, 0, 0.15);
    border-top-color: #4285F4;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }
</style>
