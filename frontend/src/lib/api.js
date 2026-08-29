import { DEFAULT_APPS } from './constants.js';

export const API_BASE = import.meta.env.VITE_API_URL || '';

export async function fetchApps() {
  try {
    const res = await fetch(`${API_BASE}/list-apps`);
    if (!res.ok) throw new Error(`Status ${res.status}`);
    const data = await res.json();
    if (Array.isArray(data)) {
      const nonAgents = ['configs', 'docs', 'frontend', 'evaluation'];
      const appNameMapping = {
        root_agent: 'Main',
        receipt_scanner: 'Receipt Scanner',
        video_editor: 'Live Video Editor',
        linkedin_post_generator: 'LinkedIn Planner',
        registration_manager: 'Registrations Manager',
        event_planner: 'Event Scheduler',
        agenda_generator: 'Agenda Formatter',
        office_secretary: 'Office Secretary'
      };
      return data
        .filter(name => !nonAgents.includes(name) && !name.includes('.evaluation'))
        .map(name => ({
          name,
          root_agent_name: appNameMapping[name] || name.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
        }));
    } else if (data.apps) {
      return data.apps;
    }
    return DEFAULT_APPS;
  } catch (e) {
    console.warn("Backend not active or unreachable. Loaded default agent catalog.", e);
    return DEFAULT_APPS;
  }
}

export async function fetchSessions(appName, userId) {
  if (!appName) return [];
  const res = await fetch(`${API_BASE}/apps/${appName}/users/${userId}/sessions`);
  if (!res.ok) {
    if (res.status === 404) return [];
    throw new Error(`Failed to fetch sessions: ${res.statusText}`);
  }
  const data = await res.json();
  const rawSessions = Array.isArray(data) ? data : (data.sessions || []);
  return rawSessions.map(s => ({
    id: s.id || s.session_id,
    session_id: s.id || s.session_id,
    state: s.state || {},
    events: s.events || []
  })).sort((a, b) => (b.session_id || '').localeCompare(a.session_id || ''));
}

export async function createSession(appName, userId, sessionId, state = {}) {
  if (!appName) return;
  const res = await fetch(`${API_BASE}/apps/${appName}/users/${userId}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, state })
  });
  if (!res.ok) throw new Error(`Failed to create session: ${res.statusText}`);
  return await res.json();
}

export async function fetchSessionHistory(appName, userId, sessionId) {
  if (!appName || !sessionId) return [];
  const res = await fetch(`${API_BASE}/apps/${appName}/users/${userId}/sessions/${sessionId}`);
  if (!res.ok) throw new Error(`Failed to load session details: ${res.statusText}`);
  const data = await res.json();
  return data.events || [];
}

export async function deleteSessionRequest(appName, userId, sessionId) {
  if (!appName || !sessionId) return;
  const res = await fetch(`${API_BASE}/apps/${appName}/users/${userId}/sessions/${sessionId}`, {
    method: 'DELETE'
  });
  if (!res.ok) throw new Error(`Failed to delete session: ${res.statusText}`);
  return true;
}

export async function runSSEStream({ appName, userId, sessionId, parts, state, onEvent, onError, signal }) {
  const payload = {
    app_name: appName,
    user_id: userId,
    session_id: sessionId,
    new_message: {
      role: 'user',
      parts: parts
    },
    ...(state && Object.keys(state).length > 0 ? { state_delta: state } : {}),
    streaming: true
  };

  const res = await fetch(`${API_BASE}/run_sse`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal
  });

  if (!res.ok) {
    if (res.status === 404) {
      // Fallback to non-streaming /run
      const fallbackRes = await fetch(`${API_BASE}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...payload, streaming: false }),
        signal
      });
      if (!fallbackRes.ok) {
        const errJson = await fallbackRes.json().catch(() => null);
        throw new Error(errJson?.detail || `Backend error: ${fallbackRes.statusText}`);
      }
      const data = await fallbackRes.json();
      if (Array.isArray(data)) {
        data.forEach(e => onEvent(e));
      } else {
        onEvent(data);
      }
      return;
    }
    
    const errJson = await res.json().catch(() => null);
    throw new Error(errJson?.detail || `Backend error: ${res.statusText}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    
    const lines = buffer.split('\n');
    buffer = lines.pop(); // keep last incomplete line in buffer

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith(':')) continue; // skip comments / heartbeats
      if (trimmed.startsWith('data:')) {
        const jsonStr = trimmed.slice(5).trim();
        if (jsonStr === '[DONE]') continue;
        try {
          const eventObj = JSON.parse(jsonStr);
          onEvent(eventObj);
        } catch (parseErr) {
          console.warn('Failed to parse SSE JSON chunk:', jsonStr, parseErr);
        }
      }
    }
  }

  if (buffer.trim().startsWith('data:')) {
    const jsonStr = buffer.trim().slice(5).trim();
    if (jsonStr && jsonStr !== '[DONE]') {
      try {
        const eventObj = JSON.parse(jsonStr);
        onEvent(eventObj);
      } catch (parseErr) {
        console.warn('Failed to parse final SSE chunk:', jsonStr, parseErr);
      }
    }
  }
}
