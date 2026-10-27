<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { fundsApi, type Transfer } from "../api/funds";
import { type Account } from "../api/accounts";
import TransferFilters from "../components/TransferFilters.vue";
import TransferRecords from "../components/TransferRecords.vue";
import PaginationBar from "../components/PaginationBar.vue";
import { emptyFundFilters, fundDateError, hasFundFilters } from "../composables/transferFilters";
const props = defineProps<{
  accounts: Account[];
  approvals: boolean;
  trusted: boolean;
  hideCreate?: boolean;
  revision?: number;
  targetCode?: string;
  initialStatus?: string;
}>();
const emit = defineEmits<{
  changed: [];
  notice: [string];
  create: [];
}>();
const items = ref<Transfer[]>([]);
const filters = ref({ ...emptyFundFilters(), status: props.initialStatus || null });
const page = ref(1);
const limit = ref(20);
const total = ref(0);
const loading = ref(false);
const error = ref("");
const hasFilters = computed(() => hasFundFilters(filters.value));
let filterTimer: number | undefined;
async function load() {
  if (fundDateError(filters.value))
    return;
  loading.value = true;
  try {
    const { search, status, tag, dateFrom, dateTo } = filters.value;
    const result = await fundsApi.transfers({
      page: page.value,
      limit: limit.value,
      status: props.approvals ? "pending" : status || undefined,
      tag: tag || undefined,
      q: search.trim() || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    });
    items.value = result.items;
    total.value = result.total;
    error.value = "";
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    loading.value = false;
  }
}
watch(filters, () => {
  const wasFirst = page.value === 1;
  page.value = 1;
  if (wasFirst) {
    window.clearTimeout(filterTimer);
    filterTimer = window.setTimeout(load, 250);
  }
}, { deep: true });
watch(page, load);
watch(limit, () => {
  window.clearTimeout(filterTimer);
  if (page.value === 1)
    load();
  else
    page.value = 1;
});
watch(() => props.revision, load);
onMounted(load);
onBeforeUnmount(() => window.clearTimeout(filterTimer));
</script>

<template>
  <TransferFilters v-model="filters" :items="items" :approvals="approvals" :count="total" />
  <TransferRecords :target-code="targetCode" :items="items" :accounts="accounts" :approvals="approvals" :trusted="trusted"
    :hide-create="hideCreate" :has-filters="hasFilters" :loading="loading" :error="error"
    @changed="emit('changed')" @notice="emit('notice', $event)" @create="emit('create')" @reset="filters = emptyFundFilters()" />
  <PaginationBar :page="page" :limit="limit" :total="total" @update:page="page = $event" @update:limit="limit = $event" />
</template>
