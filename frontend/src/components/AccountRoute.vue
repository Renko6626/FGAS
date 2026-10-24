<script setup lang="ts">
import { computed } from "vue";
import type { AccountBase } from "../api/accounts";
import AccountLabel from "./AccountLabel.vue";
const props = defineProps<{
  accounts: AccountBase[];
  sourceId: string;
  destinationId: string;
  sourceName?: string;
  destinationName?: string;
}>();
const source = computed(() =>
  props.accounts.find((a) => a.id === props.sourceId),
);
const destination = computed(() =>
  props.accounts.find((a) => a.id === props.destinationId),
);
</script>

<template>
  <span class="account-route"
    ><AccountLabel
      :name="sourceName || source?.name || sourceId"
      :url="source?.avatar_url" /><span
      class="account-route-arrow"
      aria-label="转向"
      >→</span
    ><AccountLabel
      :name="destinationName || destination?.name || destinationId"
      :url="destination?.avatar_url"
  /></span>
</template>

<style scoped>
.account-route {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  vertical-align: middle;
  max-width: 100%;
}
.account-route-arrow {
  color: #666;
  flex-shrink: 0;
}
</style>
