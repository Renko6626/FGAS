<script setup lang="ts">
import { computed } from "vue";
import { NButton } from "naive-ui";
import { money, statuses, type Account, type Transfer } from "../api/funds";
import AccountRoute from "../components/AccountRoute.vue";
import type { StockTransfer } from "../api/warehouse";

const props = defineProps<{
  accounts: Account[];
  transfers: Transfer[];
  stock: StockTransfer[];
  total: number;
  trusted: boolean;
}>();
const emit = defineEmits<{
  navigate: [string, ("funds" | "stock")?];
  create: [];
  createStock: [];
}>();
const pendingFunds = computed(
  () => props.transfers.filter((t) => t.status === "pending").length,
);
const pendingStock = computed(
  () =>
    props.stock.filter(
      (t) =>
        t.status === "pending" ||
        t.confirmations.some((c) => c.status === "pending"),
    ).length,
);
const inTransit = computed(
  () => props.stock.filter((t) => t.status === "in_transit").length,
);
const recent = computed(() =>
  [...props.transfers]
    .sort((a, b) => b.effective_date.localeCompare(a.effective_date))
    .slice(0, 6),
);
</script>

<template>
  <div class="dashboard">
    <section class="fund-overview fantasy_guide_div_1">
      <div class="fund-overview-title">
        <h2>公账余额</h2>
        <NButton class="plain-button" text @click="emit('navigate', 'accounts')"
          >查看账户</NButton
        >
      </div>
      <strong class="fund-total">¥ {{ money(total) }}</strong>
      <hr />
      <div class="home-actions">
        <NButton @click="emit('create')">登记资金</NButton
        ><NButton @click="emit('createStock')">登记货物</NButton
        ><NButton @click="emit('navigate', 'settlements')">私账结算</NButton>
      </div>
    </section>
    <section class="home-pending fantasy_guide_div_1">
      <h2>{{ trusted ? "待办事项" : "记录状态" }}</h2>
      <hr />
      <button
        class="pending-row"
        @click="emit('navigate', trusted ? 'approvals' : 'transfers', 'funds')"
      >
        <span>资金待审批</span><strong>{{ pendingFunds }} 笔</strong>
      </button>
      <button
        v-if="trusted"
        class="pending-row"
        @click="emit('navigate', 'approvals', 'stock')"
      >
        <span>货物待审批</span><strong>{{ pendingStock }} 笔</strong>
      </button>
      <button class="pending-row" @click="emit('navigate', 'stock')">
        <span>货物待完成</span><strong>{{ inTransit }} 笔</strong>
      </button>
    </section>
    <section class="home-records fantasy_guide_div_1">
      <div class="toolbar">
        <h2>近期资金流水</h2>
        <NButton
          class="plain-button"
          text
          @click="emit('navigate', 'transfers')"
          >全部流水</NButton
        >
      </div>
      <hr />
      <div v-if="recent.length" class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>业务日期</th>
              <th>来源 → 去向</th>
              <th class="numeric">金额（元）</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in recent" :key="item.id">
              <td>{{ item.effective_date }}</td>
              <td>
                <AccountRoute
                  :accounts="accounts"
                  :source-id="item.source_account_id"
                  :destination-id="item.destination_account_id"
                  :source-name="item.source_account_name"
                  :destination-name="item.destination_account_name"
                />
              </td>
              <td class="numeric">{{ money(item.amount_minor) }}</td>
              <td>
                <span class="status-pill" :class="`status-${item.status}`">{{
                  statuses[item.status] || item.status
                }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="empty-state">
        <p>暂无资金流水</p>
        <NButton @click="emit('create')">登记资金</NButton>
      </div>
    </section>
  </div>
</template>
