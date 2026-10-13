<script setup lang="ts">
import {computed, ref, onBeforeUnmount} from 'vue'
import {NButton, NInput, NModal} from 'naive-ui'
import {warehouse, versions, today, key, failure, isDefinitiveStockConflict, stockStatuses, type StockTransfer} from '../api/warehouse'

const props = defineProps<{item: StockTransfer; trusted: boolean}>()
const emit = defineEmits<{changed: []; pending: [boolean]; current: [StockTransfer]}>()
const show = ref(false)
const busy = ref(false)
const error = ref('')
const date = ref(today())
const basis = ref('')
const observations = ref<Record<string, string>>({})
const locked = ref(false)
const conflict = ref(false)
const currentRecord = ref<StockTransfer | null>(null)
let disposed = false
onBeforeUnmount(() => { disposed = true })
const submittedItem = ref<StockTransfer | null>(null)
const displayedItem = computed(() => submittedItem.value || props.item)
let pending: {path: string; body: Record<string, unknown>} | null = null

function clearPending() {
  pending = null
  locked.value = false
  submittedItem.value = null
  conflict.value = false
  currentRecord.value = null
  emit('pending', false)
}

async function save() {
  if (busy.value) return
  error.value = ''
  try {
    if (!pending) {
      const observed = props.item.lines.filter(line => {
        const value = observations.value[line.id]
        return value !== undefined && value !== ''
      })
      if (observed.some(line => !/^[0-9]+$/.test(observations.value[line.id]!))) {
        throw new Error('实际数量须为非负整数，留空表示未观察')
      }
      submittedItem.value = JSON.parse(JSON.stringify(props.item)) as StockTransfer
      pending = {
        path: `/stock-transfers/${props.item.id}/completion`,
        body: {
          ...versions(props.item),
          effective_date: date.value,
          basis: basis.value,
          idempotency_key: key(),
          observations: observed.map(line => ({
            line_id: line.id,
            observed_quantity: observations.value[line.id],
            basis: basis.value
          }))
        }
      }
      locked.value = true
      emit('pending', true)
    }
    busy.value = true
    conflict.value = false
    currentRecord.value = null
    await warehouse.action(pending.path, pending.body)
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
    const result = await warehouse.detail(submittedItem.value!.id)
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
  // Only an explicit acknowledgement after a successful authoritative read releases this owner.
  emit('current', currentRecord.value)
  clearPending()
  show.value = false
  emit('changed')
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
