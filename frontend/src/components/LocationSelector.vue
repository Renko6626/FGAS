<script setup lang="ts">
import {computed,ref} from 'vue'
import {NSelect,NCheckbox} from 'naive-ui'
import type {Location} from '../api/funds'
const props=defineProps<{locations:Location[];modelValue:string;label:string;disabled?:boolean}>()
const emit=defineEmits<{'update:modelValue':[string]}>()
const showEnded=ref(false)
const options=computed(()=>props.locations.filter(l=>l.id===props.modelValue||(l.active&&(showEnded.value||l.stocktake?.status!=='ended'))).map(l=>({label:`${l.name} (${l.id})`,value:l.id})))
</script>
<template><div class="endpoint"><label>{{label}}</label><NSelect :disabled="disabled" :value="modelValue||null" :options="options" filterable placeholder="选择位置" @update:value="emit('update:modelValue',$event||'')"/><NCheckbox :disabled="disabled" v-model:checked="showEnded">显示已结束盘点端点</NCheckbox></div></template>
