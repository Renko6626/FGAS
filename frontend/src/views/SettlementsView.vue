<script setup lang="ts">
import { computed, h, ref, watch } from "vue";
import { NButton, NSelect, type SelectOption } from "naive-ui";
import { money, statuses } from "../api/funds";
import type { Account } from "../api/accounts";
import { settlementsApi, type SettlementOverview } from "../api/settlements";
import AccountLabel from "../components/AccountLabel.vue";
import AccountRoute from "../components/AccountRoute.vue";
import SettlementEditor from "../components/SettlementEditor.vue";
const props = defineProps<{ accounts: Account[]; trusted: boolean }>();
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
    .map((a) => ({ label: a.name, value: a.id })),
);
function renderAccountLabel(option: SelectOption) {
  const account = props.accounts.find((a) => a.id === option.value);
  return h(AccountLabel, {
    name: account?.name || String(option.label ?? option.value),
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
      ].map((item) => [item.transfer.id, item.transfer]),
    ),
);
async function load() {
  detail.value = null;
  if (!selected.value) return;
  busy.value = true;
  error.value = "";
  try {
    detail.value = await settlementsApi.overview(selected.value);
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
watch(selected, () => {
  activeTab.value = "expense";
  show.value = false;
  void load();
});
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
  <div class="toolbar">
    <h2>私账结算</h2>
    <NButton :disabled="!selected" :loading="busy" @click="load">刷新</NButton>
  </div>
  <label class="account-picker"
    >私账账户<NSelect
      v-model:value="selected"
      :options="options"
      :render-label="renderAccountLabel"
      placeholder="选择私账账户"
  /></label>
  <p v-if="error" class="error">{{ error }}</p>
  <template v-if="detail">
    <div class="settlement-summary">
      <div class="account-balance">
        <h3>
          <AccountLabel
            :name="detail.account.name"
            :url="detail.account.avatar_url"
          />
        </h3>
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
    <section
      v-for="group in groups.filter((group) => group.key === activeTab)"
      :key="group.key"
    >
      <div class="toolbar">
        <h3>{{ group.title }}</h3>
        <NButton v-if="trusted" @click="edit(group.key)">{{
          group.key === "expense" ? "报销支出" : "交回代收款"
        }}</NButton>
      </div>
      <div v-if="group.items.length" class="table-wrap">
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
            <tr v-for="item in group.items" :key="item.transfer.id">
              <td>{{ item.transfer.effective_date }}</td>
              <td>
                <AccountRoute
                  :accounts="accounts"
                  :source-id="item.transfer.source_account_id"
                  :destination-id="item.transfer.destination_account_id"
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
                  <small>{{ item.transfer.id }}</small>
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
      <div v-if="detail.settlements.length" class="table-wrap">
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
              :key="payment.transfer.id"
            >
              <td>{{ payment.transfer.effective_date }}</td>
              <td>
                <AccountRoute
                  :accounts="accounts"
                  :source-id="payment.transfer.source_account_id"
                  :destination-id="payment.transfer.destination_account_id"
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
                    :key="`${match.item_transfer_id}-${index}`"
                    class="match-record"
                  >
                    <template v-if="originalItems.get(match.item_transfer_id)"
                      ><p>
                        {{
                          originalItems.get(match.item_transfer_id)!
                            .effective_date
                        }}，原单 ¥{{
                          money(
                            originalItems.get(match.item_transfer_id)!
                              .amount_minor,
                          )
                        }}
                      </p>
                      <AccountRoute
                        :accounts="accounts"
                        :source-id="
                          originalItems.get(match.item_transfer_id)!
                            .source_account_id
                        "
                        :destination-id="
                          originalItems.get(match.item_transfer_id)!
                            .destination_account_id
                        "
                        :source-name="
                          originalItems.get(match.item_transfer_id)!
                            .source_account_name
                        "
                        :destination-name="
                          originalItems.get(match.item_transfer_id)!
                            .destination_account_name
                        "
                    /></template>
                    <p v-else>{{ match.item_transfer_id }}</p>
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
                    >结算编号：{{ payment.transfer.id }}</small
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
.account-picker {
  max-width: 440px;
  margin-bottom: 24px;
}
.settlement-summary {
  display: flex;
  align-items: center;
  gap: 40px;
  flex-wrap: wrap;
  margin: 24px 0 28px;
}
.account-balance {
  flex: 1;
  min-width: 180px;
}
.account-balance h3 {
  margin-bottom: 12px;
}
.balance-direction {
  margin: 4px 0 0;
}
.outstanding-summary {
  display: flex;
  gap: 36px;
  flex-wrap: wrap;
}
.outstanding-summary strong {
  display: block;
  font-size: 24px;
  font-weight: normal;
  font-variant-numeric: tabular-nums;
  margin-top: 4px;
}
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
    gap: 20px;
  }
  .outstanding-summary {
    gap: 24px;
    width: 100%;
  }
}
</style>
