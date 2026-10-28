<script setup lang="ts">
import { ref, shallowRef, computed, onMounted } from "vue";
import { NButton, NInput, NDrawer, NDrawerContent, NSelect } from "naive-ui";
import { money, statuses as fundStatuses } from "../presentation/funds";
import { approvalLabel, actionNames } from "../presentation/audit";
import type { StockAccount, Account } from "../api/accounts";
import type { Sku } from "../api/warehouse";
import { warehouse, type StockTransfer } from "../api/warehouse";
import { stockStatuses, today } from "../presentation/warehouse";
import { useFundTransferOptions } from "../composables/useFundTransferOptions";
import AccountRoute from "./AccountRoute.vue";
import AccountLabel from "./AccountLabel.vue";
import AccountAvatar from "./AccountAvatar.vue";
import StockTransferEditor from "./StockTransferEditor.vue";
const props = defineProps<{ locations: StockAccount[]; trusted: boolean; skus: Sku[]; accounts: Account[] }>();
const emit = defineEmits<{ changed: []; error: [string] }>();
const editor = ref<InstanceType<typeof StockTransferEditor> | null>(null);
const fund = ref("");
const { options: fundOptions, loading: fundLoading, search: searchFunds } = useFundTransferOptions(() => fund.value ? [fund.value] : [], true);
onMounted(() => searchFunds(""));
const detailShow = ref(false), detail = shallowRef<StockTransfer | null>(null), busy = ref(false), error = ref(""), notice = ref("");
type Processing = "reject" | "cancel" | "return_report";
const processing = ref<Processing | null>(null), reason = ref(""), completionDate = ref(today());
const processingTitles = { reject: "拒绝货物转移", cancel: "取消货物转移", return_report: "退回完成报告" };
const pendingReport = computed(() => detail.value?.confirmations.find(report => report.status === "pending"));
const canComplete = computed(() => detail.value?.status === "in_transit" && !pendingReport.value);
const taskTitle = computed(() => {
  if (processing.value) return processingTitles[processing.value];
  if (detail.value?.status === "pending") return props.trusted ? "审批货物转移" : "查看转移申请";
  if (detail.value?.status === "in_transit") {
    if (pendingReport.value) return props.trusted ? "核实完成报告" : "查看完成报告";
    return props.trusted ? "确认货物完成" : "报告货物完成";
  }
  return "货物转移详情";
});
const effect = computed(() => {
  if (processing.value === "reject") return "拒绝后不再办理这笔申请，库存不变。";
  if (processing.value === "cancel") return "取消后不再办理这笔转移，库存不变。";
  if (processing.value === "return_report") return "退回后主单仍待完成，库存不变，可重新报告完成。";
  if (detail.value?.status === "pending") return props.trusted ? "批准后进入待完成，库存暂不变化。" : "这笔转移等待审批，尚未改变库存。";
  if (detail.value?.status === "in_transit") {
    if (pendingReport.value) return props.trusted ? "核实整笔转移已完成后，确认并更新库存。" : "完成报告等待核实，主单仍待完成，库存不变。";
    return props.trusted ? "确认后按上述全部货物数量更新库存。" : "提交完成报告后等待核实，库存暂不变化。";
  }
  return detail.value?.status === "completed" ? "整笔转移已完成，库存已更新。" : "这笔转移已结束。";
});
const approvalAgent = computed(() => detail.value?.audit.find(event => ["approve", "automatic_approval"].includes(event.action) && event.agent_credential_id));
function completionAudit(code: string) { return detail.value?.audit.find(event => event.action === "completed" && event.detail.confirmation_code === code); }
async function copyReference(link = false) {
  if (!detail.value) return;
  try { const code = detail.value.code; await navigator.clipboard.writeText(link ? `${window.location.origin}/#stock?code=${encodeURIComponent(code)}` : code); }
  catch { error.value = "复制失败，请手动复制编号或链接"; }
}
async function open(code: string) {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  notice.value = "";
  emit("error", "");
  try {
    detail.value = await warehouse.detail(code);
    detailShow.value = true;
    reason.value = "";
    processing.value = null;
    completionDate.value = today();
    fund.value = "";
  } catch (e) { error.value = (e as Error).message; emit("error", error.value); }
  finally { busy.value = false; }
}
async function changed() { emit("changed"); if (detail.value) await open(detail.value.code); }
async function run(path: string, body: unknown, message: string) {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  notice.value = "";
  try {
    detail.value = await warehouse.action(path, body);
    processing.value = null;
    reason.value = "";
    notice.value = message;
    emit("changed");
  } catch (e) { error.value = (e as Error).message + "。请刷新查看当前记录后再操作。"; }
  finally { busy.value = false; }
}
function prepareProcessing(action: Processing) { processing.value = action; reason.value = ""; error.value = ""; notice.value = ""; }
function submitProcessing() {
  if (!detail.value || !processing.value || busy.value) return;
  if (!reason.value.trim()) { error.value = "请填写原因"; return; }
  if (processing.value === "return_report") {
    if (pendingReport.value) void run(`/stock-confirmations/${pendingReport.value.code}/reject`, { reason: reason.value }, "已退回完成报告，转移仍待完成，库存不变。");
  } else void run(`/stock-transfers/${detail.value.code}/${processing.value}`, { reason: reason.value }, processing.value === "reject" ? "已拒绝货物转移，库存不变。" : "已取消货物转移，库存不变。");
}
function submitCompletion() {
  if (!detail.value || !canComplete.value || busy.value) return;
  if (!completionDate.value) { error.value = "请选择完成日期"; return; }
  void run(`/stock-transfers/${detail.value.code}/completion`, { effective_date: completionDate.value }, props.trusted ? "已确认整笔完成，库存已更新。" : "完成报告已提交，等待核实，库存未变化。");
}
defineExpose({ open, busy });
</script>

<template>
  <NDrawer v-model:show="detailShow" :width="660" style="max-width:100vw" :mask-closable="!busy" :close-on-esc="!busy">
    <NDrawerContent :key="detail?.code" :title="taskTitle" :closable="!busy" class="transfer-drawer" body-content-class="transfer-drawer-body">
      <template v-if="detail">
        <div class="drawer-record-heading">
          <span class="status-pill" :class="`status-${detail.status}`">{{ stockStatuses[detail.status] || detail.status }}</span>
          <div class="drawer-record-tools"><span>{{ detail.code }}</span><NButton size="tiny" :disabled="busy" @click="copyReference()">复制编号</NButton><NButton size="tiny" :disabled="busy" @click="open(detail.code)">刷新</NButton></div>
        </div>
        <h3 class="drawer-subject">{{ detail.description || '未填写说明' }}</h3>
        <div class="drawer-route" aria-label="货物来源与去向">
          <div class="drawer-account"><span>{{ detail.source_account_name }}</span><small>{{ detail.source_account_code }}</small></div>
          <span class="drawer-route-arrow" aria-label="转向">→</span>
          <div class="drawer-account destination"><span>{{ detail.destination_account_name }}</span><small>{{ detail.destination_account_code }}</small></div>
        </div>
        <div class="drawer-brief"><span>业务日期 {{ detail.effective_date }}</span><span>发起人 {{ detail.actor_id }}</span></div>
        <p v-if="detail.submitted_credential_id" class="drawer-caption">由 {{ detail.submitted_credential_name || detail.submitted_credential_id }} 提交</p>

        <section class="drawer-goods" aria-label="整笔货物与数量">
          <div class="drawer-table-wrap"><table class="drawer-table drawer-goods-table"><colgroup><col /><col style="width:84px" /></colgroup><thead><tr><th>整笔货物</th><th class="numeric">数量</th></tr></thead><tbody>
            <tr v-for="line in detail.lines" :key="line.sku_code">
              <td><div class="drawer-sku"><AccountAvatar :name="line.sku_name" :url="skus.find(s => s.code === line.sku_code)?.avatar_url" /><div><strong>{{ line.sku_name }}</strong><small>{{ line.sku_code }}</small></div></div>
                <div v-if="detail.status === 'in_transit'" class="drawer-stock-impact"><span>确认完成后：</span><span v-if="detail.source_kind !== 'external'">{{ detail.source_account_name }} −{{ line.quantity }} {{ line.unit }}</span><span v-if="detail.destination_kind !== 'external'">{{ detail.destination_account_name }} +{{ line.quantity }} {{ line.unit }}</span></div>
              </td><td class="numeric drawer-quantity"><strong>{{ line.quantity }}</strong> {{ line.unit }}</td>
            </tr>
          </tbody></table></div>
        </section>
        <div v-if="pendingReport" class="drawer-callout">
          <strong>有人报告整笔完成，等待核实</strong>
          <div class="drawer-brief"><span>完成日期 {{ pendingReport.effective_date }}</span><span>报告人 {{ pendingReport.actor_id }}</span></div>
          <p class="drawer-caption">完成报告 {{ pendingReport.code }}<template v-if="pendingReport.submitted_credential_id">，由 {{ pendingReport.submitted_credential_name || pendingReport.submitted_credential_id }} 提交</template></p>
        </div>
        <label v-else-if="canComplete" class="drawer-completion-date">完成日期<input v-model="completionDate" type="date" :disabled="busy" /></label>

        <details class="drawer-disclosure">
          <summary>关联资金（{{ detail.fund_references.length }}）</summary>
          <p class="drawer-caption">资金与货物独立生效，关联记录不代表已付款。</p>
          <div v-for="item in detail.fund_references" :key="item.code" class="drawer-related"><div class="drawer-related-heading"><strong>{{ item.description || item.code }}</strong><span class="status-pill" :class="`status-${item.status}`">{{ fundStatuses[item.status] || item.status }}</span><strong>¥ {{ money(item.amount_minor) }}</strong></div><AccountRoute v-if="item.source_account_code" :accounts="accounts" :source-id="item.source_account_code" :destination-id="item.destination_account_code" /></div>
          <p v-if="!detail.fund_references.length" class="drawer-caption">未关联资金记录。</p>
          <details v-if="trusted" class="drawer-secondary"><summary>补充已有资金关联</summary><label>资金记录<NSelect v-model:value="fund" :disabled="busy" filterable remote clearable :loading="fundLoading" :options="fundOptions" @search="searchFunds" /></label><NButton size="small" :disabled="busy || !fund" @click="run(`/stock-transfers/${detail.code}/fund-references`, { fund_transfer_code: fund }, '已关联资金记录。')">关联资金记录</NButton></details>
        </details>
        <details class="drawer-disclosure">
          <summary>相关货物单（{{ detail.related_transfers.length + (detail.related_transfer_code ? 1 : 0) }}）</summary>
          <p class="drawer-caption">用于记录退回、补发或更正，各笔货物单单独办理。退回时请交换来源与去向。</p>
          <NButton size="small" :disabled="busy" @click="editor?.open({ related_transfer_code: detail.code, source_account_code: detail.source_account_code, destination_account_code: detail.destination_account_code })">新建并关联</NButton>
          <NButton v-if="detail.related_transfer_code" size="small" :disabled="busy" @click="open(detail.related_transfer_code)">查看原货物单 {{ detail.related_transfer_code }}</NButton>
          <div v-for="item in detail.related_transfers" :key="item.code" class="drawer-related"><div class="drawer-related-heading"><AccountRoute :accounts="locations" :source-id="item.source_account_code" :destination-id="item.destination_account_code" /><span class="status-pill" :class="`status-${item.status}`">{{ stockStatuses[item.status] || item.status }}</span><NButton size="small" :disabled="busy" @click="open(item.code)">查看详情</NButton></div><div v-for="line in item.lines" :key="line.sku_code"><AccountLabel :name="`${line.sku_code} ${skus.find(s => s.code === line.sku_code)?.name || ''}`.trim()" :url="skus.find(s => s.code === line.sku_code)?.avatar_url" /><strong>{{ line.quantity }} {{ skus.find(s => s.code === line.sku_code)?.unit }}</strong></div></div>
          <p v-if="!detail.related_transfer_code && !detail.related_transfers.length" class="drawer-caption">暂无相关货物单。</p>
        </details>
        <details class="drawer-disclosure">
          <summary>审批与操作记录</summary>
          <dl class="drawer-meta"><dt>审批方式</dt><dd>{{ approvalLabel(detail.approval_mode) }}<template v-if="approvalAgent">（{{ approvalAgent.agent_credential_name || approvalAgent.agent_credential_id }}）</template><template v-if="detail.approved_by">，{{ detail.approved_by }}</template></dd><template v-if="detail.tags.length"><dt>标签</dt><dd>{{ detail.tags.join('，') }}</dd></template></dl>
          <div v-for="report in detail.confirmations.filter(c => c.status !== 'pending')" :key="report.code" class="drawer-related"><div class="drawer-related-heading"><strong>完成记录 {{ report.code }}</strong><span class="status-pill" :class="`status-${report.status}`">{{ stockStatuses[report.status] || fundStatuses[report.status] || report.status }}</span></div><p class="drawer-caption">报告人 {{ report.actor_id }}<template v-if="report.submitted_credential_id">，通过 {{ report.submitted_credential_name || report.submitted_credential_id }}</template>；完成日期 {{ report.effective_date }}</p><p v-if="report.approved_by" class="drawer-caption">{{ approvalLabel(completionAudit(report.code)?.detail.mode) }}<template v-if="completionAudit(report.code)?.agent_credential_id">（{{ completionAudit(report.code)?.agent_credential_name || completionAudit(report.code)?.agent_credential_id }}）</template>，审批人 {{ report.approved_by }}</p></div>
          <ol class="drawer-audit"><li v-for="event in detail.audit" :key="event.created_at + event.action"><strong>{{ actionNames[event.action] || event.action }}</strong><span>{{ event.actor_id }}<template v-if="event.agent_credential_id">，通过 {{ event.agent_credential_name || event.agent_credential_id }}</template></span><small>{{ new Date(event.created_at).toLocaleString('zh-CN') }}</small><p v-if="event.detail.reason">{{ event.detail.reason }}</p></li></ol>
          <NButton size="small" :disabled="busy" @click="copyReference(true)">复制定位链接</NButton>
        </details>
        <details v-if="trusted && ['pending', 'in_transit'].includes(detail.status)" class="drawer-disclosure"><summary>其他操作</summary><NButton size="small" :disabled="busy" @click="prepareProcessing('cancel')">取消货物转移</NButton></details>
      </template>
      <template #footer>
        <div v-if="detail" class="drawer-footer">
          <p v-if="error" class="drawer-feedback error" role="alert">{{ error }}</p>
          <p v-if="notice" class="drawer-feedback success" role="status">{{ notice }}</p>
          <p class="drawer-effect">{{ effect }}</p>
          <template v-if="processing">
            <label class="drawer-reason">{{ processingTitles[processing] }}的原因<NInput v-model:value="reason" :disabled="busy" type="textarea" :autosize="{ minRows: 2, maxRows: 3 }" placeholder="填写原因" /></label>
            <div class="drawer-actions"><NButton :disabled="busy" @click="processing = null; reason = ''; error = ''">返回</NButton><NButton type="primary" :loading="busy" :disabled="busy || !reason.trim()" @click="submitProcessing">{{ processingTitles[processing] }}</NButton></div>
          </template>
          <div v-else class="drawer-actions">
            <NButton class="drawer-close" :disabled="busy" @click="detailShow = false">关闭</NButton>
            <template v-if="trusted && detail.status === 'pending'"><NButton :disabled="busy" @click="prepareProcessing('reject')">拒绝申请</NButton><NButton type="primary" :loading="busy" :disabled="busy" @click="run(`/stock-transfers/${detail.code}/approve`, {}, '已批准转移，进入待完成，库存未变化。')">批准转移</NButton></template>
            <template v-else-if="trusted && pendingReport"><NButton :disabled="busy" @click="prepareProcessing('return_report')">退回报告</NButton><NButton type="primary" :loading="busy" :disabled="busy" @click="run(`/stock-confirmations/${pendingReport.code}/approve`, {}, '已核实并确认整笔完成，库存已更新。')">核实并确认完成</NButton></template>
            <NButton v-else-if="canComplete" type="primary" :loading="busy" :disabled="busy || !completionDate" @click="submitCompletion">{{ trusted ? '确认完成' : '提交完成报告' }}</NButton>
          </div>
        </div>
      </template>
    </NDrawerContent>
  </NDrawer>
  <StockTransferEditor ref="editor" hide-trigger :locations="locations" :skus="skus" :accounts="accounts" :trusted="trusted" @saved="changed" />
</template>

<style scoped src="../styles/transfer-drawer.css"></style>
