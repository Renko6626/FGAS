<script setup lang="ts">
import {computed,ref,watch} from 'vue'
import {NButton,NCheckbox,NInput,NModal,NSelect} from 'naive-ui'
import {api,kinds,statuses,type Account,type TransferInput} from '../api/funds'
import AccountAvatar from './AccountAvatar.vue'
import TagInput from './TagInput.vue'

const props=defineProps<{show:boolean;accounts:Account[];opening?:boolean;initial?:Partial<TransferInput>}>()
const emit=defineEmits<{close:[];saved:[string]}>()
const fresh=():TransferInput=>({
  source_account_id:props.opening?(props.accounts.find(a=>a.id==='opening')?.id||''):'',
  destination_account_id:props.opening?(props.accounts.find(a=>a.kind==='public'&&a.active)?.id||''):'',
  amount:'',effective_date:new Date().toLocaleDateString('sv-SE'),
  description:props.opening?'期初资金':'',counterparty:null,tags:[],...props.initial
})
const form=ref<TransferInput>(fresh()),error=ref(''),busy=ref(false)
const selecting=ref<'source'|'destination'|null>(null)
const category=ref<string|null>(null),tag=ref<string|null>(null),search=ref(''),showEnded=ref(false)
const source=computed(()=>props.accounts.find(a=>a.id===form.value.source_account_id))
const destination=computed(()=>props.accounts.find(a=>a.id===form.value.destination_account_id))
const selectedId=computed(()=>selecting.value==='source'?form.value.source_account_id:form.value.destination_account_id)
const tagOptions=computed(()=>[...new Set(props.accounts.filter(a=>a.active).flatMap(a=>a.tags))].map(value=>({label:value,value})))
const options=computed(()=>{
  const query=search.value.trim().toLocaleLowerCase()
  return props.accounts.filter(a=>a.active&&(showEnded.value||a.stocktake?.status!=='ended')
    &&(!category.value||a.kind===category.value)&&(!tag.value||a.tags.includes(tag.value))
    &&(!query||[a.name,a.member_name||'',...a.tags].some(value=>value.toLocaleLowerCase().includes(query))))
})
const ready=computed(()=>!!source.value&&!!destination.value&&source.value.id!==destination.value.id&&/^\d+(?:\.\d{1,2})?$/.test(form.value.amount)&&Number(form.value.amount)>0)
watch(()=>props.show,value=>{
  if(value){form.value=fresh();error.value=''}
  else selecting.value=null
})
function openPicker(side:'source'|'destination'){
  if(busy.value)return
  category.value=null;tag.value=null;search.value='';showEnded.value=false;selecting.value=side
}
function choose(account:Account){
  if(selecting.value==='source')form.value.source_account_id=account.id
  else form.value.destination_account_id=account.id
  selecting.value=null
}
function close(){if(!busy.value)emit('close')}
async function submit(){
  if(busy.value||!ready.value)return
  busy.value=true;error.value=''
  try{
    const result=await api.submit({...form.value,tags:[...form.value.tags]})
    emit('saved',statuses[result.status]||result.status)
    emit('close')
  }catch(e){error.value=(e as Error).message+'。请查看流水记录后再决定是否重新提交。'}
  finally{busy.value=false}
}
</script>

<template>
  <NModal :show="show" preset="card" :title="opening?'登记期初资金':'资金转移'" class="transfer-dialog" :style="{width:'600px',maxWidth:'calc(100vw - 32px)',maxHeight:'calc(100dvh - 32px)'}" :header-style="{padding:'20px 24px 16px',borderBottom:'1px solid #d9e2ed'}" :content-style="{padding:'20px 24px',maxHeight:'calc(100dvh - 112px)',overflowY:'auto'}" :closable="!busy" :mask-closable="!busy" :close-on-esc="!busy" @close="close" @update:show="value=>{if(!value)close()}">
    <div class="transfer-route">
      <div class="route-account">
        <span class="route-label">来源</span>
        <button class="account-face" type="button" :disabled="busy" aria-label="选择来源账户" @click="openPicker('source')">
          <AccountAvatar v-if="source" :name="source.name" :url="source.avatar_url"/>
          <span v-else class="empty-avatar" aria-hidden="true">＋</span>
          <strong>{{source?.name||'选择来源'}}</strong>
        </button>
        <NButton text :disabled="busy" @click="openPicker('source')">{{source?'更换账户':'选择账户'}}</NButton>
      </div>
      <div class="route-amount">
        <label for="transfer-amount">金额（元）</label>
        <NInput v-model:value="form.amount" :disabled="busy" placeholder="0.00" :input-props="{id:'transfer-amount',inputmode:'decimal','aria-label':'转移金额（元）'}"/>
        <span class="route-arrow" aria-label="从来源转向去向">⟶</span>
      </div>
      <div class="route-account">
        <span class="route-label">去向</span>
        <button class="account-face" type="button" :disabled="busy" aria-label="选择去向账户" @click="openPicker('destination')">
          <AccountAvatar v-if="destination" :name="destination.name" :url="destination.avatar_url"/>
          <span v-else class="empty-avatar" aria-hidden="true">＋</span>
          <strong>{{destination?.name||'选择去向'}}</strong>
        </button>
        <NButton text :disabled="busy" @click="openPicker('destination')">{{destination?'更换账户':'选择账户'}}</NButton>
      </div>
    </div>
    <p v-if="source&&destination&&source.id===destination.id" class="error">来源与去向需要不同。</p>
    <section class="transfer-details" aria-labelledby="transfer-details-title">
      <h3 id="transfer-details-title">转移信息</h3>
      <fieldset :disabled="busy">
        <div class="form-row">
          <label class="form-field">业务日期<input v-model="form.effective_date" type="date"></label>
          <label class="form-field">往来方<span class="optional">可选</span><NInput :value="form.counterparty||''" :disabled="busy" placeholder="姓名或单位" @update:value="form.counterparty=$event||null"/></label>
        </div>
        <label class="form-field">说明<span class="optional">可选</span><NInput v-model:value="form.description" type="textarea" :autosize="{minRows:2,maxRows:4}" :disabled="busy" placeholder="这笔钱用来做什么"/></label>
        <label class="form-field">标签<TagInput v-model="form.tags" :disabled="busy"/></label>
      </fieldset>
    </section>
    <p v-if="error" class="error" role="alert">{{error}}</p>
    <div class="transfer-submit"><NButton type="primary" size="large" :loading="busy" :disabled="busy||!ready" @click="submit">保存转移</NButton></div>
  </NModal>

  <NModal :show="!!selecting&&show" preset="card" :title="selecting==='source'?'选择来源账户':'选择去向账户'" class="account-picker-dialog" :style="{width:'620px',maxWidth:'calc(100vw - 32px)',maxHeight:'calc(100dvh - 32px)'}" :header-style="{padding:'20px 24px 16px',borderBottom:'1px solid #d9e2ed'}" :content-style="{padding:'20px 24px',maxHeight:'calc(100dvh - 112px)',overflowY:'auto'}" @close="selecting=null" @update:show="value=>{if(!value)selecting=null}">
    <div class="picker-categories" aria-label="按账户类型筛选">
      <NButton :type="category===null?'primary':'default'" @click="category=null">全部</NButton>
      <NButton v-for="(label,value) in kinds" :key="value" :type="category===value?'primary':'default'" @click="category=value">{{label}}</NButton>
    </div>
    <div class="picker-filters">
      <NInput v-model:value="search" clearable placeholder="搜索名称或联系人" :input-props="{'aria-label':'搜索账户'}"/>
      <NSelect v-model:value="tag" clearable :options="tagOptions" placeholder="所有标签"/>
    </div>
    <div v-if="options.length" class="picker-grid">
      <button v-for="account in options" :key="account.id" type="button" class="picker-account" :class="{selected:account.id===selectedId}" :aria-pressed="account.id===selectedId" @click="choose(account)">
        <AccountAvatar :name="account.name" :url="account.avatar_url"/>
        <strong>{{account.name}}</strong>
        <span>{{kinds[account.kind]}}</span>
      </button>
    </div>
    <p v-else class="picker-empty">没有符合条件的账户，试试其他分类或清空筛选。</p>
    <NCheckbox v-model:checked="showEnded" class="picker-ended">显示已结束盘点账户</NCheckbox>
  </NModal>
</template>

<style scoped>
.transfer-route{display:grid;grid-template-columns:minmax(0,1fr) 140px minmax(0,1fr);gap:16px;align-items:center;padding:0 0 22px}
.route-account{display:flex;align-items:center;flex-direction:column;gap:10px;min-width:0;padding:14px 10px 12px;background:#f8fafc;border:1px solid #cdd8e5;border-radius:10px}
.route-label{font-size:12px;font-weight:600;color:#65768b}
.account-face{border:0;background:transparent;padding:2px;cursor:pointer;display:flex;flex-direction:column;align-items:center;gap:12px;color:#203044;width:100%;border-radius:6px;font:inherit}
.account-face strong{font-size:15px;line-height:1.45;overflow-wrap:anywhere;min-height:22px}
.account-face:focus-visible,.picker-account:focus-visible{outline:2px solid #15559a;outline-offset:3px}
.account-face:disabled{cursor:default;opacity:.65}
.account-face :deep(.account-avatar),.empty-avatar{width:64px;height:64px;margin:0;font-size:26px}
.empty-avatar{display:inline-flex;align-items:center;justify-content:center;background:#fff;color:#8798ad;border:1px dashed #adbed2;border-radius:50%;font-weight:300}
.route-amount{text-align:center;min-width:0}
.route-amount label{font-size:12px;font-weight:600;color:#65768b;margin:0 0 8px}
.route-amount :deep(.n-input){background:#fff;--n-border:1px solid #b9cbe0!important;--n-border-radius:8px!important}
.route-amount :deep(.n-input__input-el){text-align:center;font-size:24px;font-weight:600;font-variant-numeric:tabular-nums;height:46px}
.route-arrow{display:block;font-size:44px;line-height:1.15;color:#51749b;margin-top:8px}
.transfer-details{border-top:1px solid #cdd8e5;padding-top:18px;color:#203044;font-size:14px}
.transfer-details h3{font-size:14px;font-weight:600;margin:0 0 14px;color:#405670}
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.form-field{margin:0 0 16px;font-size:13px;font-weight:500;color:#405670}
.form-field :deep(.n-input),.form-field :deep(.n-select){margin-top:7px;font-weight:400;--n-border:1px solid #cdd8e5!important;--n-border-radius:6px!important}
.optional{color:#8897a9;font-size:12px;font-weight:400;margin-left:6px}
.form-field input[type=date]{width:100%;height:36px;border:1px solid #cdd8e5;border-radius:6px;background:#fff;color:#203044;margin-top:7px;padding:6px 10px;outline:none;font-size:14px}
.form-field input[type=date]:focus{border-color:#15559a;box-shadow:0 0 0 2px #e6eef8}
.transfer-submit{display:flex;justify-content:flex-end;border-top:1px solid #cdd8e5;padding-top:16px;margin-top:2px}
.transfer-submit .n-button{min-width:150px}
.picker-categories{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 16px;padding-bottom:16px;border-bottom:1px solid #d9e2ed}
.picker-filters{display:grid;grid-template-columns:1fr 160px;gap:10px;margin-bottom:18px}
.picker-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;max-height:48vh;overflow:auto;padding:3px}
.picker-account{position:relative;display:flex;flex-direction:column;align-items:center;justify-content:flex-start;gap:9px;padding:18px 8px 14px;border:1px solid #cdd8e5;border-radius:8px;background:#fff;color:#203044;cursor:pointer;font:inherit;min-width:0}
.picker-account:hover{background:#f4f8fc;border-color:#7d9bbf}
.picker-account.selected{border:2px solid #15559a;padding:17px 7px 13px;background:#edf5ff}
.picker-account.selected::after{content:'✓';position:absolute;top:6px;right:8px;color:#15559a;font-size:13px;font-weight:700}
.picker-account :deep(.account-avatar){width:50px;height:50px;margin:0;font-size:21px}
.picker-account strong{font-size:14px;line-height:1.5;overflow-wrap:anywhere}
.picker-account>span{font-size:12px;color:#687789}
.picker-empty{padding:32px 12px;text-align:center;color:#687789;border:1px dashed #cdd8e5;border-radius:8px}
.picker-ended{margin-top:18px}
@media(max-width:480px){.transfer-route{grid-template-columns:minmax(0,1fr) 100px minmax(0,1fr);gap:8px;padding-bottom:18px}.route-account{padding:12px 6px;gap:8px}.account-face :deep(.account-avatar),.empty-avatar{width:52px;height:52px;font-size:22px}.account-face strong{font-size:13px}.route-amount :deep(.n-input__input-el){font-size:20px}.form-row{grid-template-columns:1fr;gap:0}.picker-grid{grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.picker-filters{grid-template-columns:1fr}}
</style>
