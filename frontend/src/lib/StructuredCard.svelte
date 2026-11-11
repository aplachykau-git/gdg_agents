<script>
  // Renders a backend "ui" payload (see ./ui/payloads.js) with the matching card component.
  import AgendaTimeline from './AgendaTimeline.svelte';
  import VariantCard from './VariantCard.svelte';
  import VideoPreviewCard from './VideoPreviewCard.svelte';
  import ReportDownloadCard from './ReportDownloadCard.svelte';
  import EmailDraftCard from './EmailDraftCard.svelte';
  import EventDateCard from './EventDateCard.svelte';
  import QrCodeCard from './QrCodeCard.svelte';
  import ReceiptSummaryCard from './ReceiptSummaryCard.svelte';
  import PostPlanCard from './PostPlanCard.svelte';
  import EventProfileCard from './EventProfileCard.svelte';
  import { toDocumentCard, toEmailDraft, toEventDates, toMediaCard, toQrCard, toVariants } from './ui/payloads.js';

  let { ui, author = '', onRefine = () => {}, onSend = () => {}, isBusy = false } = $props();
</script>

{#if ui?.type === 'post_variants'}
  <VariantCard variants={toVariants(ui)} {onRefine} />
{:else if ui?.type === 'agenda'}
  <AgendaTimeline rawText={ui.text} {author} onRefine={(refinedText) => onRefine(refinedText)} />
{:else if ui?.type === 'email_draft'}
  <EmailDraftCard emailDraft={toEmailDraft(ui)} {onRefine} />
{:else if ui?.type === 'meetup_dates'}
  <EventDateCard eventData={toEventDates(ui)} {onRefine} />
{:else if ui?.type === 'document'}
  <ReportDownloadCard doc={toDocumentCard(ui)} />
{:else if ui?.type === 'qr_code'}
  <QrCodeCard qr={toQrCard(ui)} />
{:else if ui?.type === 'event_profile'}
  <EventProfileCard payload={ui} {isBusy} {onSend} />
{:else if ui?.type === 'post_plan'}
  <PostPlanCard plan={ui} />
{:else if ui?.type === 'receipt_summary'}
  <ReceiptSummaryCard summary={ui} />
{:else if ui?.type === 'media'}
  <VideoPreviewCard media={toMediaCard(ui)} {onRefine} />
{/if}
