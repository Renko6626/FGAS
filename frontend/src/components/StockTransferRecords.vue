<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { NButton } from "naive-ui";
import { money, statuses as fundStatuses } from "../presentation/funds";
import { type StockAccount, type Account } from "../api/accounts";
import { type Sku } from "../api/warehouse";
import { type StockTransfer } from "../api/warehouse";
import { stockStatuses } from "../presentation/warehouse";
import AccountRoute from "./AccountRoute.vue";
import AccountLabel from "./AccountLabel.vue";
import StockTransferDetail from "./StockTransferDetail.vue";
const props = defineProps<{
  targetCode?: string;
  items: StockTransfer[];
  locations: StockAccount[];
  trusted: boolean;
  skus: Sku[];
  accounts: Account[];
  approvals?: boolean;
  loading?: boolean;
  error?: string;
}>();
const emit = defineEmits<{
  changed: [];
}>();
const detailDialog = ref<InstanceType<typeof StockTransferDetail> | null>(null);
const detailError = ref("");
onMounted(() => { if (props.targetCode) void detailDialog.value?.open(props.targetCode); });
watch(() => props.targetCode, (code) => {
  if (code) void detailDialog.value?.open(code);
}, { flush: "post" });

watch(() => props.items, () => {
  detailError.value = "";
});
defineExpose({ busy: computed(() => detailDialog.value?.busy ?? false) });
</script>

<template>
  <p v-if="error || detailError" class="error">{{ error || detailError }}</p>
  <div v-if="items.length" class="transfer-list">
    <article v-for="t in items" :key="t.code" class="transfer-record">
      <div class="record-main">
        <div class="record-route">
          <AccountRoute :accounts="locations" :source-id="t.source_account_code" :destination-id="t.destination_account_code" :source-name="t.source_account_name" :destination-name="t.destination_account_name" />
        </div>
        <div class="record-state">
          <div><span class="status-pill" :class="`status-${t.status}`">{{ stockStatuses[t.status] || t.status }}</span><span v-if="t.confirmations.some(c => c.status === 'pending')" class="confirmation-state">完成申报待审阅</span></div>
          <NButton :disabled="detailDialog?.busy" @click="detailDialog?.open(t.code)">{{ trusted && t.status === 'pending' ? '审批' : t.confirmations.some(c => c.status === 'pending') && trusted ? '审阅完成申报' : t.status === 'in_transit' && !t.confirmations.some(c => c.status === 'pending') ? '查看并申报' : '查看详情' }}</NButton>
        </div>
      </div>
      <div class="record-meta"><span>{{ t.effective_date }}</span><span>{{ t.code }}</span><span v-if="t.description" class="record-note">{{ t.description }}</span><span v-for="tag in t.tags" :key="tag" class="tag">{{ tag }}</span></div>
      <div class="record-lower">
        <div class="item-preview" aria-label="货物预览">
          <div v-for="line in t.lines.slice(0, 3)" :key="line.sku_code" class="preview-item"><AccountLabel :name="line.sku_name" :code="line.sku_code" :url="skus.find(s => s.code === line.sku_code)?.avatar_url" /><strong>{{ line.quantity }} {{ line.unit }}</strong></div>
          <span v-if="t.lines.length > 3" class="more-items">等 {{ t.lines.length }} 种货物</span>
        </div>
        <div class="record-funds"><span class="funds-label">关联资金</span><template v-if="t.fund_references.length"><span v-for="f in t.fund_references" :key="f.code" class="fund-reference">¥ {{ money(f.amount_minor) }} <span class="status-pill" :class="`status-${f.status}`">{{ fundStatuses[f.status] || f.status }}</span></span></template><span v-else>未关联</span></div>
      </div>
    </article>
  </div>
  <div v-else class="empty-state">{{ loading ? '正在读取货物转移' : '暂无符合条件的货物转移' }}</div>
  <StockTransferDetail ref="detailDialog" :locations="locations" :trusted="trusted" :skus="skus" :accounts="accounts"
    @changed="emit('changed')" @error="detailError = $event" />
</template>

<style scoped>
.transfer-list { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); align-items:start; gap:10px; }
.transfer-record { border:1px solid #e3e8ec; border-radius:7px; padding:14px 16px; min-width:0; }
.record-main { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px 14px; }
.record-route { min-width:0; }
.record-route :deep(.account-route) { flex-wrap:nowrap; }
.record-route :deep(.account-label-name small) { display:inline; margin-left:6px; font-size:11px; color:#66707c; }
.record-state { display:flex; align-items:center; justify-content:flex-end; gap:12px; flex-shrink:0; }
.record-state > div { display:flex; flex-wrap:wrap; justify-content:flex-end; align-items:center; gap:6px; }
.confirmation-state { color:#885f20; font-size:12px; }
.record-meta { display:flex; align-items:center; flex-wrap:wrap; gap:5px 12px; margin-top:10px; color:#66707c; font-size:12px; }
.record-note { color:#35404c; font-size:13px; overflow-wrap:anywhere; }
.record-meta .tag { margin:0; }
.record-lower { display:flex; flex-wrap:wrap; align-items:flex-start; justify-content:space-between; gap:10px 16px; margin-top:10px; padding-top:10px; border-top:1px solid #edf0f2; }
.item-preview { display:flex; flex-wrap:wrap; gap:8px 18px; min-width:0; }
.preview-item { display:flex; align-items:center; gap:6px; min-width:0; font-size:13px; }
.preview-item :deep(.account-avatar) { width:24px; height:24px; font-size:12px; }
.preview-item :deep(.account-label-name small) { display:inline; margin:0 0 0 6px; font-size:11px; }
.preview-item strong { white-space:nowrap; }
.more-items,.record-funds { color:#66707c; font-size:12px; }
.more-items { align-self:center; white-space:nowrap; }
.record-funds { display:flex; align-items:center; flex-wrap:wrap; justify-content:flex-end; gap:6px; flex-shrink:0; }
.funds-label { color:#88919a; }
.fund-reference { display:inline-flex; align-items:center; gap:4px; white-space:nowrap; }
@media(max-width:1100px) { .transfer-list { grid-template-columns:1fr; } }
@media(max-width:760px) { .record-main { align-items:flex-start; flex-wrap:wrap; } .record-state { width:100%; justify-content:space-between; } .record-lower { flex-wrap:wrap; } .record-funds { justify-content:flex-start; } .record-route :deep(.account-route) { flex-wrap:wrap; } }
</style>
