// Run with: npm test   (node's built-in test runner, no extra dependencies)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  computeUiCards,
  getEventUiPayload,
  toDocumentCard,
  toEmailDraft,
  toEventDates,
  toMediaCard,
  toQrCard,
  toVariants,
  toVideoOutputChoice,
} from '../src/lib/ui/payloads.js';
import { computeScenarioDecks } from '../src/lib/scenarios.js';

const user = (text) => ({ author: 'user', content: { parts: [{ text }] } });
const toolResponse = (name, response, extra = {}) => ({
  author: 'video_editor',
  content: { parts: [{ function_response: { name, response }, ...extra }] },
});
const modelText = (text, customMetadata) => ({ author: 'linkedin_post_generator', content: { parts: [{ text }] }, customMetadata });

test('payload is read from tool results and from text metadata', () => {
  assert.equal(getEventUiPayload(toolResponse('render_video', { ui: { type: 'media', urls: {} } })).type, 'media');
  assert.equal(getEventUiPayload(modelText('x', { ui: { type: 'post_variants', variants: [] } })).type, 'post_variants');
  assert.equal(getEventUiPayload(modelText('plain')), null);
});

test('turns with a structured payload skip legacy parsing for all their events', () => {
  const events = [
    user('render 1'),
    toolResponse('render_video', { ui: { type: 'media', urls: { video: 'https://x/v.mp4' } } }),
    { author: 'video_editor', content: { parts: [{ text: '- [Video](https://x/v.mp4)' }] } },
    user('thanks'),
    { author: 'video_editor', content: { parts: [{ text: 'You are welcome' }] } },
  ];
  const { cards, structuredTurnEvents } = computeUiCards(events);
  assert.deepEqual([...cards.keys()], [1]);
  assert.deepEqual([...structuredTurnEvents].sort(), [1, 2]);
});

test('scenario decks: every proposal gets its own deck, only the latest is interactive', () => {
  const scenarios = [{ id: 'a', title: 'A', shots: [] }];
  const events = [
    user('card'),
    toolResponse('propose_scenarios', { scenarios }),
    user('new ideas'),
    // A2A delivers the remote agent's tool results as thought parts
    toolResponse('propose_scenarios', { scenarios: [...scenarios] }, { thought: true }),
  ];
  const decks = computeScenarioDecks(events);
  assert.deepEqual([...decks.entries()].map(([i, d]) => [i, d.locked]), [[1, true], [3, false]]);
});

test('adapters produce the props the existing cards expect', () => {
  const media = toMediaCard({ urls: { video: 'file:///tmp/renders/card.mp4', poster: 'https://x/p.png' }, speaker: { name: 'Jane' } });
  assert.equal(media.videoUrl, '/renders/card.mp4');
  assert.equal(media.posterUrl, 'https://x/p.png');
  assert.equal(media.speakerName, 'Jane');

  const doc = toDocumentCard({ url: 'https://docs.google.com/document/d/abc/edit', kind: 'expense_report', title: 'Report' });
  assert.equal(doc.isGoogleDoc, true);
  assert.equal(doc.gdocUrl, 'https://docs.google.com/document/d/abc/edit');

  const email = toEmailDraft({ subject: 'Keys', body: 'Hello' });
  assert.equal(email.fullText, 'Subject: Keys\n\nHello');
  assert.match(email.gmailUrl, /su=Keys/);

  const variants = toVariants({ intro: 'Hi', variants: [{ number: 1, name: 'A', body: 'b' }] });
  assert.deepEqual(variants, [{ header: 'Introduction', body: 'Hi' }, { header: 'Variant 1: A', body: 'b' }]);

  const dates = toEventDates({ event_title: 'Build with AI', dates: [{ date: '2026-10-14', weekday: 'Wednesday', primary: true }] });
  assert.equal(dates.primaryDate.fullDateStr, 'Wednesday, October 14, 2026');
  assert.match(dates.primaryDate.gcalUrl, /dates=20261014T180000\/20261014T213000/);
  assert.equal(dates.totalOptions, 1);
});

test('A2A thought-only text events are not rendered as empty bubbles', async () => {
  const { isIntermediateEvent } = await import('../src/lib/agents.js');
  assert.equal(isIntermediateEvent({ author: 'video_editor', content: { parts: [{ text: 'hi', thought: true }] } }), true);
  assert.equal(isIntermediateEvent({ author: 'video_editor', content: { parts: [{ text: 'hi' }] } }), false);
  assert.equal(
    isIntermediateEvent({ author: 'video_editor', content: { parts: [{ function_response: { name: 'x', response: {} }, thought: true }] } }),
    false,
  );
});

test('stream merge appends partial text and replaces with the final event', async () => {
  const { mergeStreamEvent } = await import('../src/lib/chat/stream.js');
  const list = [];
  mergeStreamEvent(list, { id: 'e1', partial: true, content: { parts: [{ text: 'Hel' }] } });
  mergeStreamEvent(list, { id: 'e1', partial: true, content: { parts: [{ text: 'lo' }] } });
  assert.equal(list[0].content.parts[0].text, 'Hello');
  mergeStreamEvent(list, { id: 'e1', partial: false, content: { parts: [{ text: 'Hello!' }] }, customMetadata: { ui: { type: 'agenda' } } });
  assert.equal(list.length, 1);
  assert.equal(list[0].customMetadata.ui.type, 'agenda');
});

test('qr_code payload becomes a QR card and the agent is recognised', async () => {
  const card = toQrCard({
    type: 'qr_code',
    link: 'https://gdg.dev',
    svg_url: '/results/qr_gdg-dev_1234abcd.svg',
    png_url: '/results/qr_gdg-dev_1234abcd.png',
    filename: 'qr_gdg-dev_1234abcd',
    color: '#1A73E8',
    background: 'transparent',
  });
  assert.equal(card.svgUrl, '/results/qr_gdg-dev_1234abcd.svg');
  assert.equal(card.transparent, true);
  assert.equal(card.background, '');
  const { getFriendlyToolCall, getAgentTheme, resolveAgentId } = await import('../src/lib/agents.js');
  assert.equal(getAgentTheme('qr_code_generator').label, 'QR Codes');
  assert.equal(resolveAgentId('qr_code_generator'), 'qr_code_generator');
  assert.match(getFriendlyToolCall('generate_qr_code', { link: 'https://gdg.dev' }), /QR code for https:\/\/gdg.dev/);
});

test('video_output_choice card is suppressed when resolved in the same turn and marked resolved later', () => {
  const sameTurnCover = [
    user('Make only a static 4K cover'),
    toolResponse('update_speaker', { ui: { type: 'video_output_choice', speaker: { name: 'Jane' }, media_kind: 'image' } }),
    toolResponse('render_cover', { ui: { type: 'media', urls: { poster: 'https://x/cover.png' } } }),
  ];
  const sameTurnCards = computeUiCards(sameTurnCover);
  assert.equal(sameTurnCards.cards.has(1), false);
  assert.equal(sameTurnCards.cards.get(2)?.type, 'media');

  const sameTurnScenarios = [
    user('Make an animated video'),
    toolResponse('update_speaker', { ui: { type: 'video_output_choice', speaker: { name: 'Jane' }, media_kind: 'image' } }),
    toolResponse('propose_scenarios', { scenarios: [{ id: 's1', title: 'S1', shots: [] }] }),
  ];
  const scenarioCards = computeUiCards(sameTurnScenarios);
  assert.equal(scenarioCards.cards.has(1), false);

  const twoTurns = [
    user('Speaker details + photo'),
    toolResponse('update_speaker', { ui: { type: 'video_output_choice', speaker: { name: 'Jane' }, media_kind: 'image' } }),
    user('Only static 4K cover'),
    toolResponse('render_cover', { ui: { type: 'media', urls: { poster: 'https://x/cover.png' } } }),
  ];
  const twoTurnCards = computeUiCards(twoTurns);
  assert.equal(twoTurnCards.cards.get(1)?.type, 'video_output_choice');
  assert.equal(twoTurnCards.cards.get(1)?.resolved, true);
  assert.equal(twoTurnCards.cards.get(3)?.type, 'media');

  const adapted = toVideoOutputChoice({
    type: 'video_output_choice',
    speaker: { name: 'Jane' },
    avatar_url: 'file:///tmp/workspaces/w1/renders/prepared_avatar_abc123.png',
  });
  assert.equal(adapted.avatarUrl, '/renders/prepared_avatar_abc123.png');
});
