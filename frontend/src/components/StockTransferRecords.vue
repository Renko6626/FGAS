<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import type { StockAccount, Account } from "../api/accounts";
import type { Sku, StockTransfer } from "../api/warehouse";
import { stockRecord } from "../presentation/records";
import TransferRecordList from "./TransferRecordList.vue";
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
const rows = computed(() => props.items.map(item => ({
  ...stockRecord(item),
  note: hasReport(item) ? "有人报告完成，待确认" : undefined,
  actionLabel: !props.approvals && item.status === "in_transit" ? actionLabel(item) : undefined,
})));
onMounted(() => { if (props.targetCode) open(props.targetCode); });
watch(() => props.targetCode, code => { if (code) open(code); }, { flush: "post" });
watch(() => props.items, () => { detailError.value = ""; });
defineExpose({ busy: computed(() => detailDialog.value?.busy ?? false) });
</script>

<template>
  <p v-if="error || detailError" class="error" role="alert">{{ error || detailError }}</p>
  <TransferRecordList v-if="items.length" :rows="rows" value-label="数量" :selected-code="selectedCode" :loading="loading" :action-busy="detailDialog?.busy" @open="open($event.code)" />
  <div v-else class="empty-state">{{ loading ? '正在读取货物转移' : '暂无符合条件的货物转移' }}</div>
  <StockTransferDetail ref="detailDialog" :locations="locations" :trusted="trusted" :skus="skus" :accounts="accounts" @changed="emit('changed')" @error="detailError = $event" />
</template>
