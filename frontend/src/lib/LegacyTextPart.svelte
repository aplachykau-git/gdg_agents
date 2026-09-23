<script>
  // Text rendering for sessions recorded before the structured "ui" contract existed:
  // the deliverable is recognised from the wording of the text (regex heuristics).
  import AgendaTimeline from './AgendaTimeline.svelte';
  import VariantCard from './VariantCard.svelte';
  import VideoPreviewCard from './VideoPreviewCard.svelte';
  import ReportDownloadCard from './ReportDownloadCard.svelte';
  import EmailDraftCard from './EmailDraftCard.svelte';
  import EventDateCard from './EventDateCard.svelte';
  import { renderMarkdown } from './markdown.js';
  import { hasVideoScenarios } from './scenarios.js';
  import {
    isAgendaOutput,
    parseResponseVariants,
    extractMediaAssets,
    cleanTextForMediaDisplay,
    extractDocumentAssets,
    cleanTextForDocumentDisplay,
    extractEmailDraft,
    extractEventDates,
  } from './legacy/textParsers.js';

  let { text, author = '', onRefine = () => {} } = $props();

  const emailDraft = $derived(extractEmailDraft(text, author));
  const eventData = $derived(extractEventDates(text, author));
  const media = $derived(extractMediaAssets(text));
  const doc = $derived(extractDocumentAssets(text));
</script>

{#if emailDraft}
  <EmailDraftCard {emailDraft} {onRefine} />
{:else if isAgendaOutput(text, author)}
  <AgendaTimeline rawText={text} {author} onRefine={(refinedText) => onRefine(refinedText)} />
{:else if eventData}
  <div class="markdown-body">{@html renderMarkdown(text)}</div>
  <EventDateCard {eventData} {onRefine} />
{:else if media}
  {@const cleanedText = cleanTextForMediaDisplay(text)}
  {#if cleanedText}
    <div class="markdown-body">{@html renderMarkdown(cleanedText)}</div>
  {/if}
  <VideoPreviewCard {media} {onRefine} />
{:else if doc}
  {@const cleanedText = cleanTextForDocumentDisplay(text)}
  {#if cleanedText}
    <div class="markdown-body">{@html renderMarkdown(cleanedText)}</div>
  {/if}
  <ReportDownloadCard {doc} />
{:else if hasVideoScenarios(text)}
  <!-- rendered as a scenario deck by ChatMessage -->
{:else}
  {@const variants = parseResponseVariants(text, author)}
  {#if variants.length === 1}
    <div class="markdown-body">{@html renderMarkdown(text)}</div>
  {:else}
    <VariantCard {variants} {onRefine} />
  {/if}
{/if}

