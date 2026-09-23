export function areScenariosComplete(scenarios) {
  if (!Array.isArray(scenarios) || scenarios.length === 0) return false;
  return scenarios.every(sc => {
    if (!sc || !Array.isArray(sc.shots) || sc.shots.length < 5) return false;
    return sc.shots.every(sh => sh && typeof sh.action === 'string' && sh.action.trim().length > 3);
  });
}

export function hasVideoScenarios(input) {
  if (!input) return false;
  if (Array.isArray(input) && input.length > 0) return true;
  if (typeof input === 'object') {
    if (Array.isArray(input.scenarios) && input.scenarios.length > 0) return true;
    if (typeof input.message === 'string' && hasVideoScenarios(input.message)) return true;
    return false;
  }
  if (typeof input === 'string') {
    return (
      input.includes('Creative Video Scenarios') ||
      (/Option\s*\d+:\s*.+?\(`.+?`\)/i.test(input) && input.includes('Shot 1'))
    );
  }
  return false;
}

export function normalizeScenarios(rawScenarios) {
  if (!Array.isArray(rawScenarios)) return [];
  return rawScenarios.map((sc, idx) => {
    const num = sc.number || (idx + 1);
    const shots = (sc.shots || []).map((sh, sIdx) => ({
      shotNumber: sh.shot_number ?? sh.shotNumber ?? (sIdx + 1),
      timeRange: sh.time_range ?? sh.timeRange ?? `00:0${sIdx * 2} - 00:0${(sIdx + 1) * 2}`,
      action: (sh.action || '').trim(),
      camera: (sh.camera || '').trim()
    }));

    const styles = (sc.styles || []).map((st, stIdx) => ({
      id: st.id || `${sc.id || `scenario_${num}`}_style_${stIdx + 1}`,
      name: st.name || st.genre || `Style ${stIdx + 1}`,
      genre: st.genre || '',
      description: st.description || '',
      shots: (st.shots || []).map((sh, sIdx) => ({
        shotNumber: sh.shot_number ?? sh.shotNumber ?? (sIdx + 1),
        timeRange: sh.time_range ?? sh.timeRange ?? `00:0${sIdx * 2} - 00:0${(sIdx + 1) * 2}`,
        action: (sh.action || '').trim(),
        camera: (sh.camera || '').trim(),
        lightingAtmosphere: (sh.lighting_atmosphere ?? sh.lightingAtmosphere ?? '').trim()
      })),
      omniPrompt: st.omni_prompt ?? st.omniPrompt ?? ''
    }));

    return {
      id: sc.id || `scenario_${num}`,
      number: num,
      title: sc.title || `Option ${num}`,
      genre: sc.genre || 'Cinematic',
      concept: (sc.concept || '').trim(),
      narrativeMetaphor: sc.narrative_metaphor || sc.narrativeMetaphor || '',
      shots,
      omniPrompt: sc.omni_prompt || sc.omniPrompt || sc.concept || '',
      styles
    };
  });
}

export function extractVideoScenarios(input) {
  if (!input) return [];

  // If already an array of scenario objects, normalize directly
  if (Array.isArray(input)) {
    return normalizeScenarios(input);
  }

  // If an object with scenarios array or message string
  if (typeof input === 'object') {
    if (Array.isArray(input.scenarios) && input.scenarios.length > 0) {
      return normalizeScenarios(input.scenarios);
    }
    if (typeof input.message === 'string') {
      return extractVideoScenarios(input.message);
    }
    return [];
  }

  if (typeof input !== 'string') return [];
  const text = input;

  const scenarioRegex = /####?\s*Option\s*(\d+):\s*([^\n\(`]+?)(?:\s*\(`([^`\)]+?)`\))?\s*\n\*\*Concept:\*\*\s*([^\n]+)([\s\S]*?)(?=>\s*\*\*Omni Prompt|####?\s*Option|\n\n\n|$)(?:>\s*\*\*Omni Prompt(?:\s*\(([^\)]+)\))?:\*\*\s*\n>\s*([^\n]+(?:\n>[^\n]+)*))?/gi;
  
  const scenarios = [];
  let match;
  while ((match = scenarioRegex.exec(text)) !== null) {
    const num = match[1];
    const title = (match[2] || '').trim();
    const genre = (match[3] || 'Cinematic').trim();
    const concept = (match[4] || '').trim();
    const tableBlock = match[5] || '';
    const scenarioId = (match[6] || `scenario_${num}`).trim();
    const rawOmni = match[7] ? match[7].replace(/^>\s*/gm, '').trim() : '';
    const metaphorMatch = tableBlock.match(/\*\*Metaphor & Story Bridge:\*\*\s*([^\n]+)/i);
    const narrativeMetaphor = metaphorMatch ? metaphorMatch[1].trim() : '';

    const shots = [];
    const shotRowRegex = /\|\s*\*\*Shot\s*(\d+)\*\*\s*\|\s*`([^`]+)`\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)\s*\|/gi;
    let sMatch;
    while ((sMatch = shotRowRegex.exec(tableBlock)) !== null) {
      shots.push({
        shotNumber: parseInt(sMatch[1], 10),
        timeRange: sMatch[2].trim(),
        action: sMatch[3].trim(),
        camera: sMatch[4].trim()
      });
    }

    // Extract optional styles payload
    let styles = [];
    const fullBlock = match[0] || (tableBlock + (match[7] || ''));
    const stylesMatch = fullBlock.match(/<!--\s*SCENARIO_STYLES_JSON:\s*([\s\S]*?)\s*-->/);
    if (stylesMatch) {
      try {
        const parsedStyles = JSON.parse(stylesMatch[1]);
        if (Array.isArray(parsedStyles) && parsedStyles.length > 0) {
          styles = parsedStyles.map(st => ({
            id: st.id || '',
            name: st.name || st.genre || 'Style',
            genre: st.genre || '',
            shots: (st.shots || []).map(sh => ({
              shotNumber: sh.shot_number ?? sh.shotNumber ?? 1,
              timeRange: sh.time_range ?? sh.timeRange ?? '00:00 - 00:02',
              action: sh.action ?? '',
              camera: sh.camera ?? '',
              lightingAtmosphere: sh.lighting_atmosphere ?? sh.lightingAtmosphere ?? ''
            })),
            omniPrompt: st.omni_prompt ?? st.omniPrompt ?? ''
          }));
        }
      } catch (e) {
        console.warn('Failed to parse SCENARIO_STYLES_JSON:', e);
      }
    }

    scenarios.push({
      id: scenarioId,
      number: num,
      title,
      genre,
      concept,
      narrativeMetaphor,
      shots,
      omniPrompt: rawOmni || concept,
      styles
    });
  }

  if (scenarios.length === 0 && text.includes('Creative Video Scenarios')) {
    const rawBlocks = text.split(/####?\s*Option\s*\d+:/i);
    for (let i = 1; i < rawBlocks.length; i++) {
      const blk = rawBlocks[i];
      const titleLine = blk.split('\n')[0] || '';
      scenarios.push({
        id: `scenario_${i}`,
        number: i,
        title: titleLine.replace(/\(`.*?`\)/, '').trim(),
        genre: 'Cinematic',
        concept: blk.substring(0, 200).trim(),
        shots: [],
        omniPrompt: blk.substring(0, 300).trim()
      });
    }
  }

  return scenarios;
}

// ---------------------------------------------------------------------------
// Scenario decks: computed once per chat update in App.svelte instead of every
// ChatMessage re-scanning the whole event list on every streamed token.

export function getToolResponseScenarios(event) {
  for (const part of event?.content?.parts || []) {
    const response = (part.function_response || part.functionResponse)?.response;
    if (!response) continue;
    if (Array.isArray(response.scenarios) && response.scenarios.length > 0) return response.scenarios;
    if (typeof response.message === 'string' && hasVideoScenarios(response.message)) return response.message;
  }
  return null;
}

/**
 * Returns Map<eventIndex, {source, locked}>. A deck is anchored to the tool response that
 * produced it (so it does not jump to the text message that streams in afterwards). Only the
 * most recent deck is interactive; older ones are shown locked.
 */
export function computeScenarioDecks(events) {
  const anchors = [];
  let turnHasToolDeck = false;
  (events || []).forEach((event, idx) => {
    if (!event) return;
    if (event.author === 'user') {
      turnHasToolDeck = false;
      return;
    }
    const fromTool = getToolResponseScenarios(event);
    if (fromTool) {
      anchors.push([idx, fromTool]);
      turnHasToolDeck = true;
      return;
    }
    if (!turnHasToolDeck) {
      // Legacy sessions where the model repeated the scenario markdown as text.
      const textPart = (event.content?.parts || []).find(p => p.text && hasVideoScenarios(p.text));
      if (textPart) anchors.push([idx, textPart.text]);
    }
  });
  const lastIdx = anchors.length ? anchors[anchors.length - 1][0] : -1;
  return new Map(anchors.map(([idx, source]) => [idx, { source, locked: idx !== lastIdx }]));
}

export const scenarioObjectCache = new WeakMap();

export const scenarioTextCache = new Map();

export function extractVideoScenariosCached(source) {
  if (!source) return [];
  if (typeof source === 'object') {
    if (!scenarioObjectCache.has(source)) scenarioObjectCache.set(source, extractVideoScenarios(source));
    return scenarioObjectCache.get(source);
  }
  if (!scenarioTextCache.has(source)) {
    if (scenarioTextCache.size > 30) scenarioTextCache.delete(scenarioTextCache.keys().next().value);
    scenarioTextCache.set(source, extractVideoScenarios(source));
  }
  return scenarioTextCache.get(source);
}
