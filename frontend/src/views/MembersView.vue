<script setup lang="ts">
import {ref} from 'vue'
import {NButton,NInput,NModal} from 'naive-ui'
import type {Account,StockAccount} from '../api/accounts'
import {membersApi,type Member} from '../api/members'
const props=defineProps<{members:Member[];accounts:Account[];locations:StockAccount[];trusted:boolean}>()
const emit=defineEmits<{changed:[]}>()
const show=ref(false),id=ref(''),name=ref(''),note=ref(''),error=ref(''),busy=ref(false)
function edit(m?:Member){id.value=m?.code||'';name.value=m?.name||'';note.value=m?.note||'';error.value='';show.value=true}
async function save(){if(busy.value)return;busy.value=true;try{if(id.value)await membersApi.update(id.value,{name:name.value,note:note.value});else await membersApi.create({name:name.value,note:note.value});show.value=false;emit('changed')}catch(e){error.value=(e as Error).message}finally{busy.value=false}}
</script>
<template><div class="toolbar"><h2>成员与联系人</h2><NButton v-if="trusted" @click="edit()">新增成员</NButton></div><div class="table-wrap"><table><thead><tr><th>姓名</th><th>备注</th><th>关联资金账户</th><th>关联货物账户</th><th></th></tr></thead><tbody><tr v-for="m in props.members" :key="m.code"><td>{{m.name}}<small>{{m.code}}</small></td><td>{{m.note}}</td><td>{{accounts.filter(a=>a.member_code===m.code).map(a=>a.name).join('，')||'无'}}</td><td>{{locations.filter(a=>a.member_code===m.code).map(a=>a.name).join('，')||'无'}}</td><td><NButton v-if="trusted" @click="edit(m)">编辑</NButton></td></tr></tbody></table></div><NModal v-model:show="show" preset="card" title="成员资料" class="dialog"><label>姓名<NInput v-model:value="name"/></label><label>备注和联系方式<NInput v-model:value="note" type="textarea"/></label><p class="error">{{error}}</p><NButton :loading="busy" @click="save">保存</NButton></NModal></template>
