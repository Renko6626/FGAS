<script setup lang="ts">
import { computed, ref } from "vue";
import { NButton } from "naive-ui";
import type { Account, StockAccount } from "../api/accounts";
import type { Sku } from "../api/warehouse";
import type { StockTransfer } from "../api/warehouse";
import StockTransferFilters from "./StockTransferFilters.vue";
import StockTransferRecords from "./StockTransferRecords.vue";
import { emptyStockFilters, filterStockTransfers } from "../composables/transferFilters";
const props = defineProps<{
  items: StockTransfer[];
  accounts: Account[];
  locations: StockAccount[];
  skus: Sku[];
  trusted: boolean;
}>();
const emit = defineEmits<{
  changed: [];
}>();
const recordList = ref<InstanceType<typeof StockTransferRecords> | null>(null);
const filters = ref(emptyStockFilters());
const records = computed(() => filterStockTransfers(props.items, filters.value));
</script>

<template>
  <div class="toolbar"><h2>货物转移记录</h2><NButton :disabled="recordList?.busy" @click="emit('changed')">刷新</NButton></div>
  <StockTransferFilters v-model="filters" :count="records.length" :trusted="trusted" hide-create />
  <StockTransferRecords ref="recordList" :items="records" :locations="locations" :trusted="trusted" :skus="skus" :accounts="accounts" @changed="emit('changed')" />
</template>
