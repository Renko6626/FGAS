<script setup lang="ts">
import {computed} from 'vue'
import {NSelect} from 'naive-ui'
const props=defineProps<{modelValue:string[];disabled?:boolean}>()
const emit=defineEmits<{'update:modelValue':[string[]]}>()
const options=computed(()=>[...new Set(['销售','采购','供应商','客户','印刷','运费','期初','盘盈','盘亏',...props.modelValue])].map(value=>({label:value,value})))
function update(values:string[]){emit('update:modelValue',[...new Set(values.map(v=>v.trim()).filter(Boolean))])}
</script>
<template><NSelect :value="modelValue" :options="options" :disabled="disabled" multiple filterable tag clearable placeholder="选择标签或输入自定义标签" @update:value="update"/></template>
