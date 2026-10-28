<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { NButton, NCheckbox, NInput, NModal, NSelect } from 'naive-ui'
import type { User } from '../api/auth'
import { agentConnections, type AgentConnection, type ConnectionInput } from '../api/agentConnections'
import StatusHint from '../components/StatusHint.vue'
const props = defineProps<{user:User}>()
const items=ref<AgentConnection[]>([]), busy=ref(false), error=ref(''), notice=ref('')
const show=ref(false), editing=ref<AgentConnection|null>(null), name=ref(''), level=ref<'low'|'high'>('low'), expiry=ref(''), active=ref(true)
const secret=ref(''), secretShow=ref(false)
let disposed=false
const mcpAddress=new URL('/mcp',window.location.origin).href
const canHigh=computed(()=>props.user.role==='admin'||props.user.role==='trusted')
const levels=computed(()=>[{label:'低权限（提交待审申请）',value:'low'},...(canHigh.value?[{label:'高权限（明确确认后直接办理）',value:'high'}]:[])])
function clearSecret(){secret.value='';secretShow.value=false}
watch(secretShow,value=>{if(!value)secret.value=''})
onBeforeUnmount(()=>{disposed=true;clearSecret()})
async function load(){const actor=props.user.id;busy.value=true;error.value='';try{const result=await agentConnections.list();if(!disposed && actor===props.user.id)items.value=result}catch(e){if(!disposed && actor===props.user.id)error.value=(e as Error).message}finally{busy.value=false}}
watch(()=>[props.user.id,props.user.role],()=>{clearSecret();show.value=false;items.value=[];load()},{immediate:true})
function open(item?:AgentConnection){clearSecret();editing.value=item||null;name.value=item?.name||`${props.user.display_name}的 AI`;level.value=canHigh.value?item?.level||'low':'low';active.value=item?.active??true;expiry.value=item?.expires_at?localDate(item.expires_at):'';error.value='';show.value=true}
function localDate(value:string){const date=new Date(value);return new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16)}
async function save(){if(busy.value)return;const actor=props.user.id;busy.value=true;error.value='';try{const body:ConnectionInput={name:name.value.trim(),level:level.value,expires_at:expiry.value?new Date(expiry.value).toISOString():null};if(editing.value)await agentConnections.update(editing.value.id,{...body,active:active.value});else{const result=await agentConnections.create(body);if(!disposed && actor===props.user.id){secret.value=result.secret;secretShow.value=true}}if(disposed || actor!==props.user.id)return;show.value=false;notice.value=editing.value?'连接已保存':'连接已创建';await load()}catch(e){if(!disposed && actor===props.user.id)error.value=(e as Error).message}finally{busy.value=false}}
async function disable(item:AgentConnection){busy.value=true;error.value='';try{await agentConnections.update(item.id,{active:false});await load()}catch(e){error.value=(e as Error).message}finally{busy.value=false}}
async function reveal(item:AgentConnection){if(busy.value)return;clearSecret();const actor=props.user.id;busy.value=true;error.value='';try{const result=await agentConnections.secret(item.id);if(!disposed && actor===props.user.id){secret.value=result.secret;secretShow.value=true}}catch(e){if(!disposed && actor===props.user.id)error.value=(e as Error).message}finally{busy.value=false}}
async function copy(value:string){try{await navigator.clipboard.writeText(value);notice.value='已复制'}catch{error.value='复制失败，请手动选择并复制。'}}
function date(value:string|null){return value?new Date(value).toLocaleString('zh-CN'):'不过期'}
</script>
<template>
  <div class="page-toolbar"><span class="page-count">{{ items.length }} 个连接</span><StatusHint label="连接权限" text="个人 Agent 连接属于你的登录账号，可读取业务资料，并提交资金转移、货物转移和完成报告。低权限连接的写申请统一等待人工审批，即使你本人有审批权限也一样。自己的密钥可以在这里再次查看。" /><div class="page-tools"><NButton size="small" :disabled="busy" @click="load">刷新</NButton><NButton size="small" type="primary" :disabled="busy" @click="open()">新建连接</NButton></div></div>
  <p v-if="error" class="error" role="alert">{{error}}</p><p v-if="notice" role="status">{{notice}}</p>
  <div class="table-wrap compact-table"><table><thead><tr><th>名称</th><th>所属用户</th><th>等级</th><th>状态</th><th>到期时间</th><th></th></tr></thead><tbody>
    <tr v-for="item in items" :key="item.id"><td>{{item.name}}</td><td>{{item.owner_name||item.owner_user_id}}</td><td>{{item.level==='high'?'高权限':'低权限'}}</td><td>{{item.active?'已启用':'已停用'}}</td><td>{{date(item.expires_at)}}</td><td><div class="table-actions"><template v-if="item.owner_user_id===user.id"><NButton size="small" :disabled="busy" @click="reveal(item)">查看密钥</NButton><NButton size="small" :disabled="busy" @click="open(item)">编辑</NButton></template><NButton v-else-if="user.role==='admin' && item.active" size="small" :disabled="busy" @click="disable(item)">停用</NButton></div></td></tr>
    <tr v-if="!items.length"><td colspan="6">暂无连接</td></tr>
  </tbody></table></div>
  <NModal v-model:show="show" preset="card" class="dialog" :title="editing?'编辑连接':'新建连接'" :mask-closable="!busy" :closable="!busy" :close-on-esc="!busy">
    <div class="connection-form"><label>名称<NInput v-model:value="name" :maxlength="200" :disabled="busy"/></label><label v-if="canHigh">权限等级<NSelect v-model:value="level" :options="levels" :disabled="busy"/></label>
    <p v-else>个人连接固定为低权限，提交的申请由受信任用户或管理员审批。</p>
    <p v-if="level==='high'">高权限连接可直接办理业务、批准申请并维护目录。Agent 应先说明具体操作并获得你的明确确认。</p>
    <p v-if="editing?.level==='high' && !canHigh">当前身份只能将此连接降为低权限后保存。</p>
    <label>到期时间（留空表示不过期）<input v-model="expiry" type="datetime-local" :disabled="busy"/></label><NCheckbox v-if="editing" v-model:checked="active" :disabled="busy">启用连接</NCheckbox>
    <p v-if="error" class="error">{{error}}</p><NButton type="primary" :loading="busy" :disabled="busy||!name.trim()" @click="save">保存</NButton></div>
  </NModal>
  <NModal v-model:show="secretShow" preset="card" title="连接密钥" class="dialog">
    <p>将密钥保存在 Agent 客户端的认证配置中。需要时可回到连接列表再次查看。</p>
    <label>密钥<NInput :value="secret" readonly/></label><NButton @click="copy(secret)">复制密钥</NButton>
    <p>将以下地址配置为 MCP 服务地址，使用 Bearer 密钥认证。</p><NInput :value="mcpAddress" readonly/><NButton @click="copy(mcpAddress)">复制 /mcp 地址</NButton>
    <p v-if="error" class="error">{{error}}</p><div class="actions"><NButton @click="clearSecret">关闭密钥显示</NButton></div>
  </NModal>
</template>
<style scoped>
.connection-form{display:grid;gap:16px}.connection-form label{display:grid;gap:8px}.connection-form input{padding:8px;font:inherit}.actions{margin-top:12px}
</style>
