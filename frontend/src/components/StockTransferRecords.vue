<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import type { StockAccount, Account } from "../api/accounts";
import type { Sku, StockTransfer } from "../api/warehouse";
import { stockStatuses } from "../presentation/warehouse";
import StockTransferDetail from "./StockTransferDetail.vue";
const props = defineProps<{
  targetCode?: string; items: StockTransfer[]; locations: StockAccount[]; trusted: boolean; skus: Sku[]; accounts: Account[];
  approvals?: boolean; loading?: boolean; error?: string;
}>();
const emit = defineEmits<{ changed: [] }>();
const detailDialog = ref<InstanceType<typeof StockTransferDetail> | null>(null);
const detailError = ref("");
const selectedCode = ref("");
function open(code: string) { selectedCode.value = code; void detailDialog.value?.open(code); }
function hasReport(item: StockTransfer) { return item.confirmations.some(report => report.status === "pending"); }
function actionLabel(item: StockTransfer) {
  if (item.status === "in_transit") {
    if (hasReport(item)) return props.trusted ? "核实并确认完成" : "查看报告";
    return props.trusted ? "确认完成" : "报告已完成";
  }
  return "查看详情";
}
onMounted(() => { if (props.targetCode) open(props.targetCode); });
watch(() => props.targetCode, code => { if (code) open(code); }, { flush: "post" });
watch(() => props.items, () => { detailError.value = ""; });
defineExpose({ busy: computed(() => detailDialog.value?.busy ?? false) });
</script>

<template>
  <p v-if="error || detailError" class="error" role="alert">{{ error || detailError }}</p>
  <div v-if="items.length" class="ledger-records stock-records" :aria-busy="loading">
    <table class="ledger-table">
      <colgroup><col class="subject-column" /><col class="route-column" /><col class="value-column" /><col class="state-column" /></colgroup>
      <thead><tr><th>事项 / 业务日期</th><th>来源 → 去向</th><th>货物</th><th>状态 / 下一步</th></tr></thead>
      <tbody>
        <tr v-for="item in items" :key="item.code" class="ledger-record" :class="[`record-state-${item.status}`, { selected: selectedCode === item.code, 'record-awaiting-confirmation': item.status === 'in_transit' && hasReport(item) }]" @click="open(item.code)">
          <td class="record-subject">
            <button class="record-open" aria-haspopup="dialog" :aria-label="`${trusted && item.status === 'pending' ? '查看并审批' : '查看'}货物转移 ${item.code}：${item.description || '未填写说明'}`" @click.stop="open(item.code)">{{ item.description || '未填写说明' }}</button>
            <div class="record-secondary"><time>{{ item.effective_date }}</time><span>{{ item.code }}</span><span v-for="tag in item.tags.slice(0, 2)" :key="tag" class="record-tag">{{ tag }}</span><span v-if="item.fund_references.length" class="fund-link-note">关联 {{ item.fund_references.length }} 笔资金</span></div>
          </td>
          <td class="record-route">
            <div class="route-flow">
              <span class="route-account route-source" :title="item.source_account_name">{{ item.source_account_name }}</span>
              <span class="route-arrow">→</span>
              <span class="route-account route-destination" :title="item.destination_account_name">{{ item.destination_account_name }}</span>
            </div>
          </td>
          <td class="record-value"><div v-for="line in item.lines.slice(0, 2)" :key="line.sku_code" class="goods-line"><span :title="`${line.sku_code} ${line.sku_name}`">{{ line.sku_name }}</span><strong>{{ line.quantity }} <small>{{ line.unit }}</small></strong></div><span v-if="item.lines.length > 2" class="more-goods">另有 {{ item.lines.length - 2 }} 种，选中查看</span></td>
          <td class="record-action stock-action"><div class="record-state-entry"><span :class="['ledger-state', `state-${item.status}`]">{{ stockStatuses[item.status] || item.status }}</span><span class="record-chevron" aria-hidden="true">›</span></div><small v-if="hasReport(item)" class="completion-report-note">有人报告完成，待确认</small><button v-if="item.status === 'in_transit'" class="record-action-button" :disabled="detailDialog?.busy" :class="{ attention: trusted && hasReport(item) }" @click.stop="open(item.code)">{{ actionLabel(item) }}</button></td>
        </tr>
      </tbody>
    </table>
  </div>
  <div v-else class="empty-state">{{ loading ? '正在读取货物转移' : '暂无符合条件的货物转移' }}</div>
  <StockTransferDetail ref="detailDialog" :locations="locations" :trusted="trusted" :skus="skus" :accounts="accounts" @changed="emit('changed')" @error="detailError = $event" />
</template>

<style scoped src="../styles/ledger-records.css"></style>
