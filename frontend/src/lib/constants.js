/**
 * Backwards-compatible barrel: the former 1.6k-line constants.js is split by concern.
 * New code should import from the specific module.
 */
export * from './markdown.js';
export * from './config.js';
export * from './agents.js';
export * from './legacy/textParsers.js';
export * from './downloads.js';
export * from './scenarios.js';
