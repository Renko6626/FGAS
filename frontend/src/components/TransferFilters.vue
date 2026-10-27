<script setup lang="ts">
import { computed, ref } from "vue";
import { NButton, NInput } from "naive-ui";
import { type Transfer } from "../api/funds";
import { statuses } from "../presentation/funds";
import { emptyFundFilters, hasFundFilters, fundDateError, type FundFilters } from "../composables/transferFilters";
const props = defineProps<{ items: Transfer[]; approvals: boolean; count: number }>();
const filters = defineModel<FundFilters>({ required: true });
const showFilters = ref(false);
const hasFilters = computed(() => hasFundFilters(filters.value));
const dateError = computed(() => fundDateError(filters.value));
</script>
<template>
  <div v-if="!approvals" class="status-tabs" aria-label="资金状态筛选">
    <button :class="{ active: !filters.status }" :aria-pressed="!filters.status" @click="filters.status = null">全部</button>
    <button v-for="(label, value) in statuses" :key="value" :class="{ active: filters.status === value }" :aria-pressed="filters.status === value" @click="filters.status = value">{{ label }}</button>
  </div>
  <div class="ledger-toolbar">
    <NInput v-model:value="filters.search" clearable placeholder="搜索账户、说明或发起人" :input-props="{ 'aria-label': '搜索资金流水' }" />
    <NButton :aria-expanded="showFilters" @click="showFilters = !showFilters">{{ showFilters ? '收起筛选' : '更多筛选' }}</NButton>
  </div>
  <div v-if="showFilters" class="ledger-filters">
    <label>标签<NInput v-model:value="filters.tag" clearable placeholder="输入完整标签" /></label>
    <label>业务日期起<input v-model="filters.dateFrom" type="date" /></label>
    <label>业务日期止<input v-model="filters.dateTo" type="date" /></label>
  </div>
  <div class="ledger-count"><span>{{ count }} 笔{{ approvals ? '待审批' : '流水' }}</span><NButton v-if="hasFilters" text @click="filters = emptyFundFilters()">清空筛选</NButton></div>
  <p v-if="dateError" class="error" role="alert">开始日期不能晚于结束日期。</p>
</template>
<style scoped src="../styles/ledger-filters.css"></style>
