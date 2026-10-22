<script setup lang="ts">
import { ref, computed, onBeforeUnmount, onMounted, watch } from "vue";
import { NButton, NInput, NModal, NSelect } from "naive-ui";
import type { StockAccount } from "../api/funds";
import { api, money, approvalLabel, statuses as fundStatuses } from "../api/funds";
import { warehouse, stockStatuses, type StockTransfer } from "../api/warehouse";
import AccountRoute from "../components/AccountRoute.vue";
import AccountLabel from "../components/AccountLabel.vue";
import StockCompletionEditor from "../components/StockCompletionEditor.vue";
import StockTransferEditor from "../components/StockTransferEditor.vue";
import PaginationBar from "../components/PaginationBar.vue";
import type { Sku, Account } from "../api/funds";
const props = defineProps<{
  items?: StockTransfer[];
  locations: StockAccount[];
  trusted: boolean;
  skus: Sku[];
  accounts: Account[];
  approvals?: boolean;
  revision?: number;
}>();
const emit = defineEmits<{ changed: [] }>();
const local = computed(() => props.items !== undefined);
const remoteItems = ref<StockTransfer[]>([]);
const page = ref(1), limit = ref(20), total = ref(0), loading = ref(false);
let filterTimer: number | undefined;
const editor = ref<InstanceType<typeof StockTransferEditor> | null>(null);
const tag = ref<string | null>(null),
  search = ref(""),
  status = ref<string | null>(null);
const fund = ref(""), fundResults = ref<{ label: string; value: string }[]>([]),
  fundCache = ref<Record<string, string>>({}), fundLoading = ref(false);
let fundTimer: number | undefined;
const statusOptions = computed(() =>
  Object.entries(stockStatuses).map(([value, label]) => ({ label, value })),
);
const tags = computed(() =>
  [...new Set((props.items ?? remoteItems.value).flatMap((t) => t.tags))].map((value) => ({
    label: value,
    value,
  })),
);
const detailShow = ref(false),
  detail = ref<StockTransfer | null>(null),
  busy = ref(false),
  error = ref(""),
  reason = ref("");
const items = computed(() => {
  if (!local.value) return remoteItems.value;
  return props.items!.filter(
    (t) =>
      (!props.approvals ||
        t.status === "pending" ||
        t.confirmations.some((c) => c.status === "pending")) &&
      (!tag.value || t.tags.includes(tag.value)) &&
      (!status.value || t.status === status.value) &&
      (!search.value ||
        [
          t.id,
          t.description,
          t.source_account_name,
          t.destination_account_name,
          ...t.lines.map((l) => l.sku_name),
        ]
          .join(" ")
          .toLowerCase()
          .includes(search.value.trim().toLowerCase())),
  );
});
function params() {
  const values: Record<string, string | number | boolean | undefined> = {
    page: page.value,
    limit: limit.value,
  };
  if (props.approvals) values.attention = true;
  else if (status.value) values.status = status.value;
  if (tag.value) values.tag = tag.value;
  if (search.value.trim()) values.q = search.value.trim();
  return values;
}
async function load() {
  if (local.value) return;
  loading.value = true;
  try {
    const result = await warehouse.transfers(params());
    remoteItems.value = result.items;
    total.value = result.total;
    error.value = "";
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    loading.value = false;
  }
}
function scheduleLoad() {
  window.clearTimeout(filterTimer);
  filterTimer = window.setTimeout(load, 250);
}
watch([search, status, tag], () => {
  if (local.value) return;
  const wasFirst = page.value === 1;
  page.value = 1;
  if (wasFirst) scheduleLoad();
});
watch(page, () => {
  if (!local.value) load();
});
watch(limit, () => {
  window.clearTimeout(filterTimer);
  if (page.value === 1) load();
  else page.value = 1;
});
watch(() => props.revision, () => {
  if (!local.value) load();
});
onMounted(() => {
  if (!local.value) load();
  searchFunds("");
});
onBeforeUnmount(() => {
  window.clearTimeout(filterTimer);
  window.clearTimeout(fundTimer);
});
async function searchFunds(query: string) {
  window.clearTimeout(fundTimer);
  fundTimer = window.setTimeout(async () => {
    fundLoading.value = true;
    try {
      const result = await api.transfers({ q: query.trim() || undefined, limit: 20 });
      fundResults.value = result.items.map((f) => {
        const label = `${f.description || f.id}（${fundStatuses[f.status] || f.status}）`;
        fundCache.value[f.id] = label;
        return { label, value: f.id };
      });
    } catch {
      fundResults.value = [];
    } finally {
      fundLoading.value = false;
    }
  }, 200);
}
const fundOptions = computed(() => {
  const options = [...fundResults.value];
  if (fund.value && !options.some((option) => option.value === fund.value))
    options.unshift({ label: fundCache.value[fund.value] || fund.value, value: fund.value });
  return options;
});
const approvalAgent = computed(() => detail.value?.audit.find(event => ["approve", "automatic_approval"].includes(event.action) && event.agent_credential_id));
async function open(id: string) {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    detail.value = await warehouse.detail(id);
    detailShow.value = true;
    reason.value = "";
    fund.value = "";
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
async function changed() {
  emit("changed");
  if (detail.value) await open(detail.value.id);
}
async function run(path: string, body: unknown) {
  if (busy.value) return;
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
    : `/stock-transfers/${item.id}/${action}`;
  run(
    path,
    ["reject", "cancel"].includes(action) ? { reason: reason.value } : {},
  );
}
</script>
<template>
  <div class="toolbar">
    <h2>{{ approvals ? "货物审批与完成申报" : "货物转移记录" }}</h2>
    <NButton :disabled="busy" @click="emit('changed')">刷新</NButton>
  </div>
  <div class="stock-filters">
    <NInput
      v-model:value="search"
      clearable
      placeholder="搜索用途、货物、来源或去向"
    />
    <NSelect
      v-model:value="status"
      clearable
      :options="statusOptions"
      placeholder="所有货物状态"
    />
    <NSelect
      v-model:value="tag"
      clearable
      filterable
      tag
      :options="tags"
      placeholder="所有标签"
    />
  </div>
  <p v-if="error && !detailShow" class="error">{{ error }}</p>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>日期 / 用途</th>
          <th>来源 → 去向</th>
          <th>货物数量</th>
          <th>货物状态</th>
          <th>关联资金</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="t in items" :key="t.id">
          <td>
            <div>{{ t.effective_date }}</div>
            <div v-if="t.description">{{ t.description }}</div>
            <small v-if="t.tags.length">{{ t.tags.join("，") }}</small>
          </td>
          <td>
            <AccountRoute
              :accounts="locations"
              :source-id="t.source_account_id"
              :destination-id="t.destination_account_id"
              :source-name="t.source_account_name"
              :destination-name="t.destination_account_name"
            />
          </td>
          <td>
            <div v-for="l in t.lines" :key="l.id">
              <AccountLabel
                :name="l.sku_name"
                :url="skus.find((s) => s.id === l.sku_id)?.avatar_url"
              />
              <strong>{{ l.quantity }} {{ l.unit }}</strong>
            </div>
          </td>
          <td>
            <span class="status-pill" :class="`status-${t.status}`">{{
              stockStatuses[t.status] || t.status
            }}</span>
            <div
              v-if="t.confirmations.some((c) => c.status === 'pending')"
              class="confirmation-state"
            >
              完成申报待审阅
            </div>
          </td>
          <td>
            <div
              v-for="f in t.fund_references"
              :key="f.id"
              class="stock-fund-status"
            >
              <span class="status-pill" :class="`status-${f.status}`">{{
                fundStatuses[f.status] || f.status
              }}</span
              ><span>¥ {{ money(f.amount_minor) }}</span>
            </div>
            <span v-if="!t.fund_references.length">未关联</span>
          </td>
          <td>
            <NButton :disabled="busy" @click="open(t.id)">详情 / 处理</NButton>
          </td>
        </tr>
        <tr v-if="!items.length">
          <td colspan="6">{{ !local && loading ? "正在读取货物转移" : "暂无符合条件的货物转移" }}</td>
        </tr>
      </tbody>
    </table>
  </div>
  <PaginationBar
    v-if="!local"
    :page="page"
    :limit="limit"
    :total="total"
    @update:page="page = $event"
    @update:limit="limit = $event"
  />
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
          :source-id="detail.source_account_id"
          :destination-id="detail.destination_account_id"
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
          <dd>{{ detail.id }}</dd>
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
              <tr v-for="l in detail.lines" :key="l.id">
                <td>
                  <AccountLabel
                    :name="l.sku_name"
                    :url="skus.find((s) => s.id === l.sku_id)?.avatar_url"
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
          <NButton :loading="busy" :disabled="busy" @click="open(detail.id)"
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
            :key="detail.id"
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
          :key="c.id"
          class="stock-confirmation"
        >
          <div class="stock-detail-heading">
            <span class="status-pill status-pending">完成申报待审阅</span
            ><span>完成日期 {{ c.effective_date }}</span>
          </div>
          <p>申报人 {{ c.actor_id }}<template v-if="c.submitted_credential_id">，由 {{ c.submitted_credential_name || c.submitted_credential_id }} 提交</template></p>
          <template v-if="trusted"
            ><p>核对整条转移已实际完成后，批准并记录上述数量。</p>
            <NButton
              type="primary"
              :disabled="busy"
              @click="decide(detail, 'approve', c.id)"
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
                @click="decide(detail, 'reject', c.id)"
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
        <div v-for="f in detail.fund_references" :key="f.id" class="stock-fund">
          <div class="stock-detail-heading">
            <strong>{{ f.description || f.id }}</strong
            ><span class="status-pill" :class="`status-${f.status}`">{{
              fundStatuses[f.status] || f.status
            }}</span
            ><strong>¥ {{ money(f.amount_minor) }}</strong>
          </div>
          <AccountRoute
            v-if="f.source_account_id"
            :accounts="accounts"
            :source-id="f.source_account_id"
            :destination-id="f.destination_account_id!"
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
              run(`/stock-transfers/${detail.id}/fund-references`, {
                fund_transfer_id: fund,
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
                related_transfer_id: detail.id,
                source_account_id: detail.source_account_id,
                destination_account_id: detail.destination_account_id,
              })
            "
            >新建关联转移</NButton
          >
        </div>
        <NButton
          v-if="detail.related_transfer_id"
          text
          :disabled="busy"
          @click="open(detail.related_transfer_id)"
          >查看关联原单 {{ detail.related_transfer_id }}</NButton
        >
        <div
          v-for="a in detail.related_transfers"
          :key="a.id"
          class="stock-related"
        >
          <div class="stock-detail-heading">
            <AccountRoute
              :accounts="locations"
              :source-id="a.source_account_id"
              :destination-id="a.destination_account_id"
            /><span class="status-pill" :class="`status-${a.status}`">{{
              stockStatuses[a.status] || a.status
            }}</span
            ><NButton :disabled="busy" @click="open(a.id)">查看详情</NButton>
          </div>
          <div v-for="l in a.lines" :key="l.sku_id">
            <AccountLabel
              :name="skus.find((s) => s.id === l.sku_id)?.name || l.sku_id"
              :url="skus.find((s) => s.id === l.sku_id)?.avatar_url"
            />
            <strong
              >{{ l.quantity }}
              {{ skus.find((s) => s.id === l.sku_id)?.unit }}</strong
            >
          </div>
        </div>
        <p
          v-if="!detail.related_transfer_id && !detail.related_transfers.length"
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
            :key="c.id"
          >
            <span class="status-pill" :class="`status-${c.status}`">{{
              stockStatuses[c.status] || fundStatuses[c.status] || c.status
            }}</span>
            <p>申报人 {{ c.actor_id }}<template v-if="c.submitted_credential_id">，由 {{ c.submitted_credential_name || c.submitted_credential_id }} 提交</template>；完成日期 {{ c.effective_date }}</p>
            <p v-if="c.approved_by">{{ approvalLabel(c.execution_snapshot?.mode || "manual") }}<template v-if="c.execution_snapshot?.agent_credential_id">（{{ c.execution_snapshot.agent_credential_name || c.execution_snapshot.agent_credential_id }}）</template>，审批人 {{ c.approved_by }}</p>
          </div>
        </details>
        <details class="stock-secondary">
          <summary>原批准范围与资金快照</summary>
          <pre>{{ JSON.stringify(detail.approval_snapshot, null, 2) }}</pre>
        </details>
        <details class="stock-secondary">
          <summary>操作追溯</summary>
          <p v-for="event in detail.audit" :key="event.created_at + event.action">{{ event.actor_id }}<template v-if="event.agent_credential_id">，通过连接 {{ event.agent_credential_name || event.agent_credential_id }}</template>：{{ event.action }}（{{ new Date(event.created_at).toLocaleString("zh-CN") }}）</p>
          <pre>{{ JSON.stringify(detail.audit, null, 2) }}</pre>
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
.stock-filters {
  display: grid;
  grid-template-columns: minmax(240px, 2fr) minmax(160px, 1fr) minmax(
      140px,
      1fr
    );
  gap: 16px;
  margin-bottom: 24px;
}
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
pre {
  overflow: auto;
  max-height: 320px;
}
@media (max-width: 650px) {
  .stock-filters {
    grid-template-columns: 1fr;
  }
  .stock-meta {
    grid-template-columns: 64px minmax(0, 1fr);
  }
}
</style>
