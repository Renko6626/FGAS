<script setup lang="ts">
import { computed, ref } from "vue";
import { NButton, NInput, NSelect } from "naive-ui";
import type { Transfer } from "../api/funds";
import StatusHint from "./StatusHint.vue";
import { emptyFundFilters, hasFundFilters, transferDateError, type FundFilters } from "../composables/transferFilters";
const props = defineProps<{ items: Transfer[]; approvals: boolean; count: number; hideCreate?: boolean }>();
const emit = defineEmits<{ create: [] }>();
const filters = defineModel<FundFilters>({ required: true });
const showFilters = ref(false);
const hasFilters = computed(() => hasFundFilters(filters.value));
const dateError = computed(() => transferDateError(filters.value));
const primaryStatuses = [
  { value: null, label: "全部记录", help: "" },
  { value: "pending", label: "待审批", help: "这笔资金申请尚未批准，不影响余额。批准后正式入账。" },
  { value: "posted", label: "已过账", help: "资金已正式入账。错误通过冲销和更正处理，保留原记录。" },
];
const otherStatuses = [{ value: "rejected", label: "已拒绝" }, { value: "reversed", label: "已冲销" }];
const sortOptions = [{ value: "created_at", label: "登记时间：新到旧" }, { value: "effective_date", label: "业务日期：新到旧" }];
</script>
<template>
  <div class="ledger-controls">
    <div v-if="!approvals" class="status-tabs" role="group" aria-label="资金状态筛选">
      <div v-for="item in primaryStatuses" :key="item.value || 'all'" class="status-option" :class="{ active: filters.status === item.value, attention: item.value === 'pending' }">
        <button class="status-choice" :aria-pressed="filters.status === item.value" @click="filters.status = item.value">{{ item.label }}</button>
        <StatusHint v-if="item.help" :label="item.label" :text="item.help" />
      </div>
    </div>
  </div>
  <div class="ledger-toolbar">
    <NInput v-model:value="filters.search" clearable placeholder="搜索说明、账户、编号或发起人" :input-props="{ 'aria-label': '搜索资金流水' }" />
    <NSelect v-model:value="filters.sort" size="small" :options="sortOptions" class="ledger-sort" aria-label="资金流水排序" />
    <NButton size="small" :aria-expanded="showFilters" @click="showFilters = !showFilters">{{ showFilters ? '收起筛选' : '筛选' }}</NButton>
    <NButton v-if="!approvals && !hideCreate" class="ledger-create" size="small" type="primary" @click="emit('create')">登记资金</NButton>
  </div>
  <div v-if="showFilters" class="ledger-filters">
    <label v-if="!approvals">其他状态<NSelect :value="otherStatuses.some(item => item.value === filters.status) ? filters.status : null" :options="otherStatuses" clearable placeholder="拒绝或冲销记录" @update:value="filters.status = $event" /></label>
    <label>标签<NInput v-model:value="filters.tag" clearable placeholder="输入完整标签" /></label>
    <label>业务日期起<input v-model="filters.dateFrom" type="date" /></label>
    <label>业务日期止<input v-model="filters.dateTo" type="date" /></label>
  </div>
  <div class="ledger-count"><span>{{ count }} 笔{{ approvals ? '待审批申请' : '记录' }}</span><NButton v-if="hasFilters" size="tiny" text @click="filters = emptyFundFilters()">清空筛选</NButton></div>
  <p v-if="dateError" class="error" role="alert">开始日期不能晚于结束日期。</p>
</template>
<style scoped src="../styles/ledger-filters.css"></style>
