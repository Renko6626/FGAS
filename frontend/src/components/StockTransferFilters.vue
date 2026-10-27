<script setup lang="ts">
import { computed, ref } from "vue";
import { NButton, NInput } from "naive-ui";
import type { Sku, StockTransfer } from "../api/warehouse";
import { stockStatuses } from "../presentation/warehouse";
import { emptyStockFilters, type StockFilters } from "../composables/transferFilters";
const props = defineProps<{ approvals?: boolean; count?: number; items?: StockTransfer[]; skus?: Sku[] }>();
const filters = defineModel<StockFilters>({ required: true });
const showFilters = ref(false);
const hasFilters = computed(() => !!(filters.value.search || filters.value.status || filters.value.tag || filters.value.skuCode));
</script>
<template>
  <div v-if="!approvals" class="status-tabs" aria-label="货物状态筛选">
    <button :class="{ active: !filters.status }" :aria-pressed="!filters.status" @click="filters.status = null">全部</button>
    <button v-for="(label, value) in stockStatuses" :key="value" :class="{ active: filters.status === value }" :aria-pressed="filters.status === value" @click="filters.status = value">{{ label }}</button>
  </div>
  <div class="ledger-toolbar">
    <NInput v-model:value="filters.search" clearable placeholder="搜索用途、货物、来源或去向" :input-props="{ 'aria-label': '搜索货物转移' }" />
    <NButton :aria-expanded="showFilters" @click="showFilters = !showFilters">{{ showFilters ? '收起筛选' : '更多筛选' }}</NButton>
  </div>
  <div v-if="showFilters" class="ledger-filters stock-extra-filters">
    <label>商品代号<NInput v-model:value="filters.skuCode" clearable placeholder="输入完整 SKU" /></label>
    <label>标签<NInput v-model:value="filters.tag" clearable placeholder="输入完整标签" /></label>
  </div>
  <div class="ledger-count"><span>{{ count ?? props.items?.length ?? 0 }} 笔{{ approvals ? '待处理' : '货物转移' }}</span><NButton v-if="hasFilters" text @click="filters = emptyStockFilters()">清空筛选</NButton></div>
</template>
<style scoped src="../styles/ledger-filters.css"></style>
