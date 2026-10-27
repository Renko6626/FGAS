<script setup lang="ts">
import { computed, ref } from "vue";
import { NButton } from "naive-ui";
import { money, statuses } from "../presentation/funds";
import { stockStatuses } from "../presentation/warehouse";
import type { Dashboard } from "../api/dashboard";
import type { Account } from "../api/accounts";
import AccountAvatar from "../components/AccountAvatar.vue";
import AccountRoute from "../components/AccountRoute.vue";

const props = defineProps<{ data: Dashboard | null; accounts: Account[]; loading: boolean; trusted: boolean }>();
const emit = defineEmits<{
  navigate: [string, ("funds" | "stock")?, string?];
  create: [];
  createStock: [];
}>();
const filter = ref<"all" | "funds" | "stock">("all");
const filters = [{ value: "all", label: "全部" }, { value: "funds", label: "资金" }, { value: "stock", label: "货物" }] as const;
const operations = computed(() => props.data?.operations[filter.value] ?? []);
const stockedKinds = computed(() => props.data?.stock.skus.filter(row => BigInt(row.quantity) > 0n).length ?? 0);
const featuredSkus = computed(() => props.data?.stock.skus.slice(0, 4) ?? []);
const unsettledAccounts = computed(() => props.accounts.filter(account => account.kind === "private" && account.balance_minor !== 0));
const memberReceivable = computed(() => unsettledAccounts.value.reduce((total, account) => total + Math.max(account.balance_minor, 0), 0));
const memberPayable = computed(() => unsettledAccounts.value.reduce((total, account) => total + Math.max(-account.balance_minor, 0), 0));
function signedMoney(value: number) { return `${value > 0 ? "+" : ""}${money(value)}`; }
function signedQuantity(value: string) { return `${BigInt(value) > 0n ? "+" : ""}${value}`; }
function tone(value: string | number) { return BigInt(value) > 0n ? "increase" : BigInt(value) < 0n ? "decrease" : "unchanged"; }
function dateTime(value: string | null) {
  return value ? new Date(value).toLocaleString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }) : "入账时间未记录";
}
function fullDate(value: string) { return new Date(value).toLocaleString("zh-CN", { hour12: false }); }
function shortDate(value: string | null) {
  return value ? new Date(value).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }) : "—";
}
function stockChangeText(item: Dashboard['stock']['recent'][number]) {
  return item.lines.map(line => `${line.sku_code} ${line.sku_name} ${signedQuantity(line.delta_quantity)} ${line.unit}`).join('，');
}
</script>

<template>
  <div class="dashboard dashboard-overview" :aria-busy="loading">
    <section class="member-balances fantasy_guide_div_1" aria-labelledby="member-balances-heading">
      <div class="overview-heading">
        <h2 id="member-balances-heading">成员往来待结清</h2>
        <NButton class="overview-link" type="primary" size="small" @click="emit('navigate', 'settlements')">查看私账结算</NButton>
      </div>
      <p class="member-balances-note">{{ unsettledAccounts.length ? `${unsettledAccounts.length} 个私账余额未结清` : "目前没有未结清的私账余额" }}</p>
      <div class="member-balances-summary">
        <div><span>成员应交回</span><strong>¥ {{ money(memberReceivable) }}</strong></div>
        <div><span>社团应偿还</span><strong>¥ {{ money(memberPayable) }}</strong></div>
      </div>

    </section>
    <template v-if="data">
      <div class="overview-caption">
        <small>近 7 天按实际入账统计</small>
        <small :title="fullDate(data.snapshot_at)">{{ loading ? '正在更新…' : `更新于 ${dateTime(data.snapshot_at)}` }}</small>
      </div>

      <section class="overview-panel fantasy_guide_div_1" aria-labelledby="funds-heading">
        <div class="overview-heading">
          <h2 id="funds-heading">公账资金</h2>
          <NButton class="overview-link" type="primary" size="small" @click="emit('navigate', 'accounts')">查看账户</NButton>
        </div>
        <div class="fund-balance"><span class="currency">¥</span><strong>{{ money(data.funds.total_minor) }}</strong></div>
        <p class="overview-note">全部公账的当前账面余额</p>
        <div class="week-summary" :title="`${fullDate(data.window_start)} 至 ${fullDate(data.snapshot_at)}`">
          <div><small>近 7 天净变化</small><strong :class="tone(data.funds.net_minor)">{{ signedMoney(data.funds.net_minor) }}<small> 元</small></strong></div>
          <div><small>流入</small><strong>{{ money(data.funds.incoming_minor) }}<small> 元</small></strong></div>
          <div><small>流出</small><strong>{{ money(data.funds.outgoing_minor) }}<small> 元</small></strong></div>
        </div>
        <div class="changes-heading"><h3>最近余额变化</h3><small>按实际入账时间</small></div>
        <ul v-if="data.funds.recent.length" class="change-list">
          <li v-for="item in data.funds.recent" :key="item.code">
            <time :datetime="item.posted_at ?? undefined" :title="item.posted_at ? fullDate(item.posted_at) : '入账时间未记录'">{{ shortDate(item.posted_at) }}</time>
            <p class="change-description" :title="`${item.description || '资金转移'}；${item.source_account_name} → ${item.destination_account_name}`">{{ item.description || (item.reversal_of_code ? '资金冲销' : '资金转移') }}</p>
            <strong class="change-value" :class="tone(item.delta_minor)">{{ signedMoney(item.delta_minor) }} 元</strong>
          </li>
        </ul>
        <p v-else class="overview-empty">暂无已入账的公账余额变化</p>
      </section>

      <section class="overview-panel fantasy_guide_div_1" aria-labelledby="stock-heading">
        <div class="overview-heading">
          <div class="stock-heading"><h2 id="stock-heading">社团库存</h2><small>{{ stockedKinds }} 种有库存</small></div>
          <NButton class="overview-link" type="primary" size="small" @click="emit('navigate', 'inventory')">查看库存</NButton>
        </div>
        <p class="overview-note">最近变动的 {{ featuredSkus.length }} 种，含社团仓库与成员代管</p>
        <div v-if="featuredSkus.length" class="stock-totals" aria-label="最近变动货物的当前库存与近七天变化">
          <table class="stock-summary-table">
            <thead><tr><th>货物</th><th class="numeric">当前数量</th><th class="numeric">近 7 天净变化</th></tr></thead>
            <tbody>
              <tr v-for="sku in featuredSkus" :key="sku.sku_code">
                <td><div class="sku-name"><AccountAvatar :name="sku.sku_name" :url="sku.avatar_url" /><span>{{ sku.sku_code }} {{ sku.sku_name }}</span></div></td>
                <td class="numeric"><strong>{{ sku.quantity }}</strong> {{ sku.unit }}</td>
                <td class="numeric" :title="`近 7 天入库 ${sku.incoming_quantity} ${sku.unit}，出库 ${sku.outgoing_quantity} ${sku.unit}`"><strong :class="tone(sku.net_quantity)">{{ signedQuantity(sku.net_quantity) }} {{ sku.unit }}</strong></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="overview-empty stock-empty">暂无已入账的社团库存</p>
        <div class="changes-heading"><h3>最近库存变化</h3><small>内部调拨不计增减</small></div>
        <ul v-if="data.stock.recent.length" class="change-list">
          <li v-for="item in data.stock.recent" :key="item.code">
            <time :datetime="item.posted_at" :title="fullDate(item.posted_at)">{{ shortDate(item.posted_at) }}</time>
            <p class="change-description" :title="`${item.description || '货物转移'}；${item.source_account_name} → ${item.destination_account_name}`">{{ item.description || '货物转移' }}</p>
            <div class="change-value stock-change-value" :title="stockChangeText(item)">
              <strong v-for="line in item.lines" :key="line.sku_code" :class="tone(line.delta_quantity)">{{ line.sku_code }} {{ line.sku_name }} {{ signedQuantity(line.delta_quantity) }} {{ line.unit }}</strong>
            </div>
          </li>
        </ul>
        <p v-else class="overview-empty">暂无已入账的社团库存变化</p>
      </section>

      <section class="dashboard-pending" aria-label="待办事项">
        <span class="pending-label">{{ trusted ? '待办事项' : '记录状态' }}</span>
        <button @click="emit('navigate', trusted ? 'approvals' : 'transfers', 'funds', trusted ? undefined : 'pending')">资金待审批 <strong>{{ data.counts.pendingFunds }}</strong><span> 笔</span></button>
        <button v-if="trusted" @click="emit('navigate', 'approvals', 'stock')">货物待审批 <strong>{{ data.counts.pendingStock }}</strong><span> 笔</span></button>
        <button @click="emit('navigate', 'stock', undefined, 'in_transit')">货物待完成 <strong>{{ data.counts.inTransit }}</strong><span> 笔</span></button>
      </section>

      <section class="home-records fantasy_guide_div_1" aria-labelledby="operations-heading">
        <div class="overview-heading records-heading">
          <div><h2 id="operations-heading">最近转移记录</h2><p class="overview-note">最近创建的 10 笔，包含尚未入账的操作</p></div>
          <div class="operation-filters" role="group" aria-label="转移类型">
            <button v-for="item in filters" :key="item.value" :aria-pressed="filter === item.value" :class="{ selected: filter === item.value }" @click="filter = item.value">{{ item.label }}</button>
          </div>
        </div>
        <div v-if="operations.length" class="table-wrap">
          <table class="operations-table">
            <thead><tr><th>创建时间</th><th>类型与说明</th><th>来源 → 去向</th><th class="numeric">金额 / 货物</th><th>状态</th><th>操作人</th></tr></thead>
            <tbody>
              <tr v-for="item in operations" :key="`${item.kind}-${item.code}`">
                <td class="operation-date" :title="`创建于 ${fullDate(item.created_at)}；业务日期 ${item.effective_date}`">{{ dateTime(item.created_at) }}</td>
                <td class="operation-description"><small>{{ item.kind === 'funds' ? (item.reversal_of_code ? '资金冲销' : '资金转移') : '货物转移' }}</small><p>{{ item.description || '未填写说明' }}</p></td>
                <td class="operation-route"><AccountRoute :accounts="[]" source-id="" destination-id="" :source-name="item.source_account_name" :destination-name="item.destination_account_name" /></td>
                <td class="numeric operation-amount">
                  <strong v-if="item.kind === 'funds'">¥ {{ money(item.amount_minor) }}</strong>
                  <template v-else><p v-for="line in item.lines" :key="line.sku_code">{{ line.sku_code }} {{ line.sku_name }} <strong>{{ line.quantity }} {{ line.unit }}</strong></p></template>
                </td>
                <td><span class="status-pill" :class="`status-${item.status}`">{{ (item.kind === 'funds' ? statuses : stockStatuses)[item.status] || item.status }}</span></td>
                <td>{{ item.actor_name }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="overview-empty operations-empty"><p>{{ filter === 'all' ? '暂无转移记录' : filter === 'funds' ? '暂无资金转移记录' : '暂无货物转移记录' }}</p><NButton @click="filter === 'stock' ? emit('createStock') : emit('create')">{{ filter === 'stock' ? '登记货物' : '登记资金' }}</NButton></div>
        <div class="records-footer"><small>近 7 天变化按实际入账统计，内部转移不改变合计。</small><div><NButton class="plain-button" text @click="emit('navigate', 'transfers')">全部资金流水</NButton><NButton class="plain-button" text @click="emit('navigate', 'stock')">全部货物转移</NButton></div></div>
      </section>
    </template>
    <div v-else class="dashboard-placeholder" role="status">{{ loading ? '正在读取资金与库存…' : '首页数据尚未加载，请点击页面上方的刷新。' }}</div>
  </div>
</template>

<style scoped src="../styles/dashboard.css"></style>
