<script setup lang="ts">
import {computed, ref} from 'vue'
import {NButton, NInput, NModal} from 'naive-ui'
import {warehouse, versions, today, key, failure, isDefinitiveStockConflict, stockStatuses, type StockTransfer} from '../api/warehouse'
import {useOperationAttempt} from '../composables/useOperationAttempt'

const props = defineProps<{item: StockTransfer; trusted: boolean}>()
const emit = defineEmits<{changed: []; pending: [boolean]; current: [StockTransfer]}>()
const show = ref(false)
const date = ref(today())
const basis = ref('')
const observations = ref<Record<string, string>>({})
type CompletionAttempt = {path: string; body: Record<string, unknown>; snapshot: StockTransfer}
const {
  attempt, pending: locked, busy, error, conflict, currentRecord,
  start, readCurrent, acknowledgeConflict
} = useOperationAttempt<CompletionAttempt, StockTransfer>({
  submit: saved => warehouse.action(saved.path, saved.body),
  readCurrent: saved => warehouse.detail(saved.snapshot.id),
  isDefinitiveConflict: isDefinitiveStockConflict,
  describeError: failure,
  onPendingChange: value => emit('pending', value),
  onCurrent: current => emit('current', current),
  onResolved: () => { show.value = false; emit('changed') }
})
const displayedItem = computed(() => attempt.value?.snapshot || props.item)

function save() {
  return start(() => {
    const observed = props.item.lines.filter(line => {
      const value = observations.value[line.id]
      return value !== undefined && value !== ''
    })
    if (observed.some(line => !/^[0-9]+$/.test(observations.value[line.id]!))) {
      throw new Error('实际数量须为非负整数，留空表示未观察')
    }
    return {
      snapshot: props.item,
      path: `/stock-transfers/${props.item.id}/completion`,
      body: {
        ...versions(props.item), effective_date: date.value, basis: basis.value,
        idempotency_key: key(),
        observations: observed.map(line => ({
          line_id: line.id, observed_quantity: observations.value[line.id], basis: basis.value
        }))
      }
    }
  })
}
</script>

<template>
  <NButton @click="show=true">{{locked?'核对 / 重试原完成请求':trusted?'确认完成':'申报已完成'}}</NButton>
  <NModal v-model:show="show" preset="card" title="核对整条转移的实际完成情况" class="dialog">
    <p>{{displayedItem.source_location_name}} → {{displayedItem.destination_location_name}}。确认后按整条批准数量记账，实际观察差异单独记录。</p>
    <ul>
      <li v-for="l in displayedItem.lines" :key="l.id">{{l.sku_name}}：{{l.quantity}} {{l.unit}}
        <small v-if="displayedItem.source_kind==='physical'">{{displayedItem.source_location_name}} 扣减 {{l.quantity}} {{l.unit}}</small>
        <small v-if="displayedItem.destination_kind==='physical'">{{displayedItem.destination_location_name}} 增加 {{l.quantity}} {{l.unit}}</small>
        <label>实际观察数量（可留空）
          <NInput :disabled="locked" v-model:value="observations[l.id]" placeholder="非负整数；0 表示观察为零"/>
        </label>
      </li>
    </ul>
    <details>
      <summary>批准范围</summary>
      <pre>{{JSON.stringify(displayedItem.approval_snapshot,null,2)}}</pre>
    </details>
    <label>完成日期
      <NInput :disabled="locked" v-model:value="date"/>
    </label>
    <label>实际完成依据
      <NInput :disabled="locked" v-model:value="basis"/>
    </label>
    <p v-if="!trusted">申报提交后等待受信任用户审阅实际事实，审批通过才记录库存。</p>
    <p v-if="locked">原完成请求和批准范围已保留。刷新后的当前状态不会改变重试内容，也无需再次交货。</p>
    <p class="error">{{error}}</p>
    <section v-if="conflict">
      <p>这是失败尝试的核对，不代表原请求成功，也不要求再次交货。</p>
      <NButton :disabled="busy" @click="readCurrent">读取当前记录</NButton>
      <template v-if="currentRecord">
        <p>当前货物状态：{{stockStatuses[currentRecord.status]}}。</p>
        <p v-for="c in currentRecord.confirmations" :key="c.id">完成申报：{{stockStatuses[c.status]||c.status}}，{{c.effective_date}}，{{c.basis}}</p>
        <p>详情已更新为当前记录；上方原批准范围仍保留供核对。</p>
        <NButton :disabled="busy" @click="acknowledgeConflict">已核对当前记录，结束失败尝试</NButton>
        <p>结束后只能按当前状态重新准备操作，新尝试会使用新的请求键。</p>
      </template>
    </section>
    <NButton :loading="busy" @click="save">{{locked?'重试原请求':trusted?'确认整条转移已完成':'提交完成申报'}}</NButton>
  </NModal>
</template>
