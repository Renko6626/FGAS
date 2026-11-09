<script setup lang="ts">
import type { TransferRecordRow } from '../presentation/records';

defineProps<{
  rows: TransferRecordRow[];
  valueLabel?: string;
  selectedCode?: string;
  loading?: boolean;
  actionBusy?: boolean;
}>();
const emit = defineEmits<{ open: [row: TransferRecordRow] }>();
function recordDate(row: TransferRecordRow) {
  return row.createdAt ? new Date(row.createdAt).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }) : row.date;
}
function recordLabel(row: TransferRecordRow) {
  return `查看${row.kind === 'funds' ? '资金流水' : '货物转移'} ${row.code}：${row.title}`;
}
</script>

<template>
  <div class="ledger-records" :aria-busy="loading">
    <table class="ledger-table">
      <colgroup><col class="subject-column" /><col class="value-column" /><col class="account-column" /><col class="arrow-column" /><col class="account-column" /><col class="state-column" /></colgroup>
      <thead><tr><th>事项</th><th class="value-heading">{{ valueLabel || '金额 / 数量' }}</th><th class="account-heading source-heading">来源</th><th class="arrow-heading"><span aria-hidden="true">→</span><span class="visually-hidden">方向</span></th><th class="account-heading">去向</th><th class="state-heading">状态 / 下一步</th></tr></thead>
      <tbody>
        <tr v-for="row in rows" :key="row.code" class="ledger-record" :class="[`record-state-${row.status}`, { selected: selectedCode === row.code, 'record-awaiting-confirmation': row.status === 'in_transit' && row.reportPending }]" @click="emit('open', row)">
          <td colspan="2" class="record-subject">
            <div class="record-main-grid">
              <template v-if="row.goods.length">
                <template v-for="line in row.goods.slice(0, 2)" :key="line.sku_code">
                  <button class="record-open" :title="`${line.sku_code} ${line.sku_name}`" aria-haspopup="dialog" :aria-label="recordLabel(row)" @click.stop="emit('open', row)">{{ line.sku_name }}</button>
                  <div class="goods-value"><strong>{{ line.quantity }}</strong> <small>{{ line.unit }}</small></div>
                </template>
                <span v-if="row.goods.length > 2" class="more-goods">另有 {{ row.goods.length - 2 }} 种，选中查看</span>
                <p v-if="row.description" class="record-description">{{ row.description }}</p>
              </template>
              <template v-else>
                <button class="record-open" aria-haspopup="dialog" :aria-label="recordLabel(row)" @click.stop="emit('open', row)">{{ row.title }}</button>
                <strong v-if="row.amount !== undefined" class="record-money"><small>¥</small> {{ row.amount }}</strong>
              </template>
              <div class="record-secondary">
                <span class="record-kind">{{ row.kind === 'funds' ? '资金' : '货物' }}</span><span>{{ row.code }}</span>
                <time :datetime="row.createdAt || row.date" :title="row.createdAt ? `创建于 ${new Date(row.createdAt).toLocaleString('zh-CN')}；业务日期 ${row.date}` : undefined">{{ recordDate(row) }}</time>
                <span v-for="(text, index) in row.metadata" :key="index">{{ text }}</span>
              </div>
              <div class="mobile-route" aria-label="来源与去向"><span :title="row.source">{{ row.source }}</span><span class="route-arrow" aria-label="转向">→</span><span :title="row.destination">{{ row.destination }}</span></div>
            </div>
          </td>
          <td class="record-account source-account" :title="row.source">{{ row.source }}</td>
          <td class="record-arrow" aria-label="转向">→</td>
          <td class="record-account" :title="row.destination">{{ row.destination }}</td>
          <td class="record-action">
            <div class="record-state-entry"><span class="ledger-state" :class="`state-${row.status}`"><i aria-hidden="true"></i>{{ row.statusLabel }}</span><span class="record-chevron" aria-hidden="true">›</span></div>
            <small v-if="row.note" class="completion-report-note">{{ row.note }}</small>
            <slot name="actions" :row="row"><button v-if="row.actionLabel" class="record-action-button" :class="{ attention: row.reportPending }" :disabled="actionBusy" @click.stop="emit('open', row)">{{ row.actionLabel }}</button></slot>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped src="../styles/ledger-records.css"></style>
