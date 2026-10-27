<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { NButton } from "naive-ui";
import { type Transfer } from "../api/funds";
import { money, statuses } from "../presentation/funds";
import { type Account } from "../api/accounts";
import AccountRoute from "./AccountRoute.vue";
import TransferDetail from "./TransferDetail.vue";
const props = defineProps<{
  targetCode?: string;
  items: Transfer[];
  accounts: Account[];
  approvals: boolean;
  trusted: boolean;
  loading?: boolean;
  hasFilters: boolean;
  hideCreate?: boolean;
  error?: string;
}>();
const emit = defineEmits<{
  changed: [];
  notice: [string];
  create: [];
  reset: [];
}>();
const detailDialog = ref<InstanceType<typeof TransferDetail> | null>(null);
const detailError = ref("");
onMounted(() => { if (props.targetCode) void detailDialog.value?.open({ code: props.targetCode }); });
watch(() => props.targetCode, (code) => {
  if (code) void detailDialog.value?.open({ code });
}, { flush: "post" });

watch(() => props.items, () => {
  detailError.value = "";
});
</script>

<template>
  <p v-if="error || detailError" class="error" role="alert">{{ error || detailError }}</p>
  <div v-if="!items.length" class="empty-state">
    <p>
      {{
        loading
          ? "正在读取流水"
          : hasFilters
            ? "没有符合条件的流水"
            : approvals
              ? "暂无待审批的资金申请"
              : "暂无资金流水"
      }}
    </p>
    <NButton v-if="hasFilters" @click="emit('reset')">清空筛选</NButton
    ><NButton v-else-if="!approvals && !hideCreate" @click="emit('create')"
      >登记资金</NButton
    >
  </div>
  <div v-else class="transfer-list">
    <article v-for="t in items" :key="t.code" class="transfer-record">
      <div class="record-main">
        <div class="record-route"><AccountRoute :accounts="accounts" :source-id="t.source_account_code" :destination-id="t.destination_account_code" :source-name="t.source_account_name" :destination-name="t.destination_account_name" /></div>
        <div class="record-state">
          <span class="status-pill" :class="`status-${t.status}`">{{ statuses[t.status] || t.status }}</span>
          <NButton @click="detailDialog?.open(t)">{{ trusted && t.status === 'pending' ? '审批' : '查看详情' }}</NButton>
        </div>
      </div>
      <div class="record-meta"><span>{{ t.effective_date }}</span><span>{{ t.code }}</span><span v-if="t.description" class="record-note">{{ t.description }}</span><span v-for="tag in t.tags" :key="tag" class="tag">{{ tag }}</span></div>
      <div class="record-lower">
        <div class="record-amount"><span>转移金额</span><strong>¥ {{ money(t.amount_minor) }}</strong></div>
        <div class="record-actor"><span>发起人 {{ t.actor_name }}</span><span v-if="t.submitted_credential_id">由 {{ t.submitted_credential_name || t.submitted_credential_id }} 提交</span></div>
      </div>
    </article>
  </div>
  <TransferDetail ref="detailDialog" :accounts="accounts" :approvals="approvals" :trusted="trusted"
    @changed="emit('changed')" @notice="emit('notice', $event)" @error="detailError = $event" />
</template>

<style scoped>
.transfer-list { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); align-items:start; gap:10px; }
.transfer-record { border:1px solid #e3e8ec; border-radius:7px; padding:14px 16px; min-width:0; }
.record-main { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px 14px; }
.record-route { min-width:0; }
.record-route :deep(.account-route) { flex-wrap:nowrap; }
.record-route :deep(.account-label-name small) { display:inline; margin-left:6px; font-size:11px; color:#66707c; }
.record-state { display:flex; align-items:center; gap:12px; flex-shrink:0; }
.record-meta { display:flex; align-items:center; flex-wrap:wrap; gap:5px 12px; margin-top:10px; color:#66707c; font-size:12px; }
.record-note { color:#35404c; font-size:13px; overflow-wrap:anywhere; }
.record-meta .tag { margin:0; }
.record-lower { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:8px 16px; margin-top:10px; padding-top:10px; border-top:1px solid #edf0f2; }
.record-amount,.record-actor { display:flex; align-items:baseline; flex-wrap:wrap; gap:6px; color:#66707c; font-size:12px; }
.record-amount strong { color:#20242a; font-size:17px; font-variant-numeric:tabular-nums; }
.record-actor { justify-content:flex-end; }
@media(max-width:1100px) { .transfer-list { grid-template-columns:1fr; } }
@media(max-width:760px) { .record-main { align-items:flex-start; } .record-state { width:100%; justify-content:space-between; } .record-route :deep(.account-route) { flex-wrap:wrap; } }
</style>
