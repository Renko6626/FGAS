<script setup lang="ts">
import { computed, ref } from "vue";
import type { Account } from "../api/accounts";
import type { Transfer } from "../api/funds";
import TransferFilters from "./TransferFilters.vue";
import TransferRecords from "./TransferRecords.vue";
import { emptyFundFilters, filterFundTransfers, hasFundFilters } from "../composables/transferFilters";
const props = defineProps<{
  items: Transfer[];
  accounts: Account[];
  trusted: boolean;
}>();
const emit = defineEmits<{
  changed: [];
  notice: [string];
}>();
const filters = ref(emptyFundFilters());
const records = computed(() => filterFundTransfers(props.items, filters.value));
const hasFilters = computed(() => hasFundFilters(filters.value));
</script>

<template>
  <TransferFilters v-model="filters" :items="items" :approvals="false" :count="records.length" hide-create />
  <TransferRecords :items="records" :accounts="accounts" :trusted="trusted" :approvals="false" hide-create
    :has-filters="hasFilters" @changed="emit('changed')" @notice="emit('notice', $event)" @reset="filters = emptyFundFilters()" />
</template>
