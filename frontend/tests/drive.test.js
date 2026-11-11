import test from 'node:test';
import assert from 'node:assert/strict';
import { GOOGLE_MIME, readPlan, sheetRange, sheetsToText, textAttachment, utf8ToBase64, valuesToCsv } from '../src/lib/google/drive.js';

test('read plan per Drive type', () => {
  assert.equal(readPlan(GOOGLE_MIME.document).kind, 'export');
  assert.equal(readPlan(GOOGLE_MIME.document).exportMime, 'text/markdown');
  assert.equal(readPlan(GOOGLE_MIME.spreadsheet).kind, 'sheets');
  assert.equal(readPlan(GOOGLE_MIME.presentation).exportMime, 'text/plain');
  assert.equal(readPlan(GOOGLE_MIME.folder).kind, 'unsupported');
  assert.equal(readPlan('application/vnd.google-apps.form').kind, 'unsupported');
  assert.equal(readPlan('image/jpeg').kind, 'download');
  assert.equal(readPlan('application/pdf').kind, 'download');
});

test('sheet ranges are quoted when needed', () => {
  assert.equal(sheetRange('Main'), 'Main');
  assert.equal(sheetRange('Speakers & Schedule'), "'Speakers & Schedule'");
  assert.equal(sheetRange("Alex's ideas"), "'Alex''s ideas'");
});

test('values to csv and all tabs to text', () => {
  assert.equal(valuesToCsv([['a', 'b,c'], ['He said "hi"', ''], []]), 'a,"b,c"\n"He said ""hi""",\n');
  const text = sheetsToText('DevFest KRK 26', [{ title: 'Main', values: [['x']] }, { title: 'Empty', values: [] }]);
  assert.match(text, /^# DevFest KRK 26/);
  assert.match(text, /## Sheet: Main\nx/);
  assert.match(text, /## Sheet: Empty\n\(empty\)/);
});

test('utf-8 text attachment keeps Polish characters and the source link', () => {
  const att = textAttachment('plan.md', 'Kraków – zażółć', { id: '1', name: 'Plan', url: 'https://docs.google.com/document/d/1' });
  assert.equal(att.type, 'text/plain');
  assert.equal(att.source, 'drive');
  const decoded = new TextDecoder().decode(Uint8Array.from(atob(att.data), (c) => c.charCodeAt(0)));
  assert.match(decoded, /^\[Google Drive file: Plan \(https:\/\/docs\.google\.com\/document\/d\/1\)\]/);
  assert.match(decoded, /Kraków – zażółć/);
  assert.equal(utf8ToBase64('ó'), 'w7M=');
});
