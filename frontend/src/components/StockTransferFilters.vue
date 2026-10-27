<script setup lang="ts">
import { computed, ref } from "vue";
import { NButton, NInput, NSelect } from "naive-ui";
import StatusHint from "./StatusHint.vue";
import { emptyStockFilters, transferDateError, type StockFilters } from "../composables/transferFilters";
const props = defineProps<{ approvals?: boolean; count: number; trusted: boolean; hideCreate?: boolean }>();
const emit = defineEmits<{ create: [] }>();
const filters = defineModel<StockFilters>({ required: true });
const showFilters = ref(false);
const hasFilters = computed(() => !!(filters.value.search || filters.value.status || filters.value.tag || filters.value.skuCode || filters.value.dateFrom || filters.value.dateTo));
const dateError = computed(() => transferDateError(filters.value));
const primaryStatuses = [
  { value: null, label: "全部记录", help: "" },
  { value: "pending", label: "待审批", help: "转移计划尚未获批，库存不变。批准后进入“待完成”。" },
  { value: "in_transit", label: "待完成", help: "转移已获批，尚未确认整笔完成，库存仍未变化。普通成员可报告已完成；受信任用户或管理员可直接确认完成。有人报告完成时，主单仍为待完成。" },
  { value: "completed", label: "已完成", help: "整笔转移已确认完成，库存已按单据中的全部货物数量更新。" },
];
const otherStatuses = [{ value: "rejected", label: "已拒绝" }, { value: "cancelled", label: "已取消" }];
</script>
<template>
  <div class="ledger-controls">
    <div v-if="!approvals" class="status-tabs" role="group" aria-label="货物状态筛选">
      <div v-for="item in primaryStatuses" :key="item.value || 'all'" class="status-option" :class="{ active: filters.status === item.value, attention: item.value === 'pending' }">
        <button class="status-choice" :aria-pressed="filters.status === item.value" @click="filters.status = item.value">{{ item.label }}</button>
        <StatusHint v-if="item.help" :label="item.label" :text="item.help" />
      </div>
    </div>
  </div>
  <div class="ledger-toolbar">
    <NInput v-model:value="filters.search" clearable placeholder="搜索说明、货物、编号或来源去向" :input-props="{ 'aria-label': '搜索货物转移' }" />
    <span class="ledger-order">按登记时间倒序</span>
    <NButton size="small" :aria-expanded="showFilters" @click="showFilters = !showFilters">{{ showFilters ? '收起筛选' : '筛选' }}</NButton>
    <NButton v-if="!approvals && !hideCreate" class="ledger-create" size="small" type="primary" @click="emit('create')">{{ trusted ? '登记转移' : '申请转移' }}</NButton>
  </div>
  <div v-if="showFilters" class="ledger-filters">
    <label v-if="!approvals">其他状态<NSelect :value="otherStatuses.some(item => item.value === filters.status) ? filters.status : null" :options="otherStatuses" clearable placeholder="拒绝或取消记录" @update:value="filters.status = $event" /></label>
    <label>商品代号<NInput v-model:value="filters.skuCode" clearable placeholder="输入完整 SKU" /></label>
    <label>标签<NInput v-model:value="filters.tag" clearable placeholder="输入完整标签" /></label>
    <label>业务日期起<input v-model="filters.dateFrom" type="date" /></label>
    <label>业务日期止<input v-model="filters.dateTo" type="date" /></label>
  </div>
  <div class="ledger-count"><span>{{ count }} 笔{{ approvals ? '待处理转移' : '记录' }}</span><NButton v-if="hasFilters" size="tiny" text @click="filters = emptyStockFilters()">清空筛选</NButton></div>
  <p v-if="dateError" class="error" role="alert">开始日期不能晚于结束日期。</p>
</template>
<style scoped src="../styles/ledger-filters.css"></style>
