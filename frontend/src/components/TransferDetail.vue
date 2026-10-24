<script setup lang="ts">
import { computed, ref } from "vue";
import { NButton, NInput, NModal } from "naive-ui";
import { fundsApi, type Transfer } from "../api/funds";
import { money, statuses } from "../presentation/funds";
import { approvalLabel, actionNames } from "../presentation/audit";
import { type Account } from "../api/accounts";
import AccountRoute from "./AccountRoute.vue";
defineProps<{
  accounts: Account[];
  approvals: boolean;
  trusted: boolean;
}>();
const emit = defineEmits<{
  changed: [];
  notice: [string];
  error: [string];
}>();
const detail = ref<Transfer | null>(null), error = ref(""), reason = ref(""), busy = ref(false);
const processing = ref<"reject" | "reverse" | null>(null);
const audit = computed(() => detail.value?.audit || []);
const approvalAgent = computed(() =>
  audit.value.find(event => event.action === "posted" && event.agent_credential_id),
);
async function open(item: Transfer) {
  error.value = "";
  emit("error", "");
  reason.value = "";
  processing.value = null;
  try {
    detail.value = await fundsApi.detail(item.id);
  } catch (e) {
    error.value = (e as Error).message;
    emit("error", error.value);
  }
}
async function decide(approve: boolean) {
  if (!detail.value || busy.value)
    return;
  if (!approve && !reason.value.trim()) {
    error.value = "请填写拒绝原因";
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    detail.value = await fundsApi.decide(detail.value, approve, reason.value);
    processing.value = null;
    emit("changed");
    emit("notice", approve ? "审批已过账" : "已拒绝");
  } catch (e) {
    error.value = (e as Error).message;
    detail.value = await fundsApi.detail(detail.value.id).catch(() => detail.value);
  } finally {
    busy.value = false;
  }
}
async function reverse() {
  if (busy.value)
    return;
  if (!detail.value || !reason.value.trim()) {
    error.value = "请填写冲销原因";
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    const result = await fundsApi.reverse(detail.value.id, reason.value);
    emit("notice", "冲销流水" + (statuses[result.status] || result.status));
    detail.value = await fundsApi.detail(detail.value.id);
    processing.value = null;
    emit("changed");
  } catch (e) {
    error.value =
      (e as Error).message + "。请查看流水记录后再决定是否重新提交。";
  } finally {
    busy.value = false;
  }
}
defineExpose({ open });
</script>

<template>
  <NModal
    :show="!!detail"
    preset="card"
    :title="approvals ? '资金审批' : '资金流水'"
    class="dialog ledger-dialog"
    :closable="!busy"
    :mask-closable="!busy"
    :close-on-esc="!busy"
    @close="detail = null"
  >
    <template v-if="detail">
      <div class="ledger-detail-heading">
        <strong>¥ {{ money(detail.amount_minor) }}</strong
        ><span class="status-pill" :class="`status-${detail.status}`">{{
          statuses[detail.status] || detail.status
        }}</span>
      </div>
      <div class="ledger-detail-route">
        <AccountRoute
          :accounts="accounts"
          :source-id="detail.source_account_id"
          :destination-id="detail.destination_account_id"
          :source-name="detail.source_account_name"
          :destination-name="detail.destination_account_name"
        />
      </div>
      <dl>
        <dt>业务日期</dt>
        <dd>{{ detail.effective_date }}</dd>
        <dt v-if="detail.description">说明</dt>
        <dd v-if="detail.description">{{ detail.description }}</dd>
        <dt v-if="detail.counterparty">往来方</dt>
        <dd v-if="detail.counterparty">{{ detail.counterparty }}</dd>
        <dt v-if="detail.tags.length">标签</dt>
        <dd v-if="detail.tags.length">{{ detail.tags.join("，") }}</dd>
        <dt>发起人</dt>
        <dd>{{ detail.actor_name }}<p v-if="detail.submitted_credential_id">由 {{ detail.submitted_credential_name || detail.submitted_credential_id }} 提交</p></dd>
        <dt>审批</dt>
        <dd>
          {{ approvalLabel(detail.approval_mode) }}<template v-if="approvalAgent">（{{ approvalAgent.agent_credential_name || approvalAgent.agent_credential_id }}）</template><template v-if="detail.approved_by_name"
            >（{{ detail.approved_by_name }}）</template
          >
        </dd>
        <dt v-if="detail.reason">处理原因</dt>
        <dd v-if="detail.reason">{{ detail.reason }}</dd>
      </dl>
      <details class="disclosure">
        <summary>记账分录</summary>
        <p v-if="!detail.journal_lines?.length" class="muted">尚未产生分录。</p>
        <div v-else class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>账户</th>
                <th class="numeric">借方</th>
                <th class="numeric">贷方</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(line, index) in detail.journal_lines" :key="index">
                <td>
                  {{
                    accounts.find((a) => a.id === line.account_id)?.name ||
                    line.account_id
                  }}
                </td>
                <td class="numeric">{{ money(line.debit_minor) }}</td>
                <td class="numeric">{{ money(line.credit_minor) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </details>
      <details class="disclosure">
        <summary>操作记录与编号</summary>
        <ol class="audit-list">
          <li v-for="(event, index) in audit" :key="index">
            <strong>{{ actionNames[event.action] || event.action }}</strong
            ><span>{{ event.actor_id }}<template v-if="event.agent_credential_id">，通过连接 {{ event.agent_credential_name || event.agent_credential_id }}</template></span
            ><small>{{
              new Date(event.created_at).toLocaleString("zh-CN")
            }}</small>
            <p v-if="event.detail">
              {{
                ["automatic", "manual", "agent_direct", "agent_approval"].includes(event.detail)
                  ? approvalLabel(event.detail)
                  : event.detail
              }}
            </p>
          </li>
        </ol>
        <dl class="internal-id">
          <dt>流水编号</dt>
          <dd>{{ detail.id }}</dd>
          <dt>版本</dt>
          <dd>{{ detail.version }}</dd>
          <dt v-if="detail.reversal_of">冲销原流水</dt>
          <dd v-if="detail.reversal_of">{{ detail.reversal_of }}</dd>
        </dl>
      </details>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <div v-if="processing" class="processing-panel">
        <label
          >{{ processing === "reject" ? "拒绝原因" : "冲销原因"
          }}<NInput
            v-model:value="reason"
            :disabled="busy"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 4 }"
        /></label>
        <div class="actions">
          <NButton
            :disabled="busy"
            @click="
              processing = null;
              reason = '';
            "
            >取消</NButton
          ><NButton
            type="primary"
            :loading="busy"
            :disabled="!reason.trim()"
            @click="processing === 'reject' ? decide(false) : reverse()"
            >{{ processing === "reject" ? "确认拒绝" : "申请冲销" }}</NButton
          >
        </div>
      </div>
      <div v-else class="actions">
        <template v-if="detail.status === 'pending' && trusted"
          ><NButton
            :disabled="busy"
            @click="
              processing = 'reject';
              reason = '';
            "
            >拒绝</NButton
          ><NButton type="primary" :loading="busy" @click="decide(true)"
            >批准并过账</NButton
          ></template
        ><NButton
          v-if="detail.status === 'posted'"
          @click="
            processing = 'reverse';
            reason = '';
          "
          >申请冲销</NButton
        >
      </div>
    </template>
  </NModal>
</template>

<style scoped>
.ledger-detail-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}
.ledger-detail-heading > strong {
  font-size: 36px;
  font-weight: normal;
  font-variant-numeric: tabular-nums;
  font-family: "YanSong", SimSun, serif;
}
.ledger-detail-route {
  font-size: 18px;
  margin: 12px 0 24px;
  overflow-wrap: anywhere;
}
.audit-list {
  list-style: none;
  padding: 0;
  margin: 16px 0 0;
}
.audit-list li {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: baseline;
  border-bottom: 1px solid #ddd;
  padding: 12px 0;
  font-size: 13px;
}
.audit-list strong {
  font-weight: normal;
}
.audit-list small {
  margin-left: auto;
}
.audit-list p {
  width: 100%;
  margin: 0;
  color: #666;
  overflow-wrap: anywhere;
}
.processing-panel {
  margin-top: 24px;
  border-top: 1px solid #ccc;
  padding-top: 8px;
}
@media (max-width: 700px) {
  .ledger-detail-heading > strong {
    font-size: 30px;
  }
}
</style>
