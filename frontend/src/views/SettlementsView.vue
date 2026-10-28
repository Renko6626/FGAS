<script setup lang="ts">
import { computed, h, onBeforeUnmount, ref, watch } from "vue";
import { NButton, NSelect, type SelectOption } from "naive-ui";
import { money, statuses } from "../presentation/funds";
import type { Account } from "../api/accounts";
import { settlementsApi, type SettlementOverview } from "../api/settlements";
import AccountLabel from "../components/AccountLabel.vue";
import AccountRoute from "../components/AccountRoute.vue";
import SettlementEditor from "../components/SettlementEditor.vue";
const props = defineProps<{ accounts: Account[]; trusted: boolean; targetAccountCode?: string }>();
const emit = defineEmits<{ changed: [] }>();
const selected = ref<string | null>(null),
  detail = ref<SettlementOverview | null>(null),
  show = ref(false),
  direction = ref<"expense" | "receipt">("expense"),
  error = ref(""),
  busy = ref(false),
  activeTab = ref("expense");
const options = computed(() =>
  props.accounts
    .filter((a) => a.kind === "private")
    .map((a) => ({ label: `${a.name}（${a.code}）`, value: a.code })),
);
function renderAccountLabel(option: SelectOption) {
  const account = props.accounts.find((a) => a.code === option.value);
  return h(AccountLabel, {
    name: account?.name || String(option.label ?? option.value),
    code: account?.code,
    url: account?.avatar_url,
  });
}
const groups = computed(() =>
  detail.value
    ? [
        {
          key: "expense" as const,
          title: "报销支出",
          items: detail.value.expenses,
        },
        {
          key: "receipt" as const,
          title: "代收交回",
          items: detail.value.receipts,
        },
      ]
    : [],
);
const expenseOutstanding = computed(
  () =>
    detail.value?.expenses.reduce(
      (sum, item) => sum + item.outstanding_minor,
      0,
    ) ?? 0,
);
const receiptOutstanding = computed(
  () =>
    detail.value?.receipts.reduce(
      (sum, item) => sum + item.outstanding_minor,
      0,
    ) ?? 0,
);
const originalItems = computed(
  () =>
    new Map(
      [
        ...(detail.value?.expenses ?? []),
        ...(detail.value?.receipts ?? []),
      ].map((item) => [item.transfer.code, item.transfer]),
    ),
);
let requestSequence = 0;
async function load() {
  const sequence = ++requestSequence;
  detail.value = null;
  error.value = "";
  if (!selected.value) {
    busy.value = false;
    return;
  }
  busy.value = true;
  try {
    const result = await settlementsApi.overview(selected.value);
    if (sequence === requestSequence) detail.value = result;
  } catch (e) {
    if (sequence === requestSequence) error.value = (e as Error).message;
  } finally {
    if (sequence === requestSequence) busy.value = false;
  }
}
watch(selected, () => {
  activeTab.value = "expense";
  show.value = false;
  void load();
}, { flush: "sync" });
watch(() => props.targetAccountCode, (code) => { if (code) selected.value = code; }, { immediate: true });
onBeforeUnmount(() => { ++requestSequence; });
async function copyLink() {
  if (!selected.value) return;
  try {
    await navigator.clipboard.writeText(`${window.location.origin}/#settlements?account_code=${encodeURIComponent(selected.value)}`);
  } catch { error.value = "复制失败，请手动复制账户编号"; }
}
async function changed() {
  emit("changed");
  await load();
}
function edit(value: "expense" | "receipt") {
  direction.value = value;
  show.value = true;
}
</script>

<template>
  <div class="page-toolbar">
    <NSelect class="account-picker" v-model:value="selected" size="small" :options="options" :render-label="renderAccountLabel" placeholder="选择私账账户" aria-label="私账账户" />
    <div class="page-tools">
      <NButton size="small" :disabled="!selected" :loading="busy" @click="load">刷新</NButton>
      <NButton size="small" :disabled="!selected" @click="copyLink">复制定位链接</NButton>
    </div>
  </div>
  <p v-if="error" class="error">{{ error }}</p>
  <template v-if="detail">
    <div class="settlement-summary">
      <div class="account-balance">
        <span>净余额</span
        ><strong class="balance-value"
          >¥{{ money(detail.account.balance_minor) }}</strong
        >
        <p class="balance-direction">
          {{
            detail.account.balance_minor > 0
              ? "应交回社团"
              : detail.account.balance_minor < 0
                ? "社团应偿还"
                : "净余额为零"
          }}
        </p>
      </div>
      <div class="outstanding-summary">
        <div>
          <span>报销未结</span><strong>¥{{ money(expenseOutstanding) }}</strong>
        </div>
        <div>
          <span>代收未结</span><strong>¥{{ money(receiptOutstanding) }}</strong>
        </div>
      </div>
    </div>
    <div class="page-toolbar settlement-tabs">
      <div class="segmented-tabs" aria-label="结算类别">
      <button
        :class="{ active: activeTab === 'expense' }"
        @click="activeTab = 'expense'"
      >
        报销支出</button
      ><button
        :class="{ active: activeTab === 'receipt' }"
        @click="activeTab = 'receipt'"
      >
        代收交回</button
      ><button
        :class="{ active: activeTab === 'history' }"
        @click="activeTab = 'history'"
      >
        结算历史
      </button>
      </div>
      <div v-if="trusted && activeTab !== 'history'" class="page-tools">
        <NButton size="small" @click="edit(activeTab === 'receipt' ? 'receipt' : 'expense')">{{ activeTab === 'receipt' ? '交回代收款' : '报销支出' }}</NButton>
      </div>
    </div>
    <section
      v-for="group in groups.filter((group) => group.key === activeTab)"
      :key="group.key"
    >
      <div v-if="group.items.length" class="table-wrap compact-table">
        <table>
          <thead>
            <tr>
              <th>日期</th>
              <th>来源 → 去向</th>
              <th>说明 / 标签</th>
              <th class="numeric">金额</th>
              <th class="numeric">已结</th>
              <th class="numeric">未结</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in group.items" :key="item.transfer.code">
              <td>{{ item.transfer.effective_date }}</td>
              <td>
                <AccountRoute
                  :accounts="accounts"
                  :source-id="item.transfer.source_account_code"
                  :destination-id="item.transfer.destination_account_code"
                  :source-name="item.transfer.source_account_name"
                  :destination-name="item.transfer.destination_account_name"
                />
              </td>
              <td>
                <div v-if="item.transfer.description">
                  {{ item.transfer.description }}
                </div>
                <span
                  v-for="tag in item.transfer.tags"
                  :key="tag"
                  class="tag"
                  >{{ tag }}</span
                >
                <details class="record-detail">
                  <summary>记录编号</summary>
                  <small>{{ item.transfer.code }}</small>
                </details>
              </td>
              <td class="numeric">¥{{ money(item.transfer.amount_minor) }}</td>
              <td class="numeric">¥{{ money(item.settled_minor) }}</td>
              <td class="numeric">¥{{ money(item.outstanding_minor) }}</td>
              <td>
                <span
                  class="status-pill"
                  :class="`status-${item.transfer.status}`"
                  >{{
                    statuses[item.transfer.status] || item.transfer.status
                  }}</span
                >
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="empty-state">暂无{{ group.title }}记录</p>
    </section>
    <section v-if="activeTab === 'history'">
      <div v-if="detail.settlements.length" class="table-wrap compact-table">
        <table>
          <thead>
            <tr>
              <th>日期</th>
              <th>来源 → 去向</th>
              <th>说明 / 标签</th>
              <th class="numeric">金额</th>
              <th class="numeric">有效匹配</th>
              <th class="numeric">未匹配</th>
              <th>状态 / 匹配记录</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="payment in detail.settlements"
              :key="payment.transfer.code"
            >
              <td>{{ payment.transfer.effective_date }}</td>
              <td>
                <AccountRoute
                  :accounts="accounts"
                  :source-id="payment.transfer.source_account_code"
                  :destination-id="payment.transfer.destination_account_code"
                  :source-name="payment.transfer.source_account_name"
                  :destination-name="payment.transfer.destination_account_name"
                />
              </td>
              <td>
                <div v-if="payment.transfer.description">
                  {{ payment.transfer.description }}
                </div>
                <span
                  v-for="tag in payment.transfer.tags"
                  :key="tag"
                  class="tag"
                  >{{ tag }}</span
                >
              </td>
              <td class="numeric">
                ¥{{ money(payment.transfer.amount_minor) }}
              </td>
              <td class="numeric">¥{{ money(payment.matched_minor) }}</td>
              <td class="numeric">¥{{ money(payment.unmatched_minor) }}</td>
              <td>
                <span
                  class="status-pill"
                  :class="`status-${payment.transfer.status}`"
                  >{{
                    statuses[payment.transfer.status] || payment.transfer.status
                  }}</span
                >
                <details class="record-detail">
                  <summary>匹配记录（{{ payment.matches.length }}）</summary>
                  <div
                    v-for="(match, index) in payment.matches"
                    :key="`${match.item_transfer_code}-${index}`"
                    class="match-record"
                  >
                    <template v-if="originalItems.get(match.item_transfer_code)"
                      ><p>
                        {{
                          originalItems.get(match.item_transfer_code)!
                            .effective_date
                        }}，原单 ¥{{
                          money(
                            originalItems.get(match.item_transfer_code)!
                              .amount_minor,
                          )
                        }}
                      </p>
                      <AccountRoute
                        :accounts="accounts"
                        :source-id="
                          originalItems.get(match.item_transfer_code)!
                            .source_account_code
                        "
                        :destination-id="
                          originalItems.get(match.item_transfer_code)!
                            .destination_account_code
                        "
                        :source-name="
                          originalItems.get(match.item_transfer_code)!
                            .source_account_name
                        "
                        :destination-name="
                          originalItems.get(match.item_transfer_code)!
                            .destination_account_name
                        "
                    /></template>
                    <p v-else>{{ match.item_transfer_code }}</p>
                    <p>
                      匹配 ¥{{ money(match.amount_minor) }}
                      <span
                        class="status-pill"
                        :class="
                          match.effective ? 'status-posted' : 'status-reversed'
                        "
                        >{{ match.effective ? "有效" : "已失效" }}</span
                      >
                    </p>
                  </div>
                  <small class="history-id"
                    >结算编号：{{ payment.transfer.code }}</small
                  >
                </details>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="empty-state">暂无结算记录</p>
    </section>

    <SettlementEditor
      :show="show"
      :direction="direction"
      :account="detail.account"
      :accounts="accounts"
      :items="direction === 'expense' ? detail.expenses : detail.receipts"
      :payments="detail.settlements"
      @close="show = false"
      @saved="changed"
    />
  </template>
  <p v-else-if="!selected" class="empty-state">选择私账账户后查看结算记录</p>
</template>

<style scoped>
.page-toolbar > .account-picker {
  flex:1 1 240px;
  max-width:440px;
}
.settlement-summary {
  display: flex;
  align-items: center;
  gap: 12px 24px;
  flex-wrap: wrap;
  margin:0 0 12px;
  padding:10px 12px;
  border:1px solid #e1e7e3;
  border-radius:6px;
  background:#f6f9f7;
}
.account-balance {
  display:flex;
  align-items:baseline;
  flex-wrap:wrap;
  gap:4px 10px;
  flex: 1;
  min-width: 180px;
}
.account-balance .balance-value { display:inline; margin:0; font:inherit; font-size:22px; font-weight:650; }
.balance-direction {
  margin:0;
  color:#66766b;
  font-size:12px;
}
.outstanding-summary {
  display: flex;
  gap: 12px 24px;
  flex-wrap: wrap;
}
.outstanding-summary strong {
  display:inline-block;
  font-size:18px;
  font-weight:600;
  font-variant-numeric: tabular-nums;
  margin-left:8px;
}
.settlement-tabs .segmented-tabs { margin-bottom:0; }
.record-detail {
  margin-top: 8px;
  max-width: 420px;
}
.record-detail summary {
  cursor: pointer;
  white-space: nowrap;
}
.record-detail small,
.history-id {
  overflow-wrap: anywhere;
}
.match-record {
  padding: 12px 0;
  min-width: 260px;
}
.match-record p {
  margin: 0 0 6px;
  overflow-wrap: anywhere;
}
.history-id {
  display: block;
  margin-top: 12px;
}
@media (max-width: 760px) {
  .settlement-summary {
    gap:10px;
  }
  .outstanding-summary {
    gap: 24px;
    width: 100%;
  }
}
</style>
