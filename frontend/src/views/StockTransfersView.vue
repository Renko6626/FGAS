<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { NButton } from "naive-ui";
import type { StockAccount, Account } from "../api/accounts";
import type { Sku } from "../api/warehouse";
import { warehouse, type StockTransfer } from "../api/warehouse";
import StockTransferFilters from "../components/StockTransferFilters.vue";
import StockTransferRecords from "../components/StockTransferRecords.vue";
import PaginationBar from "../components/PaginationBar.vue";
import { emptyStockFilters, transferDateError } from "../composables/transferFilters";
const props = defineProps<{
  locations: StockAccount[];
  trusted: boolean;
  skus: Sku[];
  accounts: Account[];
  approvals?: boolean;
  revision?: number;
  targetCode?: string;
  initialStatus?: string;
}>();
const emit = defineEmits<{
  changed: [];
  create: [];
}>();
const records = ref<InstanceType<typeof StockTransferRecords> | null>(null);
const items = ref<StockTransfer[]>([]);
const filters = ref({ ...emptyStockFilters(), status: props.initialStatus || (props.approvals ? null : "in_transit") });
const page = ref(1);
const limit = ref(20);
const total = ref(0);
const loading = ref(false);
const error = ref("");
let filterTimer: number | undefined;
async function load() {
  if (transferDateError(filters.value)) return;
  loading.value = true;
  try {
    const { search, status, tag, skuCode, dateFrom, dateTo } = filters.value;
    const result = await warehouse.transfers({
      page: page.value,
      limit: limit.value,
      ...(props.approvals ? { attention: true } : { status: status || undefined }),
      tag: tag || undefined,
      sku_code: skuCode || undefined,
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
  <div v-if="approvals" class="toolbar">
    <h2>货物待处理</h2>
    <NButton :disabled="records?.busy" @click="emit('changed')">刷新</NButton>
  </div>
  <StockTransferFilters v-model="filters" :approvals="approvals" :count="total" :trusted="trusted" @create="emit('create')" />
  <StockTransferRecords :target-code="targetCode" ref="records" :items="items" :locations="locations" :trusted="trusted" :skus="skus" :accounts="accounts"
    :approvals="approvals" :loading="loading" :error="error" @changed="emit('changed')" />
  <PaginationBar :page="page" :limit="limit" :total="total" @update:page="page = $event" @update:limit="limit = $event" />
</template>
