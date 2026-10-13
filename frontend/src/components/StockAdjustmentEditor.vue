<script setup lang="ts">
import {computed, ref} from 'vue'
import {NButton, NInput, NModal, NSelect} from 'naive-ui'
import type {Location} from '../api/funds'
import {warehouse, today, type StockTransfer} from '../api/warehouse'
const props = defineProps<{item: StockTransfer; locations: Location[]}>()
const emit = defineEmits<{changed: []}>()
const show = ref(false), busy = ref(false), error = ref('')
const sku = ref(''), location = ref(''), action = ref('adjustment_loss'), quantity = ref(''), external = ref(''), date = ref(today()), basis = ref('')
const endpoints = computed(() => [
  ...(props.item.source_kind==='physical'?[{label:props.item.source_location_name,value:props.item.source_location_id}]:[]),
  ...(props.item.destination_kind==='physical'?[{label:props.item.destination_location_name,value:props.item.destination_location_id}]:[])
])
const boundaries = computed(() => props.locations.filter(l=>l.active&&l.kind==='external'&&l.external_kind===action.value).map(l=>({label:l.name,value:l.id})))
async function save() {
  if (busy.value) return
  error.value = ''
  if (!/^[0-9]+$/.test(quantity.value)||BigInt(quantity.value)===0n) { error.value='请输入正整数调整数量'; return }
  busy.value = true
  try {
    const gain = action.value==='adjustment_gain'
    await warehouse.submit({
      source_location_id: gain?external.value:location.value,
      destination_location_id: gain?location.value:external.value,
      action_kind: action.value, effective_date: date.value, description: '盈亏调整',
      basis: basis.value, source_reference: null, fund_transfer_ids: [],
      related_transfer_id: props.item.id, lines: [{sku_id:sku.value,quantity:quantity.value}]
    })
    show.value = false
    emit('changed')
  } catch (e) { error.value=(e as Error).message+'。请刷新查看当前记录后再操作。' }
  finally { busy.value=false }
}
</script>
<template>
  <NButton @click="show=true">新增盈亏调整</NButton>
  <NModal v-model:show="show" preset="card" title="新增盈亏调整" class="dialog">
    <p>关联原转移 {{item.id}}，填写要增加或减少的数量。调整仍需单独确认完成。</p>
    <label>SKU<NSelect v-model:value="sku" :disabled="busy" :options="item.lines.map(l=>({label:`${l.sku_name}（${l.unit}）`,value:l.sku_id}))"/></label>
    <label>实际地点<NSelect v-model:value="location" :disabled="busy" :options="endpoints"/></label>
    <label>调整方向<NSelect v-model:value="action" :disabled="busy" :options="[{label:'盘盈（增加库存）',value:'adjustment_gain'},{label:'盘亏（减少库存）',value:'adjustment_loss'}]" @update:value="external=''"/></label>
    <label>数量<NInput v-model:value="quantity" :disabled="busy" placeholder="正整数"/></label>
    <label>外部调整端点<NSelect v-model:value="external" :disabled="busy" :options="boundaries"/></label>
    <label>日期<NInput v-model:value="date" :disabled="busy"/></label>
    <label>依据<NInput v-model:value="basis" :disabled="busy"/></label>
    <p class="error">{{error}}</p>
    <NButton :loading="busy" @click="save">创建调整转移</NButton>
  </NModal>
</template>
