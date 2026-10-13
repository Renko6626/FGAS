<script setup lang="ts">
import {ref,watch,computed} from 'vue'
import {NButton,NInput,NModal,NCheckbox} from 'naive-ui'
import {type Account} from '../api/funds'
import {membersApi,type Member,type ClaimInput} from '../api/memberClaims'
import EndpointSelector from './EndpointSelector.vue'
const props=defineProps<{show:boolean;member:Member;accounts:Account[]}>()
const emit=defineEmits<{close:[];saved:[]}>()
const fresh=():ClaimInput=>({member_id:props.member.id,destination_account_id:'',amount:'',effective_date:new Date().toLocaleDateString('sv-SE'),description:'',basis:'',confirm_now:false})
const form=ref(fresh()),busy=ref(false),error=ref('')
const destination=computed(()=>props.accounts.find(a=>a.id===form.value.destination_account_id))
watch(()=>props.show,show=>{if(show){form.value=fresh();error.value=''}})
async function save(){if(busy.value)return;busy.value=true;error.value='';try{await membersApi.submitClaim({...form.value});emit('saved');emit('close')}catch(e){error.value=(e as Error).message+'。请查看垫付记录后再决定是否重新提交。'}finally{busy.value=false}}
</script>
<template><NModal :show="show" preset="card" title="代录成员垫付" class="dialog" @close="emit('close')"><p>来源：{{member.name}}（{{member.account_id}}）</p><EndpointSelector v-model="form.destination_account_id" :accounts="accounts.filter(a=>a.id!==member.account_id)" label="去向" :disabled="busy"/><p v-if="destination?.is_fund">确认后，{{destination.name}}的资金余额增加。</p><p v-else-if="destination">确认后，{{destination.name}}记入借方，余额按对象类别的正常方向计算。</p><label>申报金额（元）<NInput v-model:value="form.amount" :disabled="busy"/></label><label>业务日期<input v-model="form.effective_date" type="date" :disabled="busy"></label><label>依据<NInput v-model:value="form.basis" :disabled="busy"/></label><label>说明<NInput v-model:value="form.description" :disabled="busy"/></label><NCheckbox v-model:checked="form.confirm_now" :disabled="busy">直接确认全部申报金额</NCheckbox><p v-if="error" class="error">{{error}}</p><div class="actions"><NButton type="primary" :loading="busy" @click="save">保存垫付</NButton></div></NModal></template>
