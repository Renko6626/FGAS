<script setup lang="ts">
import {ref, watch, computed} from 'vue'
import {NButton, NInput, NModal, NSelect} from 'naive-ui'
import type {Location, Transfer} from '../api/funds'
import {money, statuses as fundStatuses} from '../api/funds'
import {
  warehouse, versions, key, failure, today, stockStatuses, actions,
  isDefinitiveStockConflict, type StockTransfer, type Difference
} from '../api/warehouse'
import {useOperationAttempt} from '../composables/useOperationAttempt'
import StockCompletionEditor from '../components/StockCompletionEditor.vue'
import StockDifferenceEditor from '../components/StockDifferenceEditor.vue'

const props = defineProps<{
  items: StockTransfer[]
  locations: Location[]
  funds: Transfer[]
  trusted: boolean
  approvals?: boolean
  focus?: string
}>()
const emit = defineEmits<{changed: []}>()
const detailShow = ref(false)
const completionPending = ref(false)
const differencePending = ref(false)
const childPending = computed(() => completionPending.value || differencePending.value)
const detail = ref<StockTransfer | null>(null)
const reason = ref('')
const fund = ref('')
const adjust = ref<Difference | null>(null)
const external = ref('')
const basis = ref('')
const date = ref(today())
type StockAttempt = {path: string; body: Record<string, unknown>; transferId: string}
const {
  pending: actionPending, busy, error, conflict, currentRecord,
  start, retry, readCurrent, acknowledgeConflict, isActive
} = useOperationAttempt<StockAttempt, StockTransfer>({
  submit: saved => warehouse.action(saved.path, saved.body),
  readCurrent: saved => warehouse.detail(saved.transferId),
  isDefinitiveConflict: isDefinitiveStockConflict,
  describeError: failure,
  onCurrent: reconcileDetail,
  onResolved: async resolution => {
    adjust.value = null
    if (resolution === 'submitted') await changed()
    else emit('changed')
  }
})
let detailReadSerial = 0
const fundOptions = computed(() => props.funds.map(f => ({
  label: `${f.description || f.id}（${fundStatuses[f.status]}）`, value: f.id
})))
const visibleItems = computed(() => props.items.filter(item =>
  !props.approvals || item.status === 'pending' ||
  item.confirmations.some(confirmation => confirmation.status === 'pending')
))
// A submitted child must survive status changes caused by its own successful POST.
const showCompletion = computed(() => completionPending.value || (
  detail.value?.status === 'in_transit' &&
  !detail.value.confirmations.some(confirmation => confirmation.status === 'pending') &&
  !actionPending.value && !busy.value && !differencePending.value
))
const showDifference = computed(() => differencePending.value || (
  props.trusted && detail.value?.status === 'completed' &&
  !actionPending.value && !busy.value && !completionPending.value
))
const canAct = computed(() => props.trusted && !actionPending.value && !busy.value && !childPending.value)

async function open(id: string) {
  if ((childPending.value || actionPending.value) && detail.value?.id !== id) {
    error.value = '请先核对并重试当前详情保留的原请求。'
    return
  }
  const readSerial = ++detailReadSerial
  try {
    detailShow.value = true
    const result = await warehouse.detail(id)
    // A query started earlier must not replace an editor submitted while it was in flight.
    if (!isActive() || readSerial !== detailReadSerial || ((childPending.value || actionPending.value) && detail.value?.id !== id)) return
    detail.value = result
    error.value = ''
  } catch (e) {
    if (isActive()) error.value = (e as Error).message
  }
}
watch(() => props.focus, id => { if (id) open(id) }, {immediate: true})

async function changed() {
  emit('changed')
  if (detail.value) await open(detail.value.id)
}

function run(path: string, body: Record<string, unknown>) {
  if (actionPending.value || childPending.value || busy.value || !detail.value) return
  return start(() => ({path, body, transferId: detail.value!.id}))
}

function reconcileDetail(result: StockTransfer) {
  if (isActive() && detail.value?.id === result.id) {
    detailReadSerial++
    detail.value = result
  }
}

function decide(item: StockTransfer, action: string, confirmationId?: string) {
  const path = confirmationId
    ? `/stock-confirmations/${confirmationId}/${action}`
    : `/stock-transfers/${item.id}/${action}`
  run(path, {
    ...versions(item), idempotency_key: key(),
    ...(['reject', 'cancel'].includes(action) ? {reason: reason.value} : {})
  })
}

function adjustment() {
  if (!adjust.value) return
  run(`/stock-differences/${adjust.value.id}/adjustment`, {
    external_location_id: external.value,
    effective_date: date.value,
    basis: basis.value,
    idempotency_key: key()
  })
}
</script>

<template>
  <div class="toolbar">
    <h2>{{approvals?'货物审批与完成申报':'货物转移记录'}}</h2>
    <NButton @click="emit('changed')">刷新</NButton>
  </div>
  <p class="error">{{error}}</p>
  <p v-if="childPending">详情保留了原请求。请刷新核对，再打开原表单重试；完成核对前不能提交其他操作。</p>
  <div v-if="actionPending" class="banner">
    <p>原操作内容已保留。先刷新详情核对结果；重试只发送同一请求，不需要再次交货。</p>
    <NButton :loading="busy" @click="retry">重试原操作</NButton>
    <section v-if="conflict">
      <p>这次操作已被服务器拒绝。读取当前转移、完成申报及差异调整后，确认结束失败尝试。</p>
      <NButton :disabled="busy" @click="readCurrent">读取当前记录</NButton>
      <template v-if="currentRecord">
        <p>当前货物状态：{{stockStatuses[currentRecord.status]}}。</p>
        <p v-for="c in currentRecord.confirmations" :key="c.id">完成申报：{{stockStatuses[c.status]||c.status}}，{{c.effective_date}}，{{c.basis}}</p>
        <p v-for="d in currentRecord.differences" :key="d.id">{{d.sku_name}} 差异 {{d.delta}}，{{stockStatuses[d.status]}}。</p>
        <p>当前详情已更新，可查看原记录、已有申报及关联调整。</p>
        <NButton :disabled="busy" @click="acknowledgeConflict">已核对当前记录，结束失败尝试</NButton>
        <p>此操作不会认定原请求成功，也不要求再次交货；新的操作需按当前状态重新准备。</p>
      </template>
    </section>
  </div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>日期 / 用途</th>
          <th>来源 → 去向</th>
          <th>数量</th>
          <th>货物状态</th>
          <th>资金状态</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="t in visibleItems" :key="t.id">
          <td>{{t.effective_date}}<small>{{actions[t.action_kind]}}</small>
          </td>
          <td>{{t.source_location_name}} → {{t.destination_location_name}}</td>
          <td>
            <div v-for="l in t.lines" :key="l.id">{{l.sku_name}}：{{l.quantity}} {{l.unit}}</div>
          </td>
          <td>{{stockStatuses[t.status]}}</td>
          <td>
            <div v-for="f in t.fund_references" :key="f.id">{{fundStatuses[f.status]||f.status}}，¥ {{money(f.amount_minor)}}</div>
            <span v-if="!t.fund_references.length">未关联</span>
          </td>
          <td>
            <NButton @click="open(t.id)">详情 / 处理</NButton>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
  <NModal v-model:show="detailShow" display-directive="show" preset="card" title="货物转移详情" class="dialog">
    <template v-if="detail">
      <p>{{detail.id}}</p>
      <p>{{detail.source_location_name}} → {{detail.destination_location_name}}，{{stockStatuses[detail.status]}}</p>
      <p>说明：{{detail.description}}；依据：{{detail.basis}}</p>
      <ul>
        <li v-for="l in detail.lines" :key="l.id">{{l.sku_name}}：{{l.quantity}} {{l.unit}}</li>
      </ul>
      <NButton @click="open(detail.id)">刷新详情</NButton>
      <template v-if="canAct">
        <label>拒绝 / 取消原因
          <NInput v-model:value="reason"/>
        </label>
        <div class="actions">
          <template v-if="detail.status==='pending'">
            <NButton :loading="busy" @click="decide(detail,'approve')">批准货物转移</NButton>
            <NButton :disabled="!reason" @click="decide(detail,'reject')">拒绝</NButton>
          </template>
          <NButton v-if="['pending','in_transit'].includes(detail.status)" :disabled="!reason" @click="decide(detail,'cancel')">取消货物转移</NButton>
        </div>
      </template>
      <StockCompletionEditor
        v-if="showCompletion"
        :key="detail.id"
        :item="detail"
        :trusted="trusted"
        @pending="completionPending=$event"
        @current="reconcileDetail"
        @changed="changed"
      />
      <div v-for="c in detail.confirmations" :key="c.id">
        <h3>完成申报：{{stockStatuses[c.status]||c.status}}</h3>
        <p>申报人 {{c.actor_id}}；日期 {{c.effective_date}}；依据 {{c.basis}}</p>
        <ul>
          <li v-for="o in c.payload.observations" :key="o.line_id">{{detail.lines.find(l=>l.id===o.line_id)?.sku_name}} 观察 {{o.observed_quantity}}；{{o.basis}}</li>
        </ul>
        <template v-if="canAct&&c.status==='pending'">
          <p>请审阅实际完成事实，批准后按整条批准数量记录库存。</p>
          <NButton @click="decide(detail,'approve',c.id)">批准完成申报</NButton>
          <NButton :disabled="!reason" @click="decide(detail,'reject',c.id)">拒绝完成申报</NButton>
        </template>
      </div>
      <h3>当前关联资金</h3>
      <p>资金与货物独立生效，关联记录不代表已付款。</p>
      <div v-for="f in detail.fund_references" :key="f.id">
        <p>{{f.description||f.id}}：{{fundStatuses[f.status]||f.status}}，¥ {{money(f.amount_minor)}}</p>
        <p v-if="f.claim">垫付声明 ¥ {{money(f.claim.declared_minor)}}；确认 {{f.claim.confirmed_minor===null?'未确认':'¥ '+money(f.claim.confirmed_minor)}}；{{f.claim.basis}}</p>
      </div>
      <template v-if="canAct">
        <label>补充已有资金关联
          <NSelect v-model:value="fund" :options="fundOptions"/>
        </label>
        <NButton :disabled="!fund" @click="run(`/stock-transfers/${detail.id}/fund-references`,{fund_transfer_id:fund,idempotency_key:key()})">关联资金记录</NButton>
      </template>
      <details>
        <summary>原批准范围与资金快照</summary>
        <pre>{{JSON.stringify(detail.approval_snapshot,null,2)}}</pre>
      </details>
      <StockDifferenceEditor
        v-if="showDifference"
        :key="detail.id"
        :item="detail"
        @pending="differencePending=$event"
        @current="reconcileDetail"
        @changed="changed"
      />
      <h3 v-if="detail.differences.length">数量差异</h3>
      <div v-for="d in detail.differences" :key="d.id">
        <p>{{d.location_name}} {{d.sku_name}}：批准 {{d.expected_quantity}}，观察 {{d.observed_quantity}}，库存差异 {{d.delta}}。{{stockStatuses[d.status]}}；{{d.basis}}</p>
        <div v-for="a in d.adjustments" :key="a.id">
          <NButton text @click="open(a.id)">调整 {{a.id}}，{{stockStatuses[a.status]}}</NButton>
        </div>
        <NButton v-if="canAct&&d.status==='unresolved'" @click="adjust=d;external='';basis=''">创建调整转移</NButton>
      </div>
      <p v-if="detail.difference_id">原差异：{{detail.difference_id}}</p>
      <details>
        <summary>操作追溯</summary>
        <pre>{{JSON.stringify(detail.audit,null,2)}}</pre>
      </details>
    </template>
  </NModal>
  <NModal :show="!!adjust" preset="card" title="创建差异调整" class="dialog" @update:show="!$event&&(adjust=null)">
    <template v-if="adjust">
      <p>库存差异 {{adjust.delta}}，调整转移仍须手动确认完成。</p>
      <label>调整外部端点<NSelect :disabled="actionPending||childPending||busy" v-model:value="external" :options="locations.filter(l=>l.active&&l.kind==='external'&&l.external_kind===(adjust?.delta.startsWith('-')?'adjustment_loss':'adjustment_gain')).map(l=>({label:l.name,value:l.id}))"/>
      </label>
      <label>日期<NInput :disabled="actionPending||childPending||busy" v-model:value="date"/>
      </label>
      <label>依据<NInput :disabled="actionPending||childPending||busy" v-model:value="basis"/>
      </label>
      <p class="error">{{error}}</p>
      <NButton :disabled="actionPending||childPending||busy" :loading="busy" @click="adjustment">创建调整</NButton>
    </template>
  </NModal>
</template>
