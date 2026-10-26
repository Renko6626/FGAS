<script setup lang="ts">
import type { StockAccount } from "../api/accounts";
import EndpointSelector from './EndpointSelector.vue'
import { stockKinds } from '../presentation/accounts'
defineProps<{locations:StockAccount[];modelValue:string;label:string;disabled?:boolean}>()
const emit=defineEmits<{'update:modelValue':[string]}>()
</script>
<template><EndpointSelector :accounts="locations" :kind-labels="stockKinds" :model-value="modelValue" :label="label" :disabled="disabled" @update:model-value="emit('update:modelValue',$event)"/></template>
