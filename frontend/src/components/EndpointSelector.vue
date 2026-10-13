<script setup lang="ts">
import {computed,ref} from 'vue'
import {NSelect,NCheckbox} from 'naive-ui'
import AccountAvatar from './AccountAvatar.vue'
import {kinds,type AccountBase} from '../api/funds'
const props=defineProps<{accounts:AccountBase[];modelValue:string;label:string;disabled?:boolean}>()
const emit=defineEmits<{ 'update:modelValue':[string] }>()
const showEnded=ref(false)
const category=ref<string|null>(null),tag=ref<string|null>(null)
const tags=computed(()=>[...new Set(props.accounts.flatMap(a=>a.tags))].map(value=>({label:value,value})))
const options=computed(()=>props.accounts.filter(a=>a.id===props.modelValue||(a.active&&(showEnded.value||a.stocktake?.status!=='ended')&&(!category.value||a.kind===category.value)&&(!tag.value||a.tags.includes(tag.value)))).map(a=>({label:`${a.name} (${a.id})`,value:a.id})))
const selected=computed(()=>props.accounts.find(a=>a.id===props.modelValue))
</script>
<template><div class="endpoint"><label>{{label}}</label><div class="filters"><NSelect :disabled="disabled" v-model:value="category" clearable placeholder="所有类别" :options="Object.entries(kinds).map(([value,label])=>({value,label}))"/><NSelect :disabled="disabled" v-model:value="tag" clearable placeholder="所有标签" :options="tags"/></div><NSelect :disabled="disabled" :value="modelValue||null" :options="options" filterable placeholder="选择记账对象" @update:value="emit('update:modelValue',$event || '')"/><NCheckbox v-model:checked="showEnded" :disabled="disabled">显示已结束盘点端点</NCheckbox><AccountAvatar v-if="selected" :name="selected.name" :url="selected.avatar_url"/><small>已选：{{selected?`${selected.name} (${selected.id})`:'尚未选择'}}；筛选不会更改已选对象。</small></div></template>
