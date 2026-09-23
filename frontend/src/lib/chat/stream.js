/**
 * Merge one ADK SSE event into the (mutable) event list.
 *
 * Partial chunks of the same event id carry text deltas and are appended; the final
 * (`partial === false`) event carries the consolidated payload and replaces them.
 */
export function mergeStreamEvent(list, eventObj) {
  const existingIdx = eventObj.id ? list.findLastIndex((e) => e.id === eventObj.id) : -1;
  if (existingIdx === -1) {
    list.push(eventObj);
    return;
  }
  if (eventObj.partial === false) {
    // Final consolidated payload from ADK replaces the accumulated partial chunks.
    list[existingIdx] = eventObj;
    return;
  }
  const existingEv = list[existingIdx];
  const newText = eventObj.content?.parts?.[0]?.text || "";
  const prevText = existingEv.content?.parts?.[0]?.text || "";
  list[existingIdx] = {
    ...eventObj,
    content: {
      ...eventObj.content,
      parts: [
        {
          ...(eventObj.content?.parts?.[0] || {}),
          text: prevText + newText,
        },
      ],
    },
  };
}

