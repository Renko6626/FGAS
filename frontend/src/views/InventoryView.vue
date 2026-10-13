<script setup lang="ts">
import {ref,onMounted} from 'vue'
import {NButton,NSelect} from 'naive-ui'
import type {Location,Sku} from '../api/funds'
import type {Member} from '../api/memberClaims'
import {warehouse,stockStatuses,type InventoryRow} from '../api/warehouse'
const props=defineProps<{locations:Location[];skus:Sku[];members:Member[];revision:number}>(),emit=defineEmits<{open:[string]}>()
const location=ref(''),sku=ref(''),member=ref(''),rows=ref<InventoryRow[]>([]),totals=ref<{sku_id:string;quantity:string;valuation:string}[]>([]),error=ref(''),busy=ref(false),snapshot=ref('')
async function refresh(){busy.value=true;try{const result=await warehouse.inventory({location_id:location.value,sku_id:sku.value,member_id:member.value});rows.value=result.quantities;totals.value=result.totals;snapshot.value=result.snapshot_at;error.value=''}catch(e){error.value=(e as Error).message}finally{busy.value=false}}
onMounted(refresh)
</script>
<template><div class="toolbar"><h2>库存数量</h2><NButton :loading="busy" @click="refresh">查询 / 刷新</NButton></div><div class="filters"><NSelect v-model:value="location" clearable placeholder="所有实际地点" :options="props.locations.filter(l=>l.kind==='physical').map(l=>({label:l.name,value:l.id}))"/><NSelect v-model:value="sku" clearable placeholder="所有 SKU" :options="skus.map(s=>({label:s.name,value:s.id}))"/><NSelect v-model:value="member" clearable placeholder="所有当前保管成员" :options="members.map(m=>({label:m.name,value:m.id}))"/></div><p class="error">{{error}}</p><p>未估值。仅已确认完成的转移影响库存。查询时间：{{snapshot}}</p><div class="table-wrap"><table><thead><tr><th>地点 / 当前保管成员</th><th>SKU</th><th>库存数量</th><th>未完成转移涉及数量</th><th>已知差异</th></tr></thead><tbody><tr v-for="r in rows" :key="r.location_id+r.sku_id"><td>{{r.location_name}}<small>{{r.member_name||'未指定成员'}}</small></td><td>{{r.sku_name}}</td><td>{{r.quantity}} {{r.unit}}</td><td>{{r.in_transit_planned_quantity}}</td><td><div v-for="d in r.differences" :key="d.id"><NButton text @click="emit('open',d.stock_transfer_id)">{{d.delta}}，{{stockStatuses[d.status]||d.status}}</NButton><small v-if="d.adjustment_id">调整 {{d.adjustment_id}}：{{stockStatuses[d.adjustment_status||'']}}</small></div></td></tr></tbody></table></div><p v-for="t in totals" :key="t.sku_id">{{skus.find(s=>s.id===t.sku_id)?.name||t.sku_id}} 合计：{{t.quantity}}，{{t.valuation}}</p></template>
