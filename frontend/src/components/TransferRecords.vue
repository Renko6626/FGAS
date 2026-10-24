<script setup lang="ts">
import { ref, watch } from "vue";
import { NButton } from "naive-ui";
import { money, statuses, type Transfer } from "../api/funds";
import { type Account } from "../api/accounts";
import AccountRoute from "./AccountRoute.vue";
import TransferDetail from "./TransferDetail.vue";
const props = defineProps<{
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
  <div v-else class="table-wrap">
    <table class="ledger-table">
      <thead>
        <tr>
          <th>业务日期</th>
          <th>来源 → 去向</th>
          <th class="numeric">金额（元）</th>
          <th>状态</th>
          <th>发起人</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="t in items" :key="t.id">
          <td class="ledger-date">{{ t.effective_date }}</td>
          <td class="ledger-route">
            <AccountRoute
              :accounts="accounts"
              :source-id="t.source_account_id"
              :destination-id="t.destination_account_id"
              :source-name="t.source_account_name"
              :destination-name="t.destination_account_name"
            /><small v-if="t.description">{{ t.description }}</small>
            <div v-if="t.tags.length">
              <span v-for="value in t.tags" :key="value" class="tag">{{
                value
              }}</span>
            </div>
          </td>
          <td class="numeric">{{ money(t.amount_minor) }}</td>
          <td>
            <span class="status-pill" :class="`status-${t.status}`">{{
              statuses[t.status] || t.status
            }}</span>
          </td>
          <td>{{ t.actor_name }}<small v-if="t.submitted_credential_id">由 {{ t.submitted_credential_name || t.submitted_credential_id }} 提交</small></td>
          <td>
            <NButton class="plain-button" text size="small" @click="detailDialog?.open(t)">{{
              approvals ? "审批" : "详情"
            }}</NButton>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
  <TransferDetail ref="detailDialog" :accounts="accounts" :approvals="approvals" :trusted="trusted"
    @changed="emit('changed')" @notice="emit('notice', $event)" @error="detailError = $event" />
</template>

<style scoped>
.ledger-date {
  white-space: nowrap;
}
.ledger-route {
  min-width: 200px;
  max-width: 360px;
  overflow-wrap: anywhere;
}
.ledger-route small {
  max-width: 360px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
