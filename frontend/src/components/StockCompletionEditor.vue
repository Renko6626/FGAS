<script setup lang="ts">
import {computed, ref} from 'vue'
import {NButton, NInput, NModal} from 'naive-ui'
import {warehouse, versions, today, key, failure, type StockTransfer} from '../api/warehouse'

const props = defineProps<{item: StockTransfer; trusted: boolean}>()
const emit = defineEmits<{changed: []; pending: [boolean]}>()
const show = ref(false)
const busy = ref(false)
const error = ref('')
const date = ref(today())
const basis = ref('')
const observations = ref<Record<string, string>>({})
const locked = ref(false)
const submittedItem = ref<StockTransfer | null>(null)
const displayedItem = computed(() => submittedItem.value || props.item)
let pending: {path: string; body: Record<string, unknown>} | null = null

function clearPending() {
  pending = null
  locked.value = false
  submittedItem.value = null
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
    await warehouse.action(pending.path, pending.body)
    show.value = false
    clearPending()
    emit('changed')
  } catch (e) {
    error.value = failure(e)
    if ([400, 422].includes((e as {status?: number}).status || 0)) {
      clearPending()
      error.value = (e as Error).message + '。请修正输入后提交。'
    }
  } finally {
    busy.value = false
  }
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
    <NButton :loading="busy" @click="save">{{locked?'重试原请求':trusted?'确认整条转移已完成':'提交完成申报'}}</NButton>
  </NModal>
</template>
