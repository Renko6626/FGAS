<script setup lang="ts">
import { computed, h, onBeforeUnmount, ref, watch } from "vue";
import { NButton, NInput, NSelect, type SelectOption } from "naive-ui";
import { money, statuses } from "../presentation/funds";
import type { Account } from "../api/accounts";
import { settlementsApi, type SettlementOverview } from "../api/settlements";
import AccountAvatar from "../components/AccountAvatar.vue";
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
const search = ref("");
const privateAccounts = computed(() => props.accounts.filter(account => account.kind === "private"));
const accountRows = computed(() => {
  const query = search.value.trim().toLocaleLowerCase();
  return privateAccounts.value.filter(account => !query ||
    `${account.name} ${account.code} ${account.member_name || ''}`.toLocaleLowerCase().includes(query))
    .sort((a, b) => Math.abs(b.balance_minor) - Math.abs(a.balance_minor) || a.name.localeCompare(b.name, 'zh-CN'));
});
const receivable = computed(() => privateAccounts.value.reduce((sum, account) => sum + Math.max(account.balance_minor, 0), 0));
const payable = computed(() => privateAccounts.value.reduce((sum, account) => sum + Math.max(-account.balance_minor, 0), 0));
function balanceDirection(value: number) {
  return value > 0 ? "成员应交回" : value < 0 ? "社团应偿还" : "净余额为零";
}
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
  <template v-if="!selected">
    <div class="settlement-overview" aria-label="私账往来净余额">
      <div><span>成员应交回（净额）</span><strong>¥ {{ money(receivable) }}</strong></div>
      <div><span>社团应偿还（净额）</span><strong>¥ {{ money(payable) }}</strong></div>
      <small>{{ privateAccounts.length }} 个私账</small>
    </div>
    <p class="settlement-caption">净余额说明往来方向。逐笔未结款项请进入账户核对，净余额为零也可能有未结明细。</p>
    <div class="page-toolbar"><NInput v-model:value="search" clearable placeholder="搜索私账、成员或账户编号" :input-props="{ 'aria-label': '搜索私账' }" /><span class="page-count">{{ accountRows.length }} 个账户</span></div>
    <div v-if="accountRows.length" class="settlement-accounts">
      <button v-for="account in accountRows" :key="account.code" class="settlement-account" @click="selected = account.code">
        <AccountAvatar :name="account.name" :url="account.avatar_url" />
        <span class="settlement-account-name"><strong>{{ account.name }}</strong><small>{{ account.code }}<template v-if="account.member_name">　{{ account.member_name }}</template><template v-if="!account.active">　已停用</template></small></span>
        <span class="settlement-account-balance"><strong>¥ {{ money(Math.abs(account.balance_minor)) }}</strong><small>{{ balanceDirection(account.balance_minor) }}</small></span>
        <span class="settlement-account-open">查看明细 <span aria-hidden="true">›</span></span>
      </button>
    </div>
    <div v-else class="empty-state"><p>{{ privateAccounts.length ? '没有符合条件的私账' : '还没有私账账户，可在资金账户中建立。' }}</p><NButton v-if="search" size="small" @click="search = ''">清空搜索</NButton></div>
  </template>
  <div v-else class="page-toolbar">
    <NButton size="small" @click="selected = null">全部私账</NButton>
    <NSelect class="account-picker" v-model:value="selected" size="small" :options="options" :render-label="renderAccountLabel" placeholder="选择私账账户" aria-label="私账账户" />
    <div class="page-tools"><NButton size="small" :loading="busy" @click="load">刷新</NButton><NButton size="small" @click="copyLink">复制定位链接</NButton></div>
  </div>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <p v-if="selected && busy && !detail" class="empty-state" role="status">正在读取结算明细…</p>
  <template v-if="detail">
    <div class="settlement-summary">
      <div class="account-balance"><span>净余额</span><strong class="balance-value">¥{{ money(detail.account.balance_minor) }}</strong><p class="balance-direction">{{ balanceDirection(detail.account.balance_minor) }}</p></div>
      <div class="outstanding-summary"><div><span>报销未结</span><strong>¥{{ money(expenseOutstanding) }}</strong></div><div><span>代收未结</span><strong>¥{{ money(receiptOutstanding) }}</strong></div></div>
    </div>
    <div class="page-toolbar settlement-tabs">
      <div class="segmented-tabs" aria-label="结算类别"><button :class="{ active: activeTab === 'expense' }" @click="activeTab = 'expense'">报销支出</button><button :class="{ active: activeTab === 'receipt' }" @click="activeTab = 'receipt'">代收交回</button><button :class="{ active: activeTab === 'history' }" @click="activeTab = 'history'">结算历史</button></div>
      <div v-if="trusted && activeTab !== 'history'" class="page-tools"><NButton size="small" type="primary" @click="edit(activeTab === 'receipt' ? 'receipt' : 'expense')">{{ activeTab === 'receipt' ? '交回代收款' : '报销支出' }}</NButton></div>
    </div>
    <section v-for="group in groups.filter(group => group.key === activeTab)" :key="group.key">
      <div v-if="group.items.length" class="table-wrap compact-table responsive-table">
        <table class="settlement-table">
          <colgroup><col style="width:26%" /><col style="width:12%" /><col style="width:32%" /><col style="width:10%" /><col style="width:10%" /><col style="width:10%" /></colgroup>
          <thead><tr><th>事项 / 日期</th><th class="numeric">金额</th><th>来源 → 去向</th><th class="numeric">已结</th><th class="numeric">未结</th><th>状态</th></tr></thead>
          <tbody><tr v-for="item in group.items" :key="item.transfer.code">
            <td class="table-primary"><strong>{{ item.transfer.description || '未填写说明' }}</strong><small>{{ item.transfer.effective_date }}　{{ item.transfer.code }}</small><span v-for="tag in item.transfer.tags" :key="tag" class="tag">{{ tag }}</span></td>
            <td class="numeric table-priority" data-label="金额"><strong>¥{{ money(item.transfer.amount_minor) }}</strong></td>
            <td class="settlement-route-cell table-route" data-label="来源 → 去向"><AccountRoute :accounts="accounts" :source-id="item.transfer.source_account_code" :destination-id="item.transfer.destination_account_code" :source-name="item.transfer.source_account_name" :destination-name="item.transfer.destination_account_name" /></td>
            <td class="numeric" data-label="已结">¥{{ money(item.settled_minor) }}</td>
            <td class="numeric" data-label="未结"><strong>¥{{ money(item.outstanding_minor) }}</strong></td>
            <td class="table-priority" data-label="状态"><span class="status-pill" :class="`status-${item.transfer.status}`">{{ statuses[item.transfer.status] || item.transfer.status }}</span></td>
          </tr></tbody>
        </table>
      </div><p v-else class="empty-state">暂无{{ group.title }}记录</p>
    </section>
    <section v-if="activeTab === 'history'">
      <div v-if="detail.settlements.length" class="table-wrap compact-table responsive-table">
        <table class="settlement-table">
          <colgroup><col style="width:26%" /><col style="width:12%" /><col style="width:32%" /><col style="width:10%" /><col style="width:10%" /><col style="width:10%" /></colgroup>
          <thead><tr><th>事项 / 匹配记录</th><th class="numeric">金额</th><th>来源 → 去向</th><th class="numeric">有效匹配</th><th class="numeric">未匹配</th><th>状态</th></tr></thead>
          <tbody><tr v-for="payment in detail.settlements" :key="payment.transfer.code">
            <td class="table-primary"><strong>{{ payment.transfer.description || '结算付款' }}</strong><small>{{ payment.transfer.effective_date }}　{{ payment.transfer.code }}</small><span v-for="tag in payment.transfer.tags" :key="tag" class="tag">{{ tag }}</span>
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
            <td class="numeric table-priority" data-label="金额"><strong>¥{{ money(payment.transfer.amount_minor) }}</strong></td>
            <td class="settlement-route-cell table-route" data-label="来源 → 去向"><AccountRoute :accounts="accounts" :source-id="payment.transfer.source_account_code" :destination-id="payment.transfer.destination_account_code" :source-name="payment.transfer.source_account_name" :destination-name="payment.transfer.destination_account_name" /></td>
            <td class="numeric" data-label="有效匹配">¥{{ money(payment.matched_minor) }}</td>
            <td class="numeric" data-label="未匹配">¥{{ money(payment.unmatched_minor) }}</td>
            <td class="table-priority" data-label="状态"><span class="status-pill" :class="`status-${payment.transfer.status}`">{{ statuses[payment.transfer.status] || payment.transfer.status }}</span></td>
          </tr></tbody>
        </table>
      </div><p v-else class="empty-state">暂无结算记录</p>
    </section>
    <SettlementEditor :show="show" :direction="direction" :account="detail.account" :accounts="accounts" :items="direction === 'expense' ? detail.expenses : detail.receipts" :payments="detail.settlements" @close="show = false" @saved="changed" />
  </template>
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
  border:1px solid var(--line);
  border-radius:6px;
  background:#f8f9fb;
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
  color:#657286;
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
.settlement-table { table-layout:fixed; min-width:920px; }
.settlement-table .table-primary > strong { font-size:13px; font-weight:600; }
.settlement-table .table-primary > small { color:#788391; font-size:11px; }
.settlement-route-cell { overflow-wrap:anywhere; }
.settlement-table :deep(.account-avatar) { display:none; }
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
  min-width: 0;
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

.settlement-overview { display:flex; align-items:center; flex-wrap:wrap; gap:16px 36px; padding:4px 0 14px; border-bottom:1px solid var(--line); }
.settlement-overview > div { display:flex; flex-wrap:wrap; align-items:baseline; gap:8px 12px; }
.settlement-overview span { color:#788391; font-size:12px; }.settlement-overview strong { font-size:22px; font-weight:650; font-variant-numeric:tabular-nums; }.settlement-overview > small { margin-left:auto; font-size:12px; }
.settlement-caption { margin:10px 0 16px; color:#788391; font-size:12px; }
.settlement-accounts { border-top:1px solid var(--line); }
.settlement-account { display:flex; align-items:center; width:100%; min-width:0; gap:12px; padding:14px 10px; border:0; border-bottom:1px solid var(--line); background:white; text-align:left; color:#29323e; }
.settlement-account:hover,.settlement-account:focus-visible { background:#f5f7fa; }.settlement-account :deep(.account-avatar) { width:32px; height:32px; margin:0; flex:none; font-size:14px; }
.settlement-account-name { min-width:0; flex:1; }.settlement-account-name strong { display:block; font-size:14px; font-weight:600; overflow-wrap:anywhere; }.settlement-account small { display:block; color:#788391; font-size:11px; margin-top:3px; }
.settlement-account-balance { text-align:right; flex:none; font-variant-numeric:tabular-nums; }.settlement-account-balance strong { font-size:16px; font-weight:600; }.settlement-account-open { display:flex; align-items:center; gap:8px; margin-left:24px; font-size:12px; color:#788391; }
@media(max-width:760px) { .settlement-overview { gap:12px; }.settlement-overview > div { justify-content:space-between; width:100%; }.settlement-overview > small { margin-left:0; }.settlement-account { padding:12px 0; gap:8px; }.settlement-account-open { display:none; }.settlement-account-balance strong { font-size:14px; }.settlement-account :deep(.account-avatar) { display:none; } }
</style>
