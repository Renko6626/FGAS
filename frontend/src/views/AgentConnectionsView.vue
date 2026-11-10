<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { NButton, NCheckbox, NInput, NModal, NSelect } from 'naive-ui'
import type { User } from '../api/auth'
import { agentConnections, type AgentConnection, type ConnectionInput } from '../api/agentConnections'
const props = defineProps<{user:User}>()
const items=ref<AgentConnection[]>([]), busy=ref(false), error=ref(''), notice=ref('')
const show=ref(false), editing=ref<AgentConnection|null>(null), name=ref(''), level=ref<'low'|'high'>('low'), expiry=ref(''), active=ref(true)
const secret=ref(''), secretShow=ref(false), secretConnection=ref<AgentConnection|null>(null)
let disposed=false
const mcpAddress=new URL('/mcp',window.location.origin).href
const setupAddress=new URL('/agent-setup.md',window.location.origin).href
const canHigh=computed(()=>props.user.role==='admin'||props.user.role==='trusted')
const levels=computed(()=>[{label:'提交申请，需审批（low）',value:'low'},...(canHigh.value?[{label:'可直接办理，须先确认（high）',value:'high'}]:[])])
function clearSecret(){secret.value='';secretConnection.value=null;secretShow.value=false}
function connectionStatus(item:AgentConnection){
  if(!item.active)return '已停用'
  if(item.expires_at && new Date(item.expires_at).getTime()<=Date.now())return '已过期'
  if(item.owner_user_id===props.user.id && item.level==='high' && !canHigh.value)return '当前身份无权使用'
  return '已启用'
}
const setupText=computed(()=>secret.value ? `请帮我把 FGAS 接入当前 Agent 客户端，先阅读接入指南：
${setupAddress}

MCP 服务地址：${mcpAddress}
传输方式：Streamable HTTP
认证请求头：Authorization: Bearer ${secret.value}

请使用当前客户端的原生 MCP 接入方式，只添加或更新 FGAS 连接，保留其他设置。沿用当前模型，不需要另外配置模型 API Key。
配置后用原生 FGAS 工具查询 me，核对真实用户、连接名称和权限，再做一次只读查询，并向我报告结果。
这次只配置和检查连接，不创建测试账目，不提交或直接办理业务。之后的业务另行确认；不要自动升级权限。
密钥只保存到客户端的认证配置中，不在回复或业务参数中重复展示。` : '')
watch(secretShow,value=>{if(!value){secret.value='';secretConnection.value=null}})
onBeforeUnmount(()=>{disposed=true;clearSecret()})
async function load(){const actor=props.user.id;busy.value=true;error.value='';try{const result=await agentConnections.list();if(!disposed && actor===props.user.id)items.value=result}catch(e){if(!disposed && actor===props.user.id)error.value=(e as Error).message}finally{busy.value=false}}
watch(()=>[props.user.id,props.user.role],()=>{clearSecret();show.value=false;items.value=[];load()},{immediate:true})
function open(item?:AgentConnection){clearSecret();notice.value='';editing.value=item||null;name.value=item?.name||`${props.user.display_name}的 AI`;level.value=canHigh.value?item?.level||'low':'low';active.value=item?.active??true;expiry.value=item?.expires_at?localDate(item.expires_at):'';error.value='';show.value=true}
function localDate(value:string){const date=new Date(value);return new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16)}
async function save(){if(busy.value)return;const actor=props.user.id;busy.value=true;error.value='';try{const body:ConnectionInput={name:name.value.trim(),level:level.value,expires_at:expiry.value?new Date(expiry.value).toISOString():null};if(editing.value)await agentConnections.update(editing.value.id,{...body,active:active.value});else{const result=await agentConnections.create(body);if(!disposed && actor===props.user.id){secret.value=result.secret;secretConnection.value=result.credential;secretShow.value=true}}if(disposed || actor!==props.user.id)return;show.value=false;notice.value=editing.value?'连接已保存':'连接已创建';await load()}catch(e){if(!disposed && actor===props.user.id)error.value=(e as Error).message}finally{busy.value=false}}
async function disable(item:AgentConnection){busy.value=true;error.value='';try{await agentConnections.update(item.id,{active:false});await load()}catch(e){error.value=(e as Error).message}finally{busy.value=false}}
async function reveal(item:AgentConnection){if(busy.value)return;clearSecret();notice.value='';const actor=props.user.id;busy.value=true;error.value='';try{const result=await agentConnections.secret(item.id);if(!disposed && actor===props.user.id){secret.value=result.secret;secretConnection.value=item;secretShow.value=true}}catch(e){if(!disposed && actor===props.user.id)error.value=(e as Error).message}finally{busy.value=false}}
async function copy(value:string,label='内容'){if(!value)return;error.value='';try{await navigator.clipboard.writeText(value);notice.value=`${label}已复制`}catch{error.value='复制失败，请展开手动配置并选择所需内容复制。'}}
function date(value:string|null){return value?new Date(value).toLocaleString('zh-CN'):'不过期'}
</script>
<template>
  <section class="connection-guide" aria-labelledby="connection-guide-title">
    <h2 id="connection-guide-title">让你常用的 Agent 连接 FGAS</h2>
    <p>继续使用外部 Agent 自己的模型，在对话中查询账目、库存或提交申请。无需配置网页助手的模型 Key。</p>
    <ol class="connection-steps">
      <li><strong>创建本人连接</strong><p>默认可查询资料、提交待审批申请。已有连接可以直接使用。</p></li>
      <li><strong>把接入说明交给 Agent</strong><p>点击“接入配置”，复制包含地址和密钥的说明，粘贴给你要使用的 Agent。</p></li>
      <li><strong>核对身份和权限</strong><p>让 Agent 报告连接到的用户及权限，并做一次只读查询。无需新建测试账目。</p></li>
    </ol>
    <a :href="setupAddress" target="_blank" rel="noopener">查看完整接入指南</a>
  </section>
  <div class="page-toolbar"><span class="page-count">{{ items.length }} 个连接{{ user.role==='admin' ? '（含其他成员）' : '' }}</span><div class="page-tools"><NButton size="small" :disabled="busy" @click="load">刷新</NButton><NButton size="small" type="primary" :disabled="busy" @click="open()">创建连接</NButton></div></div>
  <p class="connection-note">“已启用”是连接的开关状态，仍需由 Agent 核对实际身份、权限和连通情况。本人连接关联你的登录账号；停用后将无法继续访问。</p>
  <p v-if="error" class="error" role="alert">{{error}}</p><p v-if="notice" role="status">{{notice}}</p>
  <div class="table-wrap compact-table responsive-table"><table><thead><tr><th>名称</th><th>所属用户</th><th>办事权限</th><th>状态</th><th>到期时间</th><th></th></tr></thead><tbody>
    <tr v-for="item in items" :key="item.id"><td class="table-primary">{{item.name}}</td><td data-label="所属用户">{{item.owner_name||item.owner_user_id}}</td><td class="table-priority" data-label="办事权限">{{item.level==='high'?'可直接办理，须先确认':'提交申请，需审批'}}<small class="connection-level">{{item.level}}</small></td><td class="table-priority" data-label="状态">{{connectionStatus(item)}}</td><td class="table-wide" data-label="到期时间">{{date(item.expires_at)}}</td><td class="table-actions-cell"><div class="table-actions"><template v-if="item.owner_user_id===user.id"><NButton size="small" :disabled="busy" @click="reveal(item)">接入配置</NButton><NButton size="small" :disabled="busy" @click="open(item)">编辑</NButton></template><NButton v-else-if="user.role==='admin' && item.active" size="small" :disabled="busy" @click="disable(item)">停用</NButton></div></td></tr>
    <tr v-if="!items.length"><td class="table-empty" colspan="6">{{busy?'正在读取连接…':'还没有连接。创建一个后，就可以把接入说明交给 Agent。'}}</td></tr>
  </tbody></table></div>
  <NModal v-model:show="show" preset="card" class="dialog" :title="editing?'编辑连接':'新建连接'" :mask-closable="!busy" :closable="!busy" :close-on-esc="!busy">
    <div class="connection-form"><label>连接名称<NInput v-model:value="name" :maxlength="200" :disabled="busy" placeholder="例如：我的电脑助手"/></label><p class="connection-note">名称用于区分不同客户端，业务记录也会保留连接来源。</p><label v-if="canHigh">助手的办事权限<NSelect v-model:value="level" :options="levels" :disabled="busy"/></label>
    <p v-if="level==='low'">可查询业务资料，提交资金、货物和完成报告申请。即使你本人有审批权限，这个连接提交的申请也仍需审批。</p>
    <p v-if="level==='high'">高权限连接可直接办理业务、批准申请并维护目录。Agent 应先说明具体操作并获得你的明确确认。</p>
    <p v-if="editing?.level==='high' && !canHigh">当前身份只能将此连接降为低权限后保存。</p>
    <label>到期时间（留空表示不过期）<input v-model="expiry" type="datetime-local" :disabled="busy"/></label><NCheckbox v-if="editing" v-model:checked="active" :disabled="busy">启用连接</NCheckbox>
    <p v-if="error" class="error">{{error}}</p><NButton type="primary" :loading="busy" :disabled="busy||!name.trim()" @click="save">{{editing?'保存修改':'创建并查看接入说明'}}</NButton></div>
  </NModal>
  <NModal v-model:show="secretShow" preset="card" title="连接你的 Agent" class="dialog connection-setup-dialog">
    <div class="connection-setup" v-if="secretConnection">
      <p><strong>{{secretConnection.name}}</strong><br>{{secretConnection.level==='high'?'可直接办理业务，须先说明具体操作并获得你的确认。':'可查询资料、提交申请，申请需由人工审批。'}}</p>
      <p v-if="connectionStatus(secretConnection)!=='已启用'" class="error">此连接{{connectionStatus(secretConnection)}}，请关闭此窗口并编辑连接后再接入。</p>
      <p>复制下面的接入说明，粘贴到你常用的 Agent 对话中，让它配置连接并核对身份。说明包含本人的密钥。</p>
      <NButton type="primary" :disabled="!secret || connectionStatus(secretConnection)!=='已启用'" @click="copy(setupText,'接入说明（含密钥）')">复制接入说明（含密钥）</NButton>
      <p v-if="notice" class="connection-copy-notice" role="status">{{notice}}</p>
      <details class="connection-manual">
        <summary>查看完整说明或手动配置</summary>
        <label>完整接入说明<NInput :value="setupText" type="textarea" readonly :autosize="{minRows:5,maxRows:10}"/></label>
        <label>MCP 服务地址<NInput :value="mcpAddress" readonly/></label><NButton size="small" @click="copy(mcpAddress,'MCP 地址')">单独复制地址</NButton>
        <label>连接密钥<NInput :value="secret" type="password" show-password-on="click" readonly/></label><NButton size="small" @click="copy(secret,'连接密钥')">单独复制密钥</NButton>
        <p>传输方式选 Streamable HTTP；使用 Authorization: Bearer 密钥认证，不使用网页登录 Cookie 或 OAuth。</p>
      </details>
      <p class="connection-note">接入后请 Agent 报告真实用户、连接权限及只读查询结果。保存了配置文件，还不代表已连通。</p>
      <a :href="setupAddress" target="_blank" rel="noopener">查看接入指南与常见问题</a>
      <p v-if="error" class="error" role="alert">{{error}}</p>
    </div>
    <template #footer><NButton @click="clearSecret">关闭</NButton></template>
  </NModal>
</template>
<style scoped>
.connection-form{display:grid;gap:16px}.connection-form label{display:grid;gap:8px}.connection-form input{padding:8px;font:inherit}
.connection-guide{padding:22px 24px;margin-bottom:20px;border:1px solid var(--line);border-radius:6px;background:white}
.connection-guide h2{margin:0 0 10px;font-size:20px;font-weight:500}.connection-guide>p{margin:0;color:var(--muted);line-height:1.7}
.connection-steps{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:28px;margin:22px 0;padding-left:22px}
.connection-steps li{padding-left:4px}.connection-steps strong{font-weight:600}.connection-steps p{margin:7px 0 0;color:var(--muted);font-size:13px;line-height:1.7}
.connection-note{font-size:12px;color:var(--muted);line-height:1.7}.connection-level{display:block;color:var(--muted);font-size:11px}
.connection-setup{max-height:65dvh;overflow:auto}.connection-setup p{line-height:1.7;margin:0 0 14px}
.connection-setup .connection-copy-notice{margin-top:12px;color:#387454}.connection-manual{margin:18px 0;padding:12px;border:1px solid var(--line);border-radius:4px}
.connection-manual summary{cursor:pointer}.connection-manual label{display:grid;gap:6px;margin:14px 0 8px}.connection-manual p{margin:12px 0 0;font-size:12px;color:var(--muted)}
.connection-guide a,.connection-setup a{color:var(--ink);text-underline-offset:3px}
@media(max-width:700px){.connection-guide{padding:16px}.connection-steps{grid-template-columns:1fr;gap:16px}.connection-setup-dialog :deep(.n-button__content){white-space:normal}}
</style>
