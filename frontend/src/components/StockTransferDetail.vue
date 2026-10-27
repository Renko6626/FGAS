<script setup lang="ts">
import { ref, shallowRef, computed, onMounted } from "vue";
import { NButton, NInput, NModal, NSelect } from "naive-ui";
import { money, statuses as fundStatuses } from "../presentation/funds";
import { approvalLabel, actionNames } from "../presentation/audit";
import { type StockAccount, type Account } from "../api/accounts";
import { type Sku } from "../api/warehouse";
import { warehouse, type StockTransfer } from "../api/warehouse";
import { stockStatuses } from "../presentation/warehouse";
import { useFundTransferOptions } from "../composables/useFundTransferOptions";
import AccountRoute from "./AccountRoute.vue";
import AccountLabel from "./AccountLabel.vue";
import StockCompletionEditor from "./StockCompletionEditor.vue";
import StockTransferEditor from "./StockTransferEditor.vue";
defineProps<{
  locations: StockAccount[];
  trusted: boolean;
  skus: Sku[];
  accounts: Account[];
}>();
const emit = defineEmits<{
  changed: [];
  error: [string];
}>();
const editor = ref<InstanceType<typeof StockTransferEditor> | null>(null);
const fund = ref("");
const {
  options: fundOptions,
  loading: fundLoading,
  search: searchFunds,
} = useFundTransferOptions(() => fund.value ? [fund.value] : [], true);
onMounted(() => searchFunds(""));
const detailShow = ref(false), detail = shallowRef<StockTransfer | null>(null), busy = ref(false), error = ref(""), reason = ref("");
const approvalAgent = computed(() =>
  detail.value?.audit.find(event =>
    ["approve", "automatic_approval"].includes(event.action) && event.agent_credential_id,
  ),
);
function completionAudit(confirmationId: string) {
  return detail.value?.audit.find(event =>
    event.action === 'completed' && event.detail.confirmation_code === confirmationId,
  );
}
async function copyReference(link = false) {
  if (!detail.value) return;
  try {
    const code = detail.value.code;
    await navigator.clipboard.writeText(link ? `${window.location.origin}/#stock?code=${encodeURIComponent(code)}` : code);
  } catch { error.value = "复制失败，请手动复制编号或链接"; }
}
async function open(id: string) {
  if (busy.value)
    return;
  busy.value = true;
  error.value = "";
  emit("error", "");
  try {
    detail.value = await warehouse.detail(id);
    detailShow.value = true;
    reason.value = "";
    fund.value = "";
  } catch (e) {
    error.value = (e as Error).message;
    emit("error", error.value);
  } finally {
    busy.value = false;
  }
}
async function changed() {
  emit("changed");
  if (detail.value)
    await open(detail.value.code);
}
async function run(path: string, body: unknown) {
  if (busy.value)
    return;
  busy.value = true;
  error.value = "";
  try {
    detail.value = await warehouse.action(path, body);
    emit("changed");
  } catch (e) {
    error.value = (e as Error).message + "。请刷新查看当前记录后再操作。";
  } finally {
    busy.value = false;
  }
}
function decide(item: StockTransfer, action: string, confirmationId?: string) {
  const path = confirmationId
    ? `/stock-confirmations/${confirmationId}/${action}`
    : `/stock-transfers/${item.code}/${action}`;
  run(path, ["reject", "cancel"].includes(action) ? { reason: reason.value } : {});
}
defineExpose({ open, busy });
</script>

<template>
  <NModal
    v-model:show="detailShow"
    preset="card"
    title="货物转移详情"
    class="dialog"
    :mask-closable="!busy"
    :closable="!busy"
    :close-on-esc="!busy"
  >
    <template v-if="detail">
      <div class="stock-detail-heading">
        <AccountRoute
          :accounts="locations"
          :source-id="detail.source_account_code"
          :destination-id="detail.destination_account_code"
          :source-name="detail.source_account_name"
          :destination-name="detail.destination_account_name"
        /><span class="status-pill" :class="`status-${detail.status}`">{{
          stockStatuses[detail.status] || detail.status
        }}</span>
      </div>
      <section class="stock-section">
        <h3>业务明细</h3>
        <dl class="stock-meta">
          <dt>日期</dt>
          <dd>{{ detail.effective_date }}</dd>
          <dt>说明</dt>
          <dd>{{ detail.description || "未填写" }}</dd>
          <template v-if="detail.tags.length"
            ><dt>标签</dt>
            <dd>{{ detail.tags.join("，") }}</dd></template
          >
          <dt>发起人</dt><dd>{{ detail.actor_id }}<p v-if="detail.submitted_credential_id">由 {{ detail.submitted_credential_name || detail.submitted_credential_id }} 提交</p></dd>
          <dt>审批</dt><dd>{{ approvalLabel(detail.approval_mode) }}<template v-if="approvalAgent">（{{ approvalAgent.agent_credential_name || approvalAgent.agent_credential_id }}）</template><template v-if="detail.approved_by">，审批人 {{ detail.approved_by }}</template></dd>
          <dt>转移编号</dt>
          <dd>{{ detail.code }} <NButton @click="copyReference()">复制编号</NButton> <NButton @click="copyReference(true)">复制定位链接</NButton></dd>
        </dl>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>货物</th>
                <th>数量</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="l in detail.lines" :key="l.sku_code">
                <td>
                  <AccountLabel
                    :name="`${l.sku_code} ${l.sku_name}`"
                    :url="skus.find((s) => s.code === l.sku_code)?.avatar_url"
                  />
                </td>
                <td>
                  <strong>{{ l.quantity }} {{ l.unit }}</strong>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
      <section class="stock-section">
        <div class="toolbar">
          <h3>当前操作</h3>
          <NButton :loading="busy" :disabled="busy" @click="open(detail.code)"
            >刷新详情</NButton
          >
        </div>
        <p v-if="error" class="error">{{ error }}</p>
        <div class="actions">
          <NButton
            v-if="trusted && detail.status === 'pending'"
            type="primary"
            :disabled="busy"
            @click="decide(detail, 'approve')"
            >批准货物转移</NButton
          >
          <StockCompletionEditor
            v-if="
              detail.status === 'in_transit' &&
              !detail.confirmations.some((c) => c.status === 'pending')
            "
            :key="detail.code"
            :item="detail"
            :locations="locations"
            :skus="skus"
            :trusted="trusted"
            :disabled="busy"
            @changed="changed"
          />
        </div>
        <div
          v-for="c in detail.confirmations.filter(
            (c) => c.status === 'pending',
          )"
          :key="c.code"
          class="stock-confirmation"
        >
          <div class="stock-detail-heading">
            <span class="status-pill status-pending">完成申报待审阅</span
            ><span>完成日期 {{ c.effective_date }}</span>
          </div>
          <p>完成申请 {{ c.code }}，货物单 {{ c.transfer_code }}</p><p>申报人 {{ c.actor_id }}<template v-if="c.submitted_credential_id">，由 {{ c.submitted_credential_name || c.submitted_credential_id }} 提交</template></p>
          <template v-if="trusted"
            ><p>核对整条转移已实际完成后，批准并记录上述数量。</p>
            <NButton
              type="primary"
              :disabled="busy"
              @click="decide(detail, 'approve', c.code)"
              >批准完成申报</NButton
            >
            <details class="stock-secondary">
              <summary>拒绝完成申报</summary>
              <label
                >拒绝原因<NInput
                  v-model:value="reason"
                  :disabled="busy" /></label
              ><NButton
                :disabled="busy || !reason.trim()"
                @click="decide(detail, 'reject', c.code)"
                >确认拒绝完成申报</NButton
              >
            </details>
          </template>
        </div>
        <details
          v-if="trusted && ['pending', 'in_transit'].includes(detail.status)"
          class="stock-secondary"
        >
          <summary>
            {{
              detail.status === "pending"
                ? "拒绝或取消货物转移"
                : "取消货物转移"
            }}
          </summary>
          <label>原因<NInput v-model:value="reason" :disabled="busy" /></label>
          <div class="actions">
            <NButton
              v-if="detail.status === 'pending'"
              :disabled="busy || !reason.trim()"
              @click="decide(detail, 'reject')"
              >拒绝货物转移</NButton
            ><NButton
              :disabled="busy || !reason.trim()"
              @click="decide(detail, 'cancel')"
              >取消货物转移</NButton
            >
          </div>
        </details>
        <p v-if="!['pending', 'in_transit'].includes(detail.status)">
          该转移已结束。
        </p>
      </section>
      <section class="stock-section">
        <h3>资金关联</h3>
        <p>资金与货物独立生效，关联记录不代表已付款。</p>
        <div v-for="f in detail.fund_references" :key="f.code" class="stock-fund">
          <div class="stock-detail-heading">
            <strong>{{ f.description || f.code }}</strong
            ><span class="status-pill" :class="`status-${f.status}`">{{
              fundStatuses[f.status] || f.status
            }}</span
            ><strong>¥ {{ money(f.amount_minor) }}</strong>
          </div>
          <AccountRoute
            v-if="f.source_account_code"
            :accounts="accounts"
            :source-id="f.source_account_code"
            :destination-id="f.destination_account_code!"
          />
        </div>
        <p v-if="!detail.fund_references.length">未关联资金记录</p>
        <details v-if="trusted" class="stock-secondary">
          <summary>补充已有资金关联</summary>
          <label
            >资金记录<NSelect
              v-model:value="fund"
              :disabled="busy"
              filterable
              remote
              clearable
              :loading="fundLoading"
              :options="fundOptions"
              @search="searchFunds" /></label
          ><NButton
            :disabled="busy || !fund"
            @click="
              run(`/stock-transfers/${detail.code}/fund-references`, {
                fund_transfer_code: fund,
              })
            "
            >关联资金记录</NButton
          >
        </details>
      </section>
      <section class="stock-section">
        <div class="toolbar">
          <h3>关联转移</h3>
          <NButton
            :disabled="busy"
            @click="
              editor?.open({
                related_transfer_code: detail.code,
                source_account_code: detail.source_account_code,
                destination_account_code: detail.destination_account_code,
              })
            "
            >新建关联转移</NButton
          >
        </div>
        <NButton
          v-if="detail.related_transfer_code"
          text
          :disabled="busy"
          @click="open(detail.related_transfer_code)"
          >查看关联原单 {{ detail.related_transfer_code }}</NButton
        >
        <div
          v-for="a in detail.related_transfers"
          :key="a.code"
          class="stock-related"
        >
          <div class="stock-detail-heading">
            <AccountRoute
              :accounts="locations"
              :source-id="a.source_account_code"
              :destination-id="a.destination_account_code"
            /><span class="status-pill" :class="`status-${a.status}`">{{
              stockStatuses[a.status] || a.status
            }}</span
            ><NButton :disabled="busy" @click="open(a.code)">查看详情</NButton>
          </div>
          <div v-for="l in a.lines" :key="l.sku_code">
            <AccountLabel
              :name="`${l.sku_code} ${skus.find((s) => s.code === l.sku_code)?.name || ''}`.trim()"
              :url="skus.find((s) => s.code === l.sku_code)?.avatar_url"
            />
            <strong
              >{{ l.quantity }}
              {{ skus.find((s) => s.code === l.sku_code)?.unit }}</strong
            >
          </div>
        </div>
        <p
          v-if="!detail.related_transfer_code && !detail.related_transfers.length"
        >
          暂无关联转移
        </p>
      </section>
      <section class="stock-section">
        <h3>追溯</h3>
        <details
          v-if="detail.confirmations.some((c) => c.status !== 'pending')"
          class="stock-secondary"
        >
          <summary>完成申报记录</summary>
          <div
            v-for="c in detail.confirmations.filter(
              (c) => c.status !== 'pending',
            )"
            :key="c.code"
          >
            <span class="status-pill" :class="`status-${c.status}`">{{
              stockStatuses[c.status] || fundStatuses[c.status] || c.status
            }}</span>
            <p>完成申请 {{ c.code }}，货物单 {{ c.transfer_code }}</p><p>申报人 {{ c.actor_id }}<template v-if="c.submitted_credential_id">，由 {{ c.submitted_credential_name || c.submitted_credential_id }} 提交</template>；完成日期 {{ c.effective_date }}</p>
            <p v-if="c.approved_by">{{ approvalLabel(completionAudit(c.code)?.detail.mode) }}<template v-if="completionAudit(c.code)?.agent_credential_id">（{{ completionAudit(c.code)?.agent_credential_name || completionAudit(c.code)?.agent_credential_id }}）</template>，审批人 {{ c.approved_by }}</p>
          </div>
        </details>
        <details class="stock-secondary">
          <summary>操作追溯</summary>
          <p v-for="event in detail.audit" :key="event.created_at + event.action">{{ event.actor_id }}<template v-if="event.agent_credential_id">，通过连接 {{ event.agent_credential_name || event.agent_credential_id }}</template>：{{ actionNames[event.action] || event.action }}（{{ new Date(event.created_at).toLocaleString("zh-CN") }}）<span v-if="event.detail.reason">，原因：{{ event.detail.reason }}</span></p>
        </details>
      </section>
    </template>
  </NModal>
  <StockTransferEditor
    ref="editor"
    hide-trigger
    :locations="locations"
    :skus="skus"
    :accounts="accounts"
    @saved="changed"
  />
</template>

<style scoped>
.stock-detail-heading {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.stock-section {
  margin-top: 28px;
  padding-top: 20px;
  border-top: 1px solid var(--uni-border-color);
}
.stock-section h3 {
  margin-top: 0;
}
.stock-meta {
  display: grid;
  grid-template-columns: 80px minmax(0, 1fr);
  gap: 10px 16px;
}
.stock-meta dd {
  margin: 0;
  overflow-wrap: anywhere;
}
.stock-fund-status {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.stock-fund,
.stock-related,
.stock-confirmation {
  margin: 16px 0;
}
.stock-fund .account-route,
.stock-related .stock-detail-heading {
  margin-bottom: 10px;
}
.stock-secondary {
  margin-top: 18px;
}
.stock-secondary summary {
  cursor: pointer;
  margin-bottom: 12px;
}
.confirmation-state {
  margin-top: 8px;
}
@media (max-width: 650px) {
  .stock-meta {
    grid-template-columns: 64px minmax(0, 1fr);
  }
}
</style>
