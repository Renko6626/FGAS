<script setup lang="ts">
import { computed, ref } from "vue";
import { NButton, NInput, NModal, NSelect } from "naive-ui";
import {
  api,
  money,
  statuses,
  type Transfer,
  type Account,
} from "../api/funds";
import AccountRoute from "../components/AccountRoute.vue";

const props = defineProps<{
  items: Transfer[];
  accounts: Account[];
  approvals: boolean;
  trusted: boolean;
  hideCreate?: boolean;
}>();
const emit = defineEmits<{ changed: []; notice: [string]; create: [] }>();
const search = ref(""),
  status = ref<string | null>(null),
  tag = ref<string | null>(null);
const dateFrom = ref(""),
  dateTo = ref(""),
  showFilters = ref(false);
const tags = computed(() =>
  [...new Set(props.items.flatMap((t) => t.tags))].map((value) => ({
    label: value,
    value,
  })),
);
const dateError = computed(
  () => dateFrom.value && dateTo.value && dateFrom.value > dateTo.value,
);
const hasFilters = computed(
  () =>
    !!(
      search.value ||
      status.value ||
      tag.value ||
      dateFrom.value ||
      dateTo.value
    ),
);
const items = computed(() => {
  const query = search.value.trim().toLocaleLowerCase();
  return props.items.filter(
    (t) =>
      (!props.approvals || t.status === "pending") &&
      (!status.value || t.status === status.value) &&
      (!tag.value || t.tags.includes(tag.value)) &&
      (!dateFrom.value || t.effective_date >= dateFrom.value) &&
      (!dateTo.value || t.effective_date <= dateTo.value) &&
      (!query ||
        [
          t.source_account_name,
          t.destination_account_name,
          t.description,
          t.counterparty || "",
          t.actor_name,
          ...t.tags,
        ].some((v) => v.toLocaleLowerCase().includes(query))),
  );
});
function resetFilters() {
  search.value = "";
  status.value = null;
  tag.value = null;
  dateFrom.value = "";
  dateTo.value = "";
}
const detail = ref<Transfer | null>(null),
  error = ref(""),
  reason = ref(""),
  busy = ref(false);
const processing = ref<"reject" | "reverse" | null>(null);
type AuditEvent = {
  actor_id: string;
  action: string;
  detail: string;
  created_at: string;
};
const audit = computed(() => (detail.value?.audit || []) as AuditEvent[]);
const actionNames: Record<string, string> = {
  submitted: "提交",
  posted: "批准并过账",
  rejected: "拒绝",
};
async function open(item: Transfer) {
  error.value = "";
  reason.value = "";
  processing.value = null;
  try {
    detail.value = await api.detail(item.id);
  } catch (e) {
    error.value = (e as Error).message;
  }
}
async function decide(approve: boolean) {
  if (!detail.value || busy.value) return;
  if (!approve && !reason.value.trim()) {
    error.value = "请填写拒绝原因";
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    detail.value = await api.decide(detail.value, approve, reason.value);
    processing.value = null;
    emit("changed");
    emit("notice", approve ? "审批已过账" : "已拒绝");
  } catch (e) {
    error.value = (e as Error).message;
    detail.value = await api.detail(detail.value.id).catch(() => detail.value);
  } finally {
    busy.value = false;
  }
}
async function reverse() {
  if (busy.value) return;
  if (!detail.value || !reason.value.trim()) {
    error.value = "请填写冲销原因";
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    const result = await api.reverse(detail.value.id, reason.value);
    emit("notice", "冲销流水" + (statuses[result.status] || result.status));
    detail.value = await api.detail(detail.value.id);
    processing.value = null;
    emit("changed");
  } catch (e) {
    error.value =
      (e as Error).message + "。请查看流水记录后再决定是否重新提交。";
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div class="ledger-toolbar">
    <NInput
      v-model:value="search"
      clearable
      placeholder="搜索账户、说明或发起人"
      :input-props="{ 'aria-label': '搜索资金流水' }"
    />
    <NSelect
      v-if="!approvals"
      v-model:value="status"
      clearable
      placeholder="全部状态"
      :options="
        Object.entries(statuses).map(([value, label]) => ({ value, label }))
      "
    />
    <NButton :aria-expanded="showFilters" @click="showFilters = !showFilters">{{
      showFilters ? "收起筛选" : "更多筛选"
    }}</NButton>
  </div>
  <div v-if="showFilters" class="ledger-filters">
    <label
      >标签<NSelect
        v-model:value="tag"
        clearable
        placeholder="所有标签"
        :options="tags"
    /></label>
    <label>业务日期起<input v-model="dateFrom" type="date" /></label
    ><label>业务日期止<input v-model="dateTo" type="date" /></label>
  </div>
  <div class="ledger-count">
    <span>{{ items.length }} 笔{{ approvals ? "待审批" : "流水" }}</span
    ><NButton v-if="hasFilters" class="plain-button" text @click="resetFilters"
      >清空筛选</NButton
    >
  </div>
  <p v-if="dateError" class="error" role="alert">开始日期不能晚于结束日期。</p>
  <p v-if="error && !detail" class="error" role="alert">{{ error }}</p>
  <div v-if="!items.length" class="empty-state">
    <p>
      {{
        hasFilters
          ? "没有符合条件的流水"
          : approvals
            ? "暂无待审批的资金申请"
            : "暂无资金流水"
      }}
    </p>
    <NButton v-if="hasFilters" @click="resetFilters">清空筛选</NButton
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
          <td>{{ t.actor_name }}</td>
          <td>
            <NButton class="plain-button" text size="small" @click="open(t)">{{
              approvals ? "审批" : "详情"
            }}</NButton>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
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
        <dd>{{ detail.actor_name }}</dd>
        <dt>审批</dt>
        <dd>
          {{
            detail.approval_mode === "automatic"
              ? "自动批准"
              : detail.approval_mode === "manual"
                ? "人工批准"
                : "待处理"
          }}<template v-if="detail.approved_by_name"
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
            ><span>{{ event.actor_id }}</span
            ><small>{{
              new Date(event.created_at).toLocaleString("zh-CN")
            }}</small>
            <p v-if="event.detail">
              {{
                event.detail === "automatic"
                  ? "自动批准"
                  : event.detail === "manual"
                    ? "人工批准"
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
.ledger-toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
}
.ledger-toolbar > .n-input {
  flex: 1;
  min-width: 180px;
}
.ledger-toolbar > .n-select {
  width: 150px;
  flex-shrink: 0;
}
.ledger-filters {
  display: grid;
  grid-template-columns: minmax(150px, 1fr) 180px 180px;
  gap: 16px;
  margin: 12px 0;
}
.ledger-filters input {
  width: 100%;
  height: 34px;
}
.ledger-count {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #666;
  margin: 20px 0 12px;
  font-size: 12px;
  min-height: 24px;
}
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
  .ledger-toolbar {
    flex-wrap: wrap;
  }
  .ledger-toolbar > .n-input {
    flex-basis: 100%;
  }
  .ledger-toolbar > .n-select {
    flex: 1;
  }
  .ledger-filters {
    grid-template-columns: 1fr 1fr;
  }
  .ledger-filters > label:first-child {
    grid-column: 1 / -1;
  }
  .ledger-filters > label {
    min-width: 0;
  }
  .ledger-detail-heading > strong {
    font-size: 30px;
  }
}
</style>
