<script setup lang="ts">
import { computed, ref } from "vue";
import { NButton, NInput, NDrawer, NDrawerContent } from "naive-ui";
import { fundsApi, type Transfer } from "../api/funds";
import { money, statuses } from "../presentation/funds";
import { approvalLabel, actionNames } from "../presentation/audit";
import { type Account } from "../api/accounts";
const props = defineProps<{
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
const notice = ref("");
const processing = ref<"reject" | "reverse" | null>(null);
const taskTitle = computed(() => processing.value === "reject" ? "拒绝资金申请" : processing.value === "reverse" ? "冲销资金流水" : detail.value?.status === "pending" ? (props.trusted ? "审批资金申请" : "查看资金申请") : "资金流水详情");
const effect = computed(() => detail.value?.status === "pending" ? (props.trusted ? "批准后正式入账，更新相关账户余额。" : "这笔申请等待审批，尚未影响账户余额。") : detail.value?.status === "posted" ? "这笔流水已正式入账。需要更正时可提交冲销，保留原记录。" : detail.value?.status === "reversed" ? "原流水已冲销，历史记录保留。" : "这笔申请已拒绝，未产生资金分录。");
const audit = computed(() => detail.value?.audit || []);
const approvalAgent = computed(() =>
  audit.value.find(event => event.action === "posted" && event.agent_credential_id),
);
async function copyReference(link = false) {
  if (!detail.value) return;
  try {
    const code = detail.value.code;
    await navigator.clipboard.writeText(link ? `${window.location.origin}/#transfers?code=${encodeURIComponent(code)}` : code);
  } catch { error.value = "复制失败，请手动复制编号或链接"; }
}
async function open(item: Pick<Transfer, "code">) {
  error.value = "";
  notice.value = "";
  emit("error", "");
  reason.value = "";
  processing.value = null;
  try {
    detail.value = await fundsApi.detail(item.code);
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
    notice.value = approve ? "已批准并过账，账户余额已更新。" : "已拒绝申请，未产生资金分录。";
    emit("changed");
    emit("notice", approve ? "审批已过账" : "已拒绝");
  } catch (e) {
    error.value = (e as Error).message;
    detail.value = await fundsApi.detail(detail.value.code).catch(() => detail.value);
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
    const result = await fundsApi.reverse(detail.value.code, reason.value);
    emit("notice", "冲销流水" + (statuses[result.status] || result.status));
    detail.value = await fundsApi.detail(detail.value.code);
    processing.value = null;
    notice.value = `已提交冲销流水 ${result.code}（${statuses[result.status] || result.status}）。`;
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
  <NDrawer :show="!!detail" :width="620" style="max-width:100vw" :mask-closable="!busy" :close-on-esc="!busy" @update:show="show => { if (!show && !busy) detail = null; }">
    <NDrawerContent :key="detail?.code" :title="taskTitle" :closable="!busy" class="transfer-drawer" body-content-class="transfer-drawer-body">
      <template v-if="detail">
        <div class="drawer-record-heading">
          <span class="status-pill" :class="`status-${detail.status}`">{{ statuses[detail.status] || detail.status }}</span>
          <div class="drawer-record-tools"><span>{{ detail.code }}</span><NButton size="tiny" :disabled="busy" @click="copyReference()">复制编号</NButton><NButton size="tiny" :disabled="busy" @click="open(detail)">刷新</NButton></div>
        </div>
        <strong class="drawer-amount">¥ {{ money(detail.amount_minor) }}</strong>
        <h3 class="drawer-subject">{{ detail.description || (detail.reversal_of_code ? '资金冲销' : '未填写说明') }}</h3>
        <div class="drawer-route" aria-label="资金来源与去向">
          <div class="drawer-account"><span>{{ detail.source_account_name }}</span><small>{{ detail.source_account_code }}</small></div>
          <span class="drawer-route-arrow" aria-label="转向">→</span>
          <div class="drawer-account destination"><span>{{ detail.destination_account_name }}</span><small>{{ detail.destination_account_code }}</small></div>
        </div>
        <div class="drawer-brief"><span>业务日期 {{ detail.effective_date }}</span><span>发起人 {{ detail.actor_name }}</span></div>
        <p v-if="detail.submitted_credential_id" class="drawer-caption">由 {{ detail.submitted_credential_name || detail.submitted_credential_id }} 提交</p>
        <dl v-if="detail.counterparty || detail.tags.length || detail.reason" class="drawer-meta">
          <template v-if="detail.counterparty"><dt>往来方</dt><dd>{{ detail.counterparty }}</dd></template>
          <template v-if="detail.tags.length"><dt>标签</dt><dd>{{ detail.tags.join('，') }}</dd></template>
          <template v-if="detail.reason"><dt>处理原因</dt><dd>{{ detail.reason }}</dd></template>
        </dl>

        <details class="drawer-disclosure">
          <summary>记账分录（{{ detail.journal_lines?.length || 0 }}）</summary>
          <p v-if="!detail.journal_lines?.length" class="drawer-caption">尚未产生资金分录。</p>
          <div v-else class="drawer-table-wrap"><table class="drawer-table"><thead><tr><th>账户</th><th class="numeric">借方</th><th class="numeric">贷方</th></tr></thead><tbody><tr v-for="(line, index) in detail.journal_lines" :key="index"><td>{{ accounts.find(a => a.code === line.account_code)?.name || line.account_code }}</td><td class="numeric">{{ money(line.debit_minor) }}</td><td class="numeric">{{ money(line.credit_minor) }}</td></tr></tbody></table></div>
        </details>
        <details class="drawer-disclosure">
          <summary>审批与操作记录</summary>
          <dl class="drawer-meta">
            <dt>审批方式</dt><dd>{{ approvalLabel(detail.approval_mode) }}<template v-if="approvalAgent">（{{ approvalAgent.agent_credential_name || approvalAgent.agent_credential_id }}）</template><template v-if="detail.approved_by_name">，{{ detail.approved_by_name }}</template></dd>
            <dt>版本</dt><dd>{{ detail.version }}</dd>
            <template v-if="detail.reversal_of_code"><dt>冲销原单</dt><dd>{{ detail.reversal_of_code }}</dd></template>
          </dl>
          <ol class="drawer-audit"><li v-for="(event, index) in audit" :key="index"><strong>{{ actionNames[event.action] || event.action }}</strong><span>{{ event.actor_id }}<template v-if="event.agent_credential_id">，通过 {{ event.agent_credential_name || event.agent_credential_id }}</template></span><small>{{ new Date(event.created_at).toLocaleString('zh-CN') }}</small><p v-if="event.detail">{{ ['automatic', 'manual', 'agent_direct', 'agent_approval'].includes(event.detail) ? approvalLabel(event.detail) : event.detail }}</p></li></ol>
          <NButton size="small" :disabled="busy" @click="copyReference(true)">复制定位链接</NButton>
        </details>
        <details v-if="detail.status === 'posted'" class="drawer-disclosure">
          <summary>更正这笔流水</summary>
          <p class="drawer-caption">冲销会新建关联原单的反向资金流水，原记录保留。</p>
          <NButton size="small" :disabled="busy" @click="processing = 'reverse'; reason = ''; error = ''; notice = ''">提交冲销</NButton>
        </details>
      </template>
      <template #footer>
        <div v-if="detail" class="drawer-footer">
          <p v-if="error" class="drawer-feedback error" role="alert">{{ error }}</p>
          <p v-if="notice" class="drawer-feedback success" role="status">{{ notice }}</p>
          <template v-if="processing">
            <label class="drawer-reason">{{ processing === 'reject' ? '拒绝原因' : '冲销原因' }}<NInput v-model:value="reason" :disabled="busy" type="textarea" :autosize="{ minRows: 2, maxRows: 3 }" :placeholder="processing === 'reject' ? '填写拒绝这笔申请的原因' : '填写需要冲销的原因'" /></label>
            <div class="drawer-actions"><NButton :disabled="busy" @click="processing = null; reason = ''; error = ''">返回</NButton><NButton type="primary" :loading="busy" :disabled="busy || !reason.trim()" @click="processing === 'reject' ? decide(false) : reverse()">{{ processing === 'reject' ? '确认拒绝' : '提交冲销' }}</NButton></div>
          </template>
          <template v-else>
            <p class="drawer-effect">{{ effect }}</p>
            <div class="drawer-actions"><NButton class="drawer-close" :disabled="busy" @click="detail = null">关闭</NButton><template v-if="detail.status === 'pending' && trusted"><NButton :disabled="busy" @click="processing = 'reject'; reason = ''; error = ''; notice = ''">拒绝申请</NButton><NButton type="primary" :loading="busy" :disabled="busy" @click="decide(true)">批准并过账</NButton></template></div>
          </template>
        </div>
      </template>
    </NDrawerContent>
  </NDrawer>
</template>

<style scoped src="../styles/transfer-drawer.css"></style>
