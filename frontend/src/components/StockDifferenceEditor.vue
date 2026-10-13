<script setup lang="ts">
import {ref} from 'vue'
import {NButton, NInput, NModal, NSelect} from 'naive-ui'
import {request} from '../api/client'
import {warehouse, key, failure, isDefinitiveStockConflict, stockStatuses, type StockTransfer} from '../api/warehouse'
import {useOperationAttempt} from '../composables/useOperationAttempt'

const props = defineProps<{item: StockTransfer}>()
const emit = defineEmits<{changed: []; pending: [boolean]; current: [StockTransfer]}>()
const show = ref(false)
const line = ref('')
const location = ref('')
const quantity = ref('')
const basis = ref('')
const at = ref(new Date().toISOString())
type DifferenceAttempt = {transferId: string; body: Record<string, unknown>}
const {
  pending: locked, busy, error, conflict, currentRecord,
  start, readCurrent, acknowledgeConflict
} = useOperationAttempt<DifferenceAttempt, StockTransfer>({
  submit: saved => request(`/stock-transfers/${saved.transferId}/differences`, 'POST', saved.body),
  readCurrent: saved => warehouse.detail(saved.transferId),
  isDefinitiveConflict: isDefinitiveStockConflict,
  describeError: failure,
  onPendingChange: value => emit('pending', value),
  onCurrent: current => emit('current', current),
  onResolved: () => { show.value = false; emit('changed') }
})

function save() {
  return start(() => {
    if (!/^[0-9]+$/.test(quantity.value)) throw new Error('实际数量须为非负整数')
    return {
      transferId: props.item.id,
      body: {
        line_id: line.value, location_id: location.value, observed_quantity: quantity.value,
        comparison_at: at.value, basis: basis.value, idempotency_key: key()
      }
    }
  })
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
