<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { NButton } from "naive-ui";
import type { Transfer } from "../api/funds";
import { money, statuses } from "../presentation/funds";
import type { Account } from "../api/accounts";
import TransferDetail from "./TransferDetail.vue";
const props = defineProps<{
  targetCode?: string; items: Transfer[]; accounts: Account[]; approvals: boolean; trusted: boolean;
  loading?: boolean; hasFilters: boolean; hideCreate?: boolean; error?: string;
}>();
const emit = defineEmits<{ changed: []; notice: [string]; create: []; reset: [] }>();
const detailDialog = ref<InstanceType<typeof TransferDetail> | null>(null);
const detailError = ref("");
const selectedCode = ref("");
function open(item: Pick<Transfer, "code">) { selectedCode.value = item.code; void detailDialog.value?.open(item); }
onMounted(() => { if (props.targetCode) open({ code: props.targetCode }); });
watch(() => props.targetCode, code => { if (code) open({ code }); }, { flush: "post" });
watch(() => props.items, () => { detailError.value = ""; });
</script>

<template>
  <p v-if="error || detailError" class="error" role="alert">{{ error || detailError }}</p>
  <div v-if="!items.length" class="empty-state">
    <p>{{ loading ? '正在读取流水' : hasFilters ? '没有符合条件的流水' : approvals ? '暂无待审批的资金申请' : '暂无资金流水' }}</p>
    <NButton v-if="hasFilters" @click="emit('reset')">清空筛选</NButton><NButton v-else-if="!approvals && !hideCreate" @click="emit('create')">登记资金</NButton>
  </div>
  <div v-else class="ledger-records funds-records" :aria-busy="loading">
    <table class="ledger-table">
      <colgroup><col class="subject-column" /><col class="route-column" /><col class="value-column" /><col class="state-column" /></colgroup>
      <thead><tr><th>事项 / 业务日期</th><th>来源 → 去向</th><th>金额</th><th>状态 / 下一步</th></tr></thead>
      <tbody>
        <tr v-for="item in items" :key="item.code" class="ledger-record" :class="[`record-state-${item.status}`, { selected: selectedCode === item.code }]" @click="open(item)">
          <td class="record-subject">
            <button class="record-open" aria-haspopup="dialog" :aria-label="`${trusted && item.status === 'pending' ? '查看并审批' : '查看'}资金流水 ${item.code}：${item.description || (item.reversal_of_code ? '资金冲销' : '未填写说明')}`" @click.stop="open(item)">{{ item.description || (item.reversal_of_code ? '资金冲销' : '未填写说明') }}</button>
            <div class="record-secondary"><time>{{ item.effective_date }}</time><span>{{ item.code }}</span><span v-if="item.reversal_of_code" class="reversal-reference">冲销 {{ item.reversal_of_code }}</span><span v-for="tag in item.tags.slice(0, 2)" :key="tag" class="record-tag">{{ tag }}</span></div>
          </td>
          <td class="record-route">
            <div class="route-flow">
              <span class="route-account route-source" :title="item.source_account_name">{{ item.source_account_name }}</span>
              <span class="route-arrow">→</span>
              <span class="route-account route-destination" :title="item.destination_account_name">{{ item.destination_account_name }}</span>
            </div>
          </td>
          <td class="record-value money-cell"><strong><small>¥</small> {{ money(item.amount_minor) }}</strong></td>
          <td class="record-action"><div class="record-state-entry"><span :class="['ledger-state', `state-${item.status}`]">{{ statuses[item.status] || item.status }}</span><span class="record-chevron" aria-hidden="true">›</span></div></td>
        </tr>
      </tbody>
    </table>
  </div>
  <TransferDetail ref="detailDialog" :accounts="accounts" :approvals="approvals" :trusted="trusted" @changed="emit('changed')" @notice="emit('notice', $event)" @error="detailError = $event" />
</template>

<style scoped src="../styles/ledger-records.css"></style>
