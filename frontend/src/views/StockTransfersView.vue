<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { NButton } from "naive-ui";
import type { StockAccount, Account } from "../api/accounts";
import type { Sku } from "../api/warehouse";
import { warehouse, type StockTransfer } from "../api/warehouse";
import StockTransferFilters from "../components/StockTransferFilters.vue";
import StockTransferRecords from "../components/StockTransferRecords.vue";
import PaginationBar from "../components/PaginationBar.vue";
import { emptyStockFilters } from "../composables/transferFilters";
const props = defineProps<{
  locations: StockAccount[];
  trusted: boolean;
  skus: Sku[];
  accounts: Account[];
  approvals?: boolean;
  revision?: number;
  targetCode?: string;
}>();
const emit = defineEmits<{
  changed: [];
}>();
const records = ref<InstanceType<typeof StockTransferRecords> | null>(null);
const items = ref<StockTransfer[]>([]);
const filters = ref(emptyStockFilters());
const page = ref(1);
const limit = ref(20);
const total = ref(0);
const loading = ref(false);
const error = ref("");
let filterTimer: number | undefined;
async function load() {
  loading.value = true;
  try {
    const { search, status, tag, skuCode } = filters.value;
    const result = await warehouse.transfers({
      page: page.value,
      limit: limit.value,
      ...(props.approvals ? { attention: true } : { status: status || undefined }),
      tag: tag || undefined,
      sku_code: skuCode || undefined,
      q: search.trim() || undefined,
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
  <div class="toolbar">
    <h2>{{ approvals ? "货物审批与完成申报" : "货物转移记录" }}</h2>
    <NButton :disabled="records?.busy" @click="emit('changed')">刷新</NButton>
  </div>
  <StockTransferFilters v-model="filters" :items="items" :skus="skus" />
  <StockTransferRecords :target-code="targetCode" ref="records" :items="items" :locations="locations" :trusted="trusted" :skus="skus" :accounts="accounts"
    :approvals="approvals" :loading="loading" :error="error" @changed="emit('changed')" />
  <PaginationBar :page="page" :limit="limit" :total="total" @update:page="page = $event" @update:limit="limit = $event" />
</template>
