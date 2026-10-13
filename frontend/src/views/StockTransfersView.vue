<script setup lang="ts">
import {ref, computed} from 'vue'
import {NButton, NInput, NModal, NSelect} from 'naive-ui'
import type {Location, Transfer} from '../api/funds'
import {money, statuses as fundStatuses} from '../api/funds'
import {warehouse, stockStatuses, actions, type StockTransfer} from '../api/warehouse'
import StockCompletionEditor from '../components/StockCompletionEditor.vue'
import StockAdjustmentEditor from '../components/StockAdjustmentEditor.vue'
const props=defineProps<{items:StockTransfer[];locations:Location[];funds:Transfer[];trusted:boolean;approvals?:boolean}>()
const emit=defineEmits<{changed:[]}>()
const detailShow=ref(false),detail=ref<StockTransfer|null>(null),busy=ref(false),error=ref(''),reason=ref(''),fund=ref('')
const visibleItems=computed(()=>props.items.filter(t=>!props.approvals||t.status==='pending'||t.confirmations.some(c=>c.status==='pending')))
const fundOptions=computed(()=>props.funds.map(f=>({label:`${f.description||f.id}（${fundStatuses[f.status]}）`,value:f.id})))
async function open(id:string){
  if(busy.value)return
  busy.value=true;error.value=''
  try{detail.value=await warehouse.detail(id);detailShow.value=true;reason.value='';fund.value=''}
  catch(e){error.value=(e as Error).message}
  finally{busy.value=false}
}
async function changed(){emit('changed');if(detail.value)await open(detail.value.id)}
async function run(path:string,body:unknown){
  if(busy.value)return
  busy.value=true;error.value=''
  try{detail.value=await warehouse.action(path,body);emit('changed')}
  catch(e){error.value=(e as Error).message+'。请刷新查看当前记录后再操作。'}
  finally{busy.value=false}
}
function decide(item:StockTransfer,action:string,confirmationId?:string){
  const path=confirmationId?`/stock-confirmations/${confirmationId}/${action}`:`/stock-transfers/${item.id}/${action}`
  run(path,['reject','cancel'].includes(action)?{reason:reason.value}:{})
}
</script>
<template>
  <div class="toolbar"><h2>{{approvals?'货物审批与完成申报':'货物转移记录'}}</h2><NButton @click="emit('changed')">刷新</NButton></div>
  <p class="error">{{error}}</p>
  <div class="table-wrap"><table>
    <thead><tr><th>日期 / 用途</th><th>来源 → 去向</th><th>数量</th><th>货物状态</th><th>资金状态</th><th></th></tr></thead>
    <tbody><tr v-for="t in visibleItems" :key="t.id">
      <td>{{t.effective_date}}<small>{{actions[t.action_kind]}}</small></td>
      <td>{{t.source_location_name}} → {{t.destination_location_name}}</td>
      <td><div v-for="l in t.lines" :key="l.id">{{l.sku_name}}：{{l.quantity}} {{l.unit}}</div></td>
      <td>{{stockStatuses[t.status]}}</td>
      <td><div v-for="f in t.fund_references" :key="f.id">{{fundStatuses[f.status]||f.status}}，¥ {{money(f.amount_minor)}}</div><span v-if="!t.fund_references.length">未关联</span></td>
      <td><NButton :disabled="busy" @click="open(t.id)">详情 / 处理</NButton></td>
    </tr></tbody>
  </table></div>
  <NModal v-model:show="detailShow" preset="card" title="货物转移详情" class="dialog">
    <template v-if="detail">
      <p>{{detail.id}}</p>
      <p>{{detail.source_location_name}} → {{detail.destination_location_name}}，{{stockStatuses[detail.status]}}</p>
      <p>说明：{{detail.description}}；依据：{{detail.basis}}</p>
      <ul><li v-for="l in detail.lines" :key="l.id">{{l.sku_name}}：{{l.quantity}} {{l.unit}}</li></ul>
      <NButton :loading="busy" @click="open(detail.id)">刷新详情</NButton>
      <p class="error">{{error}}</p>
      <template v-if="trusted">
        <label>拒绝 / 取消原因<NInput v-model:value="reason" :disabled="busy"/></label>
        <div class="actions">
          <template v-if="detail.status==='pending'">
            <NButton :disabled="busy" @click="decide(detail,'approve')">批准货物转移</NButton>
            <NButton :disabled="busy||!reason" @click="decide(detail,'reject')">拒绝</NButton>
          </template>
          <NButton v-if="['pending','in_transit'].includes(detail.status)" :disabled="busy||!reason" @click="decide(detail,'cancel')">取消货物转移</NButton>
        </div>
      </template>
      <StockCompletionEditor v-if="detail.status==='in_transit'&&!detail.confirmations.some(c=>c.status==='pending')" :key="detail.id" :item="detail" :trusted="trusted" @changed="changed"/>
      <div v-for="c in detail.confirmations" :key="c.id">
        <h3>完成申报：{{stockStatuses[c.status]||c.status}}</h3>
        <p>申报人 {{c.actor_id}}；日期 {{c.effective_date}}；依据 {{c.basis}}</p>
        <template v-if="trusted&&c.status==='pending'">
          <p>请核对整条转移已实际完成，批准后按上述数量记账。</p>
          <NButton :disabled="busy" @click="decide(detail,'approve',c.id)">批准完成申报</NButton>
          <NButton :disabled="busy||!reason" @click="decide(detail,'reject',c.id)">拒绝完成申报</NButton>
        </template>
      </div>
      <h3>当前关联资金</h3><p>资金与货物独立生效，关联记录不代表已付款。</p>
      <div v-for="f in detail.fund_references" :key="f.id">
        <p>{{f.description||f.id}}：{{fundStatuses[f.status]||f.status}}，¥ {{money(f.amount_minor)}}</p>
        <p v-if="f.claim">垫付声明 ¥ {{money(f.claim.declared_minor)}}；确认 {{f.claim.confirmed_minor===null?'未确认':'¥ '+money(f.claim.confirmed_minor)}}；{{f.claim.basis}}</p>
      </div>
      <template v-if="trusted">
        <label>补充已有资金关联<NSelect v-model:value="fund" :disabled="busy" :options="fundOptions"/></label>
        <NButton :disabled="busy||!fund" @click="run(`/stock-transfers/${detail.id}/fund-references`,{fund_transfer_id:fund})">关联资金记录</NButton>
      </template>
      <details><summary>原批准范围与资金快照</summary><pre>{{JSON.stringify(detail.approval_snapshot,null,2)}}</pre></details>
      <StockAdjustmentEditor v-if="trusted&&detail.status==='completed'" :key="detail.id" :item="detail" :locations="locations" @changed="changed"/>
      <NButton v-if="detail.related_transfer_id" text :disabled="busy" @click="open(detail.related_transfer_id)">查看关联原单 {{detail.related_transfer_id}}</NButton>
      <h3 v-if="detail.adjustments.length">关联盈亏调整</h3>
      <div v-for="a in detail.adjustments" :key="a.id">
        <NButton text :disabled="busy" @click="open(a.id)">{{actions[a.action_kind]}} {{a.id}}，{{stockStatuses[a.status]}}</NButton>
        <p>{{locations.find(l=>l.id===a.source_location_id)?.name||a.source_location_id}} → {{locations.find(l=>l.id===a.destination_location_id)?.name||a.destination_location_id}}</p>
        <p v-for="l in a.lines" :key="l.sku_id">{{detail.lines.find(original=>original.sku_id===l.sku_id)?.sku_name||l.sku_id}}：{{l.quantity}} {{detail.lines.find(original=>original.sku_id===l.sku_id)?.unit}}</p>
      </div>
      <details><summary>操作追溯</summary><pre>{{JSON.stringify(detail.audit,null,2)}}</pre></details>
    </template>
  </NModal>
</template>
