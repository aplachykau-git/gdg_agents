<script>
  // What the receipt scanner recognised (payload type "receipt_summary"): every receipt with its
  // line items, totals by category and currency, budget check, and a plain-text / CSV copy.
  import { AlertTriangle, Check, ChevronRight, Copy, FileSpreadsheet, Receipt } from '@lucide/svelte';
  import ResultCard from './ui/ResultCard.svelte';
  import { formatMoney, receiptSummaryCsv } from './ui/payloads.js';

  let { summary = {} } = $props();

  let copied = $state(false);
  const target = $derived(summary.target_currency || '');
  const communityCurrency = $derived(summary.community_currency || target);
  const receipts = $derived(summary.receipts || []);
  const budget = $derived(summary.budget || null);
  const maxCategory = $derived(Math.max(1, ...(summary.totals_by_category || []).map((c) => c.amount)));

  const dateRange = $derived.by(() => {
    const dates = receipts.map((r) => r.date).filter(Boolean).sort();
    if (!dates.length) return '';
    const fmt = (iso) => {
      const d = new Date(`${iso}T12:00:00`);
      return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
    };
    return dates[0] === dates[dates.length - 1] ? fmt(dates[0]) : `${fmt(dates[0])} – ${fmt(dates[dates.length - 1])}`;
  });

  const subtitle = $derived(
    [`${receipts.length} ${receipts.length === 1 ? 'receipt' : 'receipts'}`, dateRange].filter(Boolean).join(' · ')
  );

  const status = $derived.by(() => {
    if (budget?.over_budget) return { text: 'Over budget', tone: 'danger' };
    if (summary.warnings_count) return { text: `${summary.warnings_count} to check`, tone: 'warn' };
    return { text: 'Recognised', tone: 'ok' };
  });

  async function copyText() {
    try {
      await navigator.clipboard.writeText(summary.text || '');
      copied = true;
      setTimeout(() => (copied = false), 2000);
    } catch (e) {
      console.warn('Copy failed', e);
    }
  }

  function downloadCsv() {
    const blob = new Blob([receiptSummaryCsv(summary)], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `receipts_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
</script>

<ResultCard accent="var(--agent-receipt)" accentBg="var(--bg-receipt)" icon={Receipt} title="Recognised receipts" {subtitle} status={status.text} statusTone={status.tone}>
  <div class="kpis">
    <div class="kpi">
      <span class="rc-label">Total</span>
      <span class="kpi-value">{summary.grand_total != null ? formatMoney(summary.grand_total, target) : '—'}</span>
      {#if communityCurrency && communityCurrency !== target && summary.community_total != null}
        <span class="rc-muted">≈ {formatMoney(summary.community_total, communityCurrency)}</span>
      {/if}
      {#if (summary.totals_by_currency || []).length > 1 || (summary.totals_by_currency?.[0] && summary.totals_by_currency[0].currency !== target && summary.totals_by_currency[0].currency !== communityCurrency)}
        <span class="rc-muted">{(summary.totals_by_currency || []).map((c) => formatMoney(c.amount, c.currency)).join(' + ')}</span>
      {:else if (summary.totals_by_currency || []).length === 1 && summary.totals_by_currency[0].currency !== target && communityCurrency === target}
        <span class="rc-muted">{formatMoney(summary.totals_by_currency[0].amount, summary.totals_by_currency[0].currency)}</span>
      {/if}
    </div>
    {#if budget}
      <div class="kpi">
        <span class="rc-label">Budget</span>
        <span class="kpi-value">{formatMoney(budget.amount, budget.currency)}</span>
        {#if budget.remaining != null}
          <span class="rc-chip {budget.over_budget ? 'danger' : 'ok'}">
            {budget.over_budget ? 'over by' : 'left'} {formatMoney(Math.abs(budget.remaining), budget.currency)}
          </span>
        {/if}
      </div>
    {/if}
    {#if (summary.totals_by_category || []).length}
      <div class="kpi categories">
        <span class="rc-label">By category</span>
        {#each summary.totals_by_category as cat}
          <div class="cat-row">
            <span class="cat-name">{cat.category}</span>
            <span class="cat-bar"><span style="width: {Math.max(4, (cat.amount / maxCategory) * 100)}%"></span></span>
            <span class="cat-amount">{formatMoney(cat.amount, target)}</span>
          </div>
        {/each}
      </div>
    {/if}
  </div>

  <ul class="receipts">
    {#each receipts as row (row.index)}
      <li>
        <details open={receipts.length <= 3 || row.warnings?.length > 0}>
          <summary>
            <ChevronRight size={14} class="chev" />
            <span class="r-main">
              <span class="r-merchant">{row.merchant}</span>
              <span class="r-meta">
                {#if row.date}<span>{row.date}</span>{/if}
                <span class="rc-chip neutral">{row.category}</span>
                {#if row.warnings?.length}<span class="rc-chip warn"><AlertTriangle size={11} />{row.warnings.length}</span>{/if}
              </span>
            </span>
            <span class="r-total">
              <span>{formatMoney(row.total, row.currency)}</span>
              {#if row.total_target != null && row.currency !== target}
                <span class="rc-muted">≈ {formatMoney(row.total_target, target)}</span>
              {/if}
              {#if communityCurrency && communityCurrency !== target && row.total_community != null && row.currency !== communityCurrency}
                <span class="rc-muted">≈ {formatMoney(row.total_community, communityCurrency)}</span>
              {/if}
            </span>
          </summary>

          {#if row.items?.length}
            <table class="items">
              <thead>
                <tr><th>Item</th><th class="num col-qty">Qty</th><th class="num col-money">Price</th><th class="num col-money">Sum</th></tr>
              </thead>
              <tbody>
                {#each row.items as item}
                  <tr>
                    <td>{item.name}</td>
                    <td class="num">{item.quantity ?? ''}</td>
                    <td class="num">{item.unit_price != null ? formatMoney(item.unit_price, '') : ''}</td>
                    <td class="num">{item.total != null ? formatMoney(item.total, '') : '—'}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          {/if}

          {#if row.tax != null || row.payment_method || row.document_number}
            <p class="r-extra rc-muted">
              {[row.tax != null ? `Tax ${formatMoney(row.tax, row.currency)}` : '', row.payment_method ? `Paid by ${row.payment_method}` : '', row.document_number ? `No. ${row.document_number}` : '']
                .filter(Boolean)
                .join(' · ')}
            </p>
          {/if}

          {#each row.warnings || [] as warning}
            <p class="r-warning"><AlertTriangle size={13} />{warning}</p>
          {/each}
        </details>
      </li>
    {/each}
  </ul>

  {#if summary.conversion_note}
    <p class="rc-muted note">
      {summary.conversion_note}
      {#if (summary.rates || []).length}
        ({summary.rates.map((r) => `1 ${r.currency} = ${r.rate.toFixed(4)} ${r.to}`).join(', ')})
      {/if}
    </p>
  {/if}

  {#snippet actions()}
    <button class="rc-btn primary" onclick={copyText}>
      {#if copied}<Check size={14} />Copied{:else}<Copy size={14} />Copy as text{/if}
    </button>
    <button class="rc-btn" onclick={downloadCsv}><FileSpreadsheet size={14} />CSV</button>
  {/snippet}
</ResultCard>

<style>
  .kpis {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 10px;
  }

  .kpi {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 10px 12px;
    border-radius: var(--radius-sm);
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    min-width: 0;
  }

  .kpi .rc-chip {
    align-self: flex-start;
  }

  .kpi.categories {
    grid-column: span 2;
  }

  @container (max-width: 520px) {
    .kpi.categories {
      grid-column: auto;
    }
  }

  .kpi-value {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-primary);
    font-variant-numeric: tabular-nums;
  }

  .cat-row {
    display: grid;
    grid-template-columns: minmax(70px, max-content) 1fr max-content;
    align-items: center;
    gap: 8px;
    font-size: 12px;
  }

  .cat-name {
    color: var(--text-secondary);
  }

  .cat-bar {
    height: 6px;
    border-radius: 3px;
    background: var(--bg-surface-variant);
    overflow: hidden;
  }

  .cat-bar span {
    display: block;
    height: 100%;
    border-radius: 3px;
    background: var(--agent-receipt);
  }

  .cat-amount {
    color: var(--text-primary);
    font-variant-numeric: tabular-nums;
  }

  .receipts {
    list-style: none;
    margin: 0;
    padding: 0;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    overflow: hidden;
  }

  .receipts li + li {
    border-top: 1px solid var(--border-subtle);
  }

  summary {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    cursor: pointer;
    list-style: none;
  }

  summary::-webkit-details-marker {
    display: none;
  }

  summary:hover {
    background: var(--bg-surface-elevated);
  }

  summary :global(.chev) {
    flex-shrink: 0;
    color: var(--text-tertiary);
    transition: transform 0.15s ease;
  }

  details[open] > summary :global(.chev) {
    transform: rotate(90deg);
  }

  .r-main {
    display: flex;
    flex-direction: column;
    gap: 3px;
    min-width: 0;
    flex: 1 1 auto;
  }

  .r-merchant {
    font-size: 13.5px;
    font-weight: 600;
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .r-meta {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    font-size: 12px;
    color: var(--text-tertiary);
  }

  .r-total {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 2px;
    font-size: 13.5px;
    font-weight: 600;
    color: var(--text-primary);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }

  .r-total .rc-muted {
    font-weight: 400;
  }

  .items {
    width: calc(100% - 24px);
    margin: 0 12px 10px;
    border-collapse: collapse;
    table-layout: fixed;
    font-size: 12.5px;
  }

  .items th {
    padding: 4px 6px;
    text-align: left;
    font-size: 11px;
    font-weight: 600;
    color: var(--text-tertiary);
    border-bottom: 1px solid var(--border-subtle);
  }

  .items td {
    padding: 5px 6px;
    color: var(--text-secondary);
    border-bottom: 1px solid var(--border-subtle);
  }

  .items tr:last-child td {
    border-bottom: none;
  }

  .items .col-qty {
    width: 48px;
  }

  .items .col-money {
    width: 84px;
  }

  .items td:first-child {
    overflow-wrap: anywhere;
  }

  .items .num {
    text-align: right;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }

  .r-extra {
    margin: 0 12px 10px;
  }

  .r-warning {
    display: flex;
    align-items: flex-start;
    gap: 6px;
    margin: 0 12px 10px;
    font-size: 12.5px;
    color: var(--status-warning);
  }

  .r-warning :global(svg) {
    flex-shrink: 0;
    margin-top: 2px;
  }

  .note {
    margin: 0;
  }
</style>
