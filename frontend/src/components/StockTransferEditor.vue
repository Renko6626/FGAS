<script setup lang="ts">
import {ref} from 'vue'
import {NButton,NInput,NModal,NSelect,NCheckbox} from 'naive-ui'
import type {Location,Sku,Account,Transfer} from '../api/funds'
import type {Member} from '../api/memberClaims'
import {warehouse,actions,today,type StockInput,type OperationInput} from '../api/warehouse'
import EndpointSelector from './EndpointSelector.vue'
const props=defineProps<{locations:Location[];skus:Sku[];accounts:Account[];funds:Transfer[];members:Member[];trusted:boolean}>(),emit=defineEmits<{saved:[]}>()
const show=ref(false),busy=ref(false),error=ref('')
const source=ref(''),destination=ref(''),action=ref('internal'),date=ref(today()),description=ref(''),basis=ref(''),reference=ref(''),refs=ref<string[]>([]),lines=ref([{sku_id:'',quantity:''}])
const moneyMode=ref('none'),moneySource=ref(''),moneyDestination=ref(''),amount=ref(''),member=ref(''),moneyBasis=ref(''),confirm=ref(false),confirmed=ref(''),reason=ref('')
function open(){error.value='';source.value='';destination.value='';action.value='internal';date.value=today();basis.value='';description.value='';reference.value='';refs.value=[];lines.value=[{sku_id:'',quantity:''}];moneyMode.value='none';moneySource.value='';moneyDestination.value='';amount.value='';member.value='';moneyBasis.value='';confirm.value=false;confirmed.value='';reason.value='';show.value=true}
async function save() {
  if(busy.value)return
  error.value=''
  if(lines.value.some(l=>!l.sku_id||!/^[0-9]+$/.test(l.quantity)||BigInt(l.quantity)===0n)){error.value='请选择 SKU 并填写正整数数量';return}
  busy.value=true
  try {
    const stock:StockInput={source_location_id:source.value,destination_location_id:destination.value,action_kind:action.value,effective_date:date.value,description:description.value,basis:basis.value,source_reference:reference.value||null,fund_transfer_ids:moneyMode.value==='none'?[...refs.value]:[],lines:lines.value.map(l=>({...l}))}
    if(moneyMode.value==='none')await warehouse.submit(stock)
    else {
      const money:OperationInput['money']=moneyMode.value==='fund_transfer'
        ? {kind:'fund_transfer',data:{source_account_id:moneySource.value,destination_account_id:moneyDestination.value,amount:amount.value,effective_date:date.value,description:description.value,counterparty:null}}
        : {kind:'member_claim',data:{member_id:member.value,destination_account_id:moneyDestination.value,amount:amount.value,effective_date:date.value,description:description.value,basis:moneyBasis.value,confirm_now:confirm.value,...(confirm.value?{confirmed_amount:confirmed.value,confirmation_reason:reason.value}:{})}}
      await warehouse.operation({stock,money})
    }
    show.value=false
    emit('saved')
  }catch(e){error.value=(e as Error).message+'。结果不确定时，请先刷新查看货物和资金记录，再操作。'}
  finally{busy.value=false}
}
</script>
<template><NButton type="primary" @click="open">新建货物转移</NButton><NModal v-model:show="show" :mask-closable="false" preset="card" title="新建货物转移" class="dialog"><fieldset :disabled="busy" style="border:0;padding:0"><label>来源<NSelect :disabled="busy" v-model:value="source" :options="locations.filter(l=>l.active).map(l=>({label:l.name,value:l.id}))"/></label><label>去向<NSelect :disabled="busy" v-model:value="destination" :options="locations.filter(l=>l.active).map(l=>({label:l.name,value:l.id}))"/></label><label>用途<NSelect :disabled="busy" v-model:value="action" :options="Object.entries(actions).map(([value,label])=>({value,label}))"/></label><label>日期<NInput :disabled="busy" v-model:value="date" placeholder="YYYY-MM-DD"/></label><label>说明<NInput :disabled="busy" v-model:value="description"/></label><label>依据<NInput :disabled="busy" v-model:value="basis"/></label><label>外部单据编号<NInput :disabled="busy" v-model:value="reference"/></label><div v-for="(line,i) in lines" :key="i" class="filters"><NSelect :disabled="busy" v-model:value="line.sku_id" :options="skus.filter(s=>s.active).map(s=>({label:`${s.name}（${s.unit}）`,value:s.id}))" placeholder="SKU"/><NInput :disabled="busy" v-model:value="line.quantity" placeholder="正整数数量"/><NButton :disabled="busy||lines.length===1" @click="lines.splice(i,1)">删除</NButton></div><NButton :disabled="busy" @click="lines.push({sku_id:'',quantity:''})">增加 SKU</NButton><label>资金关联方式<NSelect :disabled="busy" v-model:value="moneyMode" :options="[{label:'选择已有资金记录或不关联',value:'none'},{label:'同时新建资金划转',value:'fund_transfer'},...(trusted?[{label:'同时登记成员垫付',value:'member_claim'}]:[])]"/></label><label v-if="moneyMode==='none'">已有资金记录<NSelect :disabled="busy" v-model:value="refs" multiple clearable :options="funds.map(f=>({label:`${f.description||f.id}（${f.status}）`,value:f.id}))"/></label><template v-else><p>资金先按资金规则过账或等待审批；货物须单独审批和确认完成。取消货物不会撤销资金。</p><EndpointSelector v-if="moneyMode==='fund_transfer'" :disabled="busy" v-model="moneySource" :accounts="accounts" label="资金来源（贷方）"/><label v-else>垫付成员（贷方为成员往来账户）<NSelect :disabled="busy" v-model:value="member" :options="members.map(m=>({label:m.name,value:m.id}))"/></label><EndpointSelector :disabled="busy" v-model="moneyDestination" :accounts="accounts" label="资金去向（借方）"/><label>金额（元）<NInput :disabled="busy" v-model:value="amount"/></label><template v-if="moneyMode==='member_claim'"><label>垫付依据<NInput :disabled="busy" v-model:value="moneyBasis"/></label><NCheckbox :disabled="busy" v-model:checked="confirm">立即确认垫付金额</NCheckbox><template v-if="confirm"><label>确认金额（元）<NInput :disabled="busy" v-model:value="confirmed"/></label><label>部分确认原因<NInput :disabled="busy" v-model:value="reason"/></label></template></template></template></fieldset><p v-if="error" class="error">{{error}}</p><NButton :loading="busy" @click="save">提交</NButton></NModal></template>
