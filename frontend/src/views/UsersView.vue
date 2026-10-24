<script setup lang="ts">
import {onMounted,ref} from 'vue'
import {NButton,NSelect,NCheckbox,NPopconfirm} from 'naive-ui'
import {usersApi,type AdminUser} from '../api/users'
const props=defineProps<{currentUserId:string}>()
const emit=defineEmits<{changed:[]}>()
const users=ref<AdminUser[]>([]),error=ref(''),notice=ref(''),busy=ref('')
const roles=[{label:'管理员',value:'admin'},{label:'受信任用户',value:'trusted'},{label:'普通用户',value:'untrusted'}]
async function load(){try{users.value=await usersApi.adminUsers()}catch(e){error.value=(e as Error).message}}
onMounted(load)
function date(value:string|null){return value?new Date(value).toLocaleString('zh-CN'):'从未登录'}
function short(value:string|null){return value?(value.length>18?value.slice(0,18)+'…':value):'—'}
async function save(user:AdminUser){
  busy.value=user.id;error.value='';notice.value=''
  try{await usersApi.saveUser(user);notice.value='已保存';emit('changed');await load()}
  catch(e){error.value=(e as Error).message;if((e as {status?:number}).status===409)await load()}
  finally{busy.value=''}
}
async function force(user:AdminUser){
  busy.value='force:'+user.id;error.value='';notice.value=''
  try{const result=await usersApi.forceLogout(user.id);notice.value=`已撤销 ${user.display_name} 的 ${result.revoked} 个网页会话`;emit('changed')}
  catch(e){error.value=(e as Error).message}
  finally{busy.value=''}
}
</script>
<template>
  <h2>用户权限</h2>
  <p class="muted">用户在 Casdoor 首次登录后自动创建，默认普通用户；角色由本地管理员维护。停用账号会撤销其全部网页会话并阻止 Agent 继续访问；强制退出只撤销网页会话，不影响 Agent 连接。</p>
  <p v-if="error" class="error" role="alert">{{error}}</p>
  <p v-if="notice" role="status">{{notice}}</p>
  <div class="table-wrap"><table>
    <thead><tr><th>用户</th><th>Casdoor 账号</th><th>邮箱</th><th>最后登录</th><th>角色</th><th>启用</th><th></th></tr></thead>
    <tbody>
      <tr v-for="user in users" :key="user.id">
        <td>{{user.display_name}}<small v-if="user.id===props.currentUserId">当前账号</small><small v-else>{{user.source==='casdoor'?'Casdoor':'开发账号'}}</small></td>
        <td>{{user.sso_username||'—'}}<small v-if="user.sso_subject">sub: {{short(user.sso_subject)}}</small></td>
        <td>{{user.email||'—'}}</td>
        <td>{{date(user.last_login_at)}}</td>
        <td><NSelect v-model:value="user.role" :options="roles"/></td>
        <td><NCheckbox v-model:checked="user.active"/></td>
        <td><div class="user-actions"><NButton :loading="busy===user.id" @click="save(user)">保存</NButton><NPopconfirm @positive-click="force(user)"><template #trigger><NButton :loading="busy==='force:'+user.id" :disabled="!user.active">强制退出</NButton></template>撤销该用户的全部网页登录？</NPopconfirm></div></td>
      </tr>
      <tr v-if="!users.length"><td colspan="7">暂无用户</td></tr>
    </tbody>
  </table></div>
</template>
<style scoped>.user-actions{display:flex;gap:8px}</style>
