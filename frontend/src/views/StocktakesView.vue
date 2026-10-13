<script setup lang="ts">
import {ref,watch,onMounted} from 'vue'
import {NButton,NInput,NSelect} from 'naive-ui'
import type {Account,StockAccount,Sku,Transfer,TransferInput} from '../api/funds'
import type {Member} from '../api/funds'
import type {StockTransfer} from '../api/warehouse'
import {stocktakesApi,type StocktakeKind,type Stocktake,type StocktakeDetail} from '../api/stocktakes'
import TransfersView from './TransfersView.vue'
import StockTransfersView from './StockTransfersView.vue'
import TransferEditor from '../components/TransferEditor.vue'
import StockTransferEditor from '../components/StockTransferEditor.vue'
const props=defineProps<{accounts:Account[];locations:StockAccount[];skus:Sku[];funds:Transfer[];members:Member[];trusted:boolean}>()
const emit=defineEmits<{changed:[];notice:[string]}>()
const kind=ref<StocktakeKind>('fund'),items=ref<Stocktake[]>([]),detail=ref<StocktakeDetail|null>(null),busy=ref(false),error=ref(''),name=ref(''),description=ref(''),editDescription=ref('')
const showFund=ref(false),initial=ref<Partial<TransferInput>>({}),stockEditor=ref<InstanceType<typeof StockTransferEditor>|null>(null)
async function load(){error.value='';try{items.value=await stocktakesApi.list(kind.value);if(detail.value){detail.value=await stocktakesApi.detail(kind.value,detail.value.stocktake.id);editDescription.value=detail.value.stocktake.description}}catch(e){error.value=(e as Error).message}}
async function open(item:Stocktake){error.value='';try{detail.value=await stocktakesApi.detail(kind.value,item.id);editDescription.value=detail.value.stocktake.description}catch(e){error.value=(e as Error).message}}
async function run(action:'create'|'description'|'end'){
 if(busy.value)return
 busy.value=true;error.value=''
 try{
  if(action==='create'){const item=await stocktakesApi.create(kind.value,{name:name.value,description:description.value});name.value='';description.value='';await open(item)}
  else if(detail.value){if(action==='end')await stocktakesApi.end(kind.value,detail.value.stocktake.id);else await stocktakesApi.update(kind.value,detail.value.stocktake.id,editDescription.value)}
  await changed()
 }catch(e){error.value=(e as Error).message}finally{busy.value=false}
}
async function changed(){emit('changed');await load()}
function createTransfer(gain:boolean){
 const item=detail.value?.stocktake;if(!item)return
 if(kind.value==='fund'){const fund=props.accounts.find(a=>a.kind==='public')?.id||'';initial.value={source_account_id:gain?item.gain_account_id:fund,destination_account_id:gain?fund:item.loss_account_id};showFund.value=true}
 else stockEditor.value?.open({source_account_id:gain?item.gain_account_id:'',destination_account_id:gain?'':item.loss_account_id,tags:[gain?'盘盈':'盘亏']})
}
watch(kind,()=>{detail.value=null;showFund.value=false;load()})
onMounted(load)
</script>
<template>
 <div class="toolbar"><h2>盘点</h2><NButton :disabled="busy" @click="changed">刷新</NButton></div>
 <label>盘点类别<NSelect v-model:value="kind" :disabled="busy" :options="[{label:'资金盘点',value:'fund'},{label:'货物盘点',value:'stock'}]"/></label>
 <p>通过专属盘盈、盘亏端点登记普通转移。结束盘点后，端点在选择器中默认隐藏，已有记录仍可查看。</p>
 <fieldset v-if="trusted" :disabled="busy"><legend>创建盘点</legend><label>名称<NInput v-model:value="name" :disabled="busy" maxlength="200"/></label><label>说明<NInput v-model:value="description" :disabled="busy" type="textarea"/></label><NButton :loading="busy" :disabled="busy||!name.trim()" @click="run('create')">创建盘点</NButton></fieldset>
 <p v-if="error" class="error">{{error}}</p>
 <div class="table-wrap"><table><thead><tr><th>名称</th><th>状态</th><th>说明</th><th></th></tr></thead><tbody><tr v-for="item in items" :key="item.id"><td>{{item.name}}<small>{{item.id}}</small></td><td>{{item.status==='ended'?'已结束':'进行中'}}</td><td>{{item.description||'—'}}</td><td><NButton :disabled="busy" @click="open(item)">查看</NButton></td></tr></tbody></table></div>
 <p v-if="!items.length">暂无盘点。</p>
 <section v-if="detail"><h3>{{detail.stocktake.name}}（{{detail.stocktake.status==='ended'?'已结束':'进行中'}}）</h3><p>{{detail.stocktake.description||'暂无说明'}}</p>
  <p>盘盈端点：{{detail.stocktake.gain_account_name}}；盘亏端点：{{detail.stocktake.loss_account_name}}</p>
  <template v-if="trusted"><label>修改说明<NInput v-model:value="editDescription" :disabled="busy" type="textarea"/></label><div class="actions"><NButton :disabled="busy" @click="run('description')">保存说明</NButton><NButton v-if="detail.stocktake.status!=='ended'" :disabled="busy" @click="run('end')">结束盘点</NButton></div></template>
  <div class="actions"><NButton :disabled="busy" @click="createTransfer(true)">新建盘盈转移</NButton><NButton :disabled="busy" @click="createTransfer(false)">新建盘亏转移</NButton></div>
  <TransfersView v-if="kind==='fund'" :key="detail.stocktake.id" :items="detail.transfers as Transfer[]" :accounts="accounts" :approvals="false" :trusted="trusted" @changed="changed" @notice="emit('notice',$event)"/>
  <StockTransfersView v-else :key="detail.stocktake.id" :items="detail.transfers as StockTransfer[]" :locations="locations" :funds="funds" :trusted="trusted" :skus="skus" :accounts="accounts" @changed="changed"/>
 </section>
 <TransferEditor :show="showFund" :accounts="accounts" :initial="initial" @close="showFund=false" @saved="changed"/>
 <StockTransferEditor ref="stockEditor" hide-trigger :locations="locations" :skus="skus" :accounts="accounts" :funds="funds" @saved="changed"/>
</template>
