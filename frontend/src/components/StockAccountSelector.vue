<script setup lang="ts">
import type { StockAccount } from "../api/accounts";
import EndpointSelector from './EndpointSelector.vue'
defineProps<{locations:StockAccount[];modelValue:string;label:string;disabled?:boolean}>()
const emit=defineEmits<{'update:modelValue':[string]}>()
</script>
<template><EndpointSelector :accounts="locations" :model-value="modelValue" :label="label" :disabled="disabled" @update:model-value="emit('update:modelValue',$event)"/></template>
