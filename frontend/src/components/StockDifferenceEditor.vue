<script setup lang="ts">
import {ref, onBeforeUnmount} from 'vue'
import {NButton, NInput, NModal, NSelect} from 'naive-ui'
import {request} from '../api/client'
import {warehouse, key, failure, isDefinitiveStockConflict, stockStatuses, type StockTransfer} from '../api/warehouse'

const props = defineProps<{item: StockTransfer}>()
const emit = defineEmits<{changed: []; pending: [boolean]; current: [StockTransfer]}>()
const show = ref(false)
const busy = ref(false)
const error = ref('')
const line = ref('')
const location = ref('')
const quantity = ref('')
const basis = ref('')
const at = ref(new Date().toISOString())
const locked = ref(false)
const conflict = ref(false)
const currentRecord = ref<StockTransfer | null>(null)
let pending: {transferId: string; body: Record<string, unknown>} | null = null
let disposed = false
onBeforeUnmount(() => { disposed = true })

function clearPending() {
  pending = null
  locked.value = false
  conflict.value = false
  currentRecord.value = null
  emit('pending', false)
}

async function save() {
  if (busy.value) return
  try {
    if (!pending) {
      if (!/^[0-9]+$/.test(quantity.value)) throw new Error('实际数量须为非负整数')
      pending = {
        transferId: props.item.id,
        body: {
          line_id: line.value,
          location_id: location.value,
          observed_quantity: quantity.value,
          comparison_at: at.value,
          basis: basis.value,
          idempotency_key: key()
        }
      }
      locked.value = true
      emit('pending', true)
    }
    busy.value = true
    conflict.value = false
    currentRecord.value = null
    await request(`/stock-transfers/${pending.transferId}/differences`, 'POST', pending.body)
    if (disposed) return
    show.value = false
    clearPending()
    emit('changed')
  } catch (e) {
    if (disposed) return
    conflict.value = isDefinitiveStockConflict(e)
    error.value = conflict.value
      ? (e as Error).message + '。这次尝试未提交，请读取当前记录后核对处理。'
      : failure(e)
    if ([400, 422].includes((e as {status?: number}).status || 0)) {
      clearPending()
      error.value = (e as Error).message + '。请修正输入后提交。'
    }
  } finally {
    busy.value = false
  }
}

async function readCurrent() {
  if (!pending || !conflict.value || busy.value) return
  const attempt = pending
  busy.value = true
  currentRecord.value = null
  try {
    const result = await warehouse.detail(attempt.transferId)
    if (disposed || pending !== attempt) return
    currentRecord.value = result
    emit('current', result)
  } catch (e) {
    if (!disposed) error.value = (e as Error).message + '。读取失败，原请求仍保留。'
  } finally {
    busy.value = false
  }
}

function acknowledgeConflict() {
  if (!pending || !conflict.value || !currentRecord.value || busy.value) return
  emit('current', currentRecord.value)
  clearPending()
  show.value = false
  emit('changed')
}
</script>

<template>
  <NButton @click="show=true">{{locked?'核对 / 重试原差异请求':'记录数量差异'}}</NButton>
  <NModal v-model:show="show" preset="card" title="记录这条转移的数量差异" class="dialog">
    <p>填写该转移在所选实际地点的观察数量，不能用整仓盘点数量代替。</p>
    <label>SKU
      <NSelect :disabled="locked" v-model:value="line" :options="item.lines.map(l=>({label:`${l.sku_name}（批准 ${l.quantity} ${l.unit}）`,value:l.id}))"/>
    </label>
    <label>实际地点
      <NSelect :disabled="locked" v-model:value="location" :options="[...(item.source_kind==='physical'?[{label:item.source_location_name,value:item.source_location_id}]:[]),...(item.destination_kind==='physical'?[{label:item.destination_location_name,value:item.destination_location_id}]:[])]"/>
    </label>
    <label>观察数量<NInput :disabled="locked" v-model:value="quantity" placeholder="非负整数"/></label>
    <label>比较时间（含时区）<NInput :disabled="locked" v-model:value="at"/></label>
    <label>依据<NInput :disabled="locked" v-model:value="basis"/></label>
    <p class="error">{{error}}</p>
    <section v-if="conflict">
      <p>请核对当前已有差异。结束失败尝试不会覆盖他人的观察记录。</p>
      <NButton :disabled="busy" @click="readCurrent">读取当前记录</NButton>
      <template v-if="currentRecord">
        <p>当前货物状态：{{stockStatuses[currentRecord.status]}}。</p>
        <div v-for="d in currentRecord.differences" :key="d.id">
          <p>{{d.location_name}} {{d.sku_name}}：批准 {{d.expected_quantity}}，观察 {{d.observed_quantity}}，差异 {{d.delta}}；{{stockStatuses[d.status]}}。依据：{{d.basis}}</p>
          <p v-for="a in d.adjustments" :key="a.id">关联调整 {{a.id}}：{{stockStatuses[a.status]}}</p>
        </div>
        <NButton :disabled="busy" @click="acknowledgeConflict">已核对当前记录，结束失败尝试</NButton>
        <p>结束后可按当前记录重新准备操作，新尝试会使用新的请求键。</p>
      </template>
    </section>
    <NButton :loading="busy" @click="save">{{locked?'重试原请求':'记录差异'}}</NButton>
  </NModal>
</template>
