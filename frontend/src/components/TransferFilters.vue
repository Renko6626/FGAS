<script setup lang="ts">
import { computed, ref } from "vue";
import { NButton, NInput, NSelect } from "naive-ui";
import { statuses, type Transfer } from "../api/funds";
import { emptyFundFilters, hasFundFilters, fundDateError, type FundFilters } from "../composables/transferFilters";
const props = defineProps<{
  items: Transfer[];
  approvals: boolean;
  count: number;
}>();
const filters = defineModel<FundFilters>({ required: true });
const showFilters = ref(false);
const tags = computed(() =>
  [...new Set(props.items.flatMap(t => t.tags))].map(value => ({ label: value, value })),
);
const hasFilters = computed(() => hasFundFilters(filters.value));
const dateError = computed(() => fundDateError(filters.value));
function resetFilters() { filters.value = emptyFundFilters(); }
</script>

<template>
  <div class="ledger-toolbar">
    <NInput
      v-model:value="filters.search"
      clearable
      placeholder="搜索账户、说明或发起人"
      :input-props="{ 'aria-label': '搜索资金流水' }"
    />
    <NSelect
      v-if="!approvals"
      v-model:value="filters.status"
      clearable
      placeholder="全部状态"
      :options="
        Object.entries(statuses).map(([value, label]) => ({ value, label }))
      "
    />
    <NButton :aria-expanded="showFilters" @click="showFilters = !showFilters">{{
      showFilters ? "收起筛选" : "更多筛选"
    }}</NButton>
  </div>
  <div v-if="showFilters" class="ledger-filters">
    <label
      >标签<NSelect
        v-model:value="filters.tag"
        clearable
        filterable
        tag
        placeholder="所有标签"
        :options="tags"
    /></label>
    <label>业务日期起<input v-model="filters.dateFrom" type="date" /></label
    ><label>业务日期止<input v-model="filters.dateTo" type="date" /></label>
  </div>
  <div class="ledger-count">
    <span>{{ count }} 笔{{ approvals ? "待审批" : "流水" }}</span
    ><NButton v-if="hasFilters" class="plain-button" text @click="resetFilters"
      >清空筛选</NButton
    >
  </div>
  <p v-if="dateError" class="error" role="alert">开始日期不能晚于结束日期。</p>
</template>

<style scoped>
.ledger-toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
}
.ledger-toolbar > .n-input {
  flex: 1;
  min-width: 180px;
}
.ledger-toolbar > .n-select {
  width: 150px;
  flex-shrink: 0;
}
.ledger-filters {
  display: grid;
  grid-template-columns: minmax(150px, 1fr) 180px 180px;
  gap: 16px;
  margin: 12px 0;
}
.ledger-filters input {
  width: 100%;
  height: 34px;
}
.ledger-count {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #666;
  margin: 20px 0 12px;
  font-size: 12px;
  min-height: 24px;
}
@media (max-width: 700px) {
  .ledger-toolbar { flex-wrap: wrap; }
  .ledger-toolbar > .n-input { flex-basis: 100%; }
  .ledger-toolbar > .n-select { flex: 1; }
  .ledger-filters { grid-template-columns: 1fr 1fr; }
  .ledger-filters > label:first-child { grid-column: 1 / -1; }
  .ledger-filters > label { min-width: 0; }
}
</style>
