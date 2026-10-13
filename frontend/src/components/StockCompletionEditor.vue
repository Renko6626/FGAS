<script setup lang="ts">
import {ref} from 'vue'
import {NButton, NInput, NModal} from 'naive-ui'
import {warehouse, today, type StockTransfer} from '../api/warehouse'
const props = defineProps<{item: StockTransfer; trusted: boolean}>()
const emit = defineEmits<{changed: []}>()
const show = ref(false), busy = ref(false), error = ref(''), date = ref(today()), basis = ref('')
async function save() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await warehouse.action(`/stock-transfers/${props.item.id}/completion`, {
      effective_date: date.value, basis: basis.value
    })
    show.value = false
    emit('changed')
  } catch (e) {
    error.value = (e as Error).message + '。请刷新查看当前记录后再操作。'
  } finally { busy.value = false }
}
</script>
<template>
  <NButton @click="show=true">{{trusted?'确认完成':'申报已完成'}}</NButton>
  <NModal v-model:show="show" preset="card" title="确认整条转移已完成" class="dialog">
    <p>{{item.source_location_name}} → {{item.destination_location_name}}，按整条批准数量记账。</p>
    <ul>
      <li v-for="l in item.lines" :key="l.id">{{l.sku_name}}：{{l.quantity}} {{l.unit}}
        <small v-if="item.source_kind==='physical'">{{item.source_location_name}} 扣减 {{l.quantity}} {{l.unit}}</small>
        <small v-if="item.destination_kind==='physical'">{{item.destination_location_name}} 增加 {{l.quantity}} {{l.unit}}</small>
      </li>
    </ul>
    <label>完成日期<NInput v-model:value="date" :disabled="busy"/></label>
    <label>实际完成依据<NInput v-model:value="basis" :disabled="busy"/></label>
    <p v-if="!trusted">申报提交后等待受信任用户审阅，批准后才记录库存。</p>
    <p class="error">{{error}}</p>
    <NButton :loading="busy" @click="save">{{trusted?'确认整条转移已完成':'提交完成申报'}}</NButton>
  </NModal>
</template>
