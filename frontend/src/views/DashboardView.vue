<script setup lang="ts">
import { computed, defineAsyncComponent, ref } from 'vue';
import { NButton } from 'naive-ui';
import { money } from '../presentation/funds';
import { dashboardRecord, type TransferRecordRow } from '../presentation/records';
import type { Dashboard } from '../api/dashboard';
import type { Account } from '../api/accounts';
import AccountAvatar from '../components/AccountAvatar.vue';
import TransferRecordList from '../components/TransferRecordList.vue';
const SharedHandbook = defineAsyncComponent(() => import('../components/SharedHandbook.vue'));

const props = defineProps<{ data: Dashboard | null; accounts: Account[]; loading: boolean; trusted: boolean; revision: number }>();
const emit = defineEmits<{
  navigate: [string, ('funds' | 'stock')?, string?];
  create: [];
  createStock: [];
}>();
const filter = ref<'all' | 'funds' | 'stock'>('all');
const filters = [{ value: 'all', label: '全部' }, { value: 'funds', label: '资金' }, { value: 'stock', label: '货物' }] as const;
const operations = computed(() => (props.data?.operations[filter.value] ?? []).map(dashboardRecord));
const stockedKinds = computed(() => props.data?.stock.skus.filter(row => BigInt(row.quantity) > 0n).length ?? 0);
const featuredSkus = computed(() => props.data?.stock.skus.slice(0, 4) ?? []);
const publicAccounts = computed(() => props.accounts.filter(account => account.kind === 'public').slice(0, 3));
const unsettledAccounts = computed(() => props.accounts.filter(account => account.kind === 'private' && account.balance_minor !== 0));
const memberReceivable = computed(() => unsettledAccounts.value.reduce((total, account) => total + Math.max(account.balance_minor, 0), 0));
const memberPayable = computed(() => unsettledAccounts.value.reduce((total, account) => total + Math.max(-account.balance_minor, 0), 0));
function signedMoney(value: number) { return `${value > 0 ? '+' : ''}${money(value)}`; }
function signedQuantity(value: string) { return `${BigInt(value) > 0n ? '+' : ''}${value}`; }
function tone(value: string | number) { return BigInt(value) > 0n ? 'increase' : BigInt(value) < 0n ? 'decrease' : 'unchanged'; }
function dateTime(value: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }) : '入账时间未记录';
}
function fullDate(value: string) { return new Date(value).toLocaleString('zh-CN', { hour12: false }); }
function shortDate(value: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }) : '—';
}
function stockChangeText(item: Dashboard['stock']['recent'][number]) {
  return item.lines.map(line => `${line.sku_code} ${line.sku_name} ${signedQuantity(line.delta_quantity)} ${line.unit}`).join('，');
}
function openOperation(row: TransferRecordRow) {
  window.location.hash = `${row.kind === 'funds' ? 'transfers' : 'stock'}?code=${encodeURIComponent(row.code)}`;
}
</script>

<template>
  <div class="dashboard dashboard-overview" :aria-busy="loading">
    <SharedHandbook :trusted="trusted" :revision="revision" />
    <template v-if="data">
      <section class="dashboard-pending" :aria-label="trusted ? '待办处理' : '记录进度'">
        <button class="pending-task" :class="{ 'has-items': data.counts.pendingFunds > 0 }" :title="trusted ? '批准后正式入账' : '等待审批后入账'" @click="emit('navigate', trusted ? 'approvals' : 'transfers', 'funds', trusted ? undefined : 'pending')">
          <span>资金待审批</span><strong>{{ data.counts.pendingFunds }}</strong><span class="task-chevron" aria-hidden="true">›</span>
        </button>
        <button v-if="trusted" class="pending-task" :class="{ 'has-items': data.counts.pendingStock > 0 }" title="转移申请与完成报告" @click="emit('navigate', 'approvals', 'stock')">
          <span>货物待审核</span><strong>{{ data.counts.pendingStock }}</strong><span class="task-chevron" aria-hidden="true">›</span>
        </button>
        <button class="pending-task" :class="{ 'has-items': data.counts.inTransit > 0 }" :title="trusted ? '整笔确认后更新库存' : '货物全部到位后报告完成'" @click="emit('navigate', 'stock', undefined, 'in_transit')">
          <span>货物待完成</span><strong>{{ data.counts.inTransit }}</strong><span class="task-chevron" aria-hidden="true">›</span>
        </button>
      </section>
      <div class="overview-caption"><small>近 7 天按实际入账统计</small><small :title="fullDate(data.snapshot_at)">{{ loading ? '正在更新…' : `更新于 ${dateTime(data.snapshot_at)}` }}</small></div>

      <section class="overview-panel fantasy_guide_div_1" aria-labelledby="funds-heading">
        <div class="overview-heading"><h2 id="funds-heading">公账资金</h2><NButton text size="small" @click="emit('navigate', 'accounts')">查看账户</NButton></div>
        <div class="fund-balance"><span class="currency">¥</span><strong>{{ money(data.funds.total_minor) }}</strong></div>
        <p class="overview-note">全部公账的当前账面余额</p>
        <div class="week-summary" :title="`${fullDate(data.window_start)} 至 ${fullDate(data.snapshot_at)}`">
          <div><small>近 7 天流入</small><strong>{{ money(data.funds.incoming_minor) }}</strong></div>
          <div><small>近 7 天流出</small><strong>{{ money(data.funds.outgoing_minor) }}</strong></div>
          <div><small>近 7 天净变化</small><strong :class="tone(data.funds.net_minor)">{{ signedMoney(data.funds.net_minor) }}</strong></div>
        </div>
        <div class="public-accounts"><div v-for="account in publicAccounts" :key="account.code"><span>{{ account.name }}</span><strong>¥ {{ money(account.balance_minor) }}</strong></div></div>
        <details class="changes-disclosure"><summary>最近余额变化</summary>
          <ul v-if="data.funds.recent.length" class="change-list"><li v-for="item in data.funds.recent" :key="item.code">
            <time :datetime="item.posted_at ?? undefined" :title="item.posted_at ? fullDate(item.posted_at) : '入账时间未记录'">{{ shortDate(item.posted_at) }}</time>
            <p class="change-description" :title="`${item.description || '资金转移'}；${item.source_account_name} → ${item.destination_account_name}`">{{ item.description || (item.reversal_of_code ? '资金冲销' : '资金转移') }}</p>
            <strong class="change-value" :class="tone(item.delta_minor)">{{ signedMoney(item.delta_minor) }} 元</strong>
          </li></ul><p v-else class="overview-empty">暂无已入账的公账余额变化</p>
        </details>
      </section>

      <section class="overview-panel fantasy_guide_div_1" aria-labelledby="stock-heading">
        <div class="overview-heading"><div class="stock-heading"><h2 id="stock-heading">社团库存</h2><small>{{ stockedKinds }} 种有库存</small></div><NButton text size="small" @click="emit('navigate', 'inventory')">查看库存</NButton></div>
        <p class="overview-note">最近变动的 {{ featuredSkus.length }} 种，含社团仓库与成员代管</p>
        <div v-if="featuredSkus.length" class="stock-totals"><table class="stock-summary-table compact-table"><thead><tr><th>货物</th><th class="numeric">当前数量</th><th class="numeric">近 7 天净变化</th></tr></thead><tbody>
          <tr v-for="sku in featuredSkus" :key="sku.sku_code"><td><div class="sku-name"><AccountAvatar :name="sku.sku_name" :url="sku.avatar_url" /><span :title="sku.sku_code">{{ sku.sku_name }}</span></div></td><td class="numeric"><strong>{{ sku.quantity }}</strong> {{ sku.unit }}</td><td class="numeric" :title="`近 7 天入库 ${sku.incoming_quantity} ${sku.unit}，出库 ${sku.outgoing_quantity} ${sku.unit}`"><strong :class="tone(sku.net_quantity)">{{ signedQuantity(sku.net_quantity) }} {{ sku.unit }}</strong></td></tr>
        </tbody></table></div><p v-else class="overview-empty stock-empty">暂无已入账的社团库存</p>
        <details class="changes-disclosure"><summary>最近库存变化 <small>内部调拨不计增减</small></summary>
          <ul v-if="data.stock.recent.length" class="change-list"><li v-for="item in data.stock.recent" :key="item.code"><time :datetime="item.posted_at" :title="fullDate(item.posted_at)">{{ shortDate(item.posted_at) }}</time><p class="change-description" :title="`${item.description || '货物转移'}；${item.source_account_name} → ${item.destination_account_name}`">{{ item.description || '货物转移' }}</p><div class="change-value stock-change-value" :title="stockChangeText(item)"><strong v-for="line in item.lines" :key="line.sku_code" :class="tone(line.delta_quantity)">{{ line.sku_name }} {{ signedQuantity(line.delta_quantity) }} {{ line.unit }}</strong></div></li></ul><p v-else class="overview-empty">暂无已入账的社团库存变化</p>
        </details>
      </section>

      <section class="member-balances fantasy_guide_div_1" :class="{ attention: unsettledAccounts.length > 0 }" aria-labelledby="member-balances-heading">
        <h2 id="member-balances-heading">私账往来</h2>
        <div class="member-balances-summary"><div><span>成员应交回（净额）</span><strong>¥ {{ money(memberReceivable) }}</strong></div><div><span>社团应偿还（净额）</span><strong>¥ {{ money(memberPayable) }}</strong></div></div>
        <NButton text size="small" :title="`${unsettledAccounts.length} 个私账净余额非零；请核对逐笔结算记录`" @click="emit('navigate', 'settlements')">{{ trusted ? '核对并办理结算' : '核对私账记录' }}</NButton>
      </section>

      <section class="home-records fantasy_guide_div_1" aria-labelledby="operations-heading">
        <div class="overview-heading records-heading"><h2 id="operations-heading">最近转移记录 <small>最近创建的 10 笔，含未入账记录</small></h2><div class="operation-filters" role="group" aria-label="转移类型"><button v-for="item in filters" :key="item.value" :aria-pressed="filter === item.value" :class="{ selected: filter === item.value }" @click="filter = item.value">{{ item.label }}</button></div></div>
        <TransferRecordList v-if="operations.length" :rows="operations" :value-label="filter === 'funds' ? '金额' : filter === 'stock' ? '数量' : '金额 / 数量'" :loading="loading" @open="openOperation" />
        <div v-else class="overview-empty operations-empty"><p>{{ filter === 'all' ? '暂无转移记录' : filter === 'funds' ? '暂无资金转移记录' : '暂无货物转移记录' }}</p><NButton @click="filter === 'stock' ? emit('createStock') : emit('create')">{{ filter === 'stock' ? (trusted ? '登记转移' : '申请转移') : '登记资金' }}</NButton></div>
        <div class="records-footer"><small>近 7 天变化按实际入账统计，内部转移不改变合计。</small><div><NButton text size="small" @click="emit('navigate', 'transfers')">全部资金流水</NButton><NButton text size="small" @click="emit('navigate', 'stock')">全部货物转移</NButton></div></div>
      </section>
    </template>
    <div v-else class="dashboard-placeholder" role="status">{{ loading ? '正在读取资金与库存…' : '首页数据尚未加载，请通过工具菜单刷新。' }}</div>
  </div>
</template>

<style scoped src="../styles/dashboard.css"></style>
