<script setup lang="ts">
import {ref,onMounted} from 'vue'
import {NButton,NSelect,NCheckbox} from 'naive-ui'
import {api,type User} from '../api/funds'
const emit=defineEmits<{changed:[]}>()
const users=ref<User[]>([]),error=ref(''),busy=ref('')
async function load(){try{users.value=await api.adminUsers()}catch(e){error.value=(e as Error).message}}
onMounted(load)
async function save(user:User){busy.value=user.id;error.value='';try{await api.saveUser(user);emit('changed');await load()}catch(e){error.value=(e as Error).message}finally{busy.value=''}}
</script>
<template><h2>用户权限</h2><p class="muted">修改已有开发账号的角色与启用状态。权限由后端持久化并验证。</p><p v-if="error" class="error">{{error}}</p><div class="table-wrap"><table><thead><tr><th>用户</th><th>角色</th><th>启用</th><th></th></tr></thead><tbody><tr v-for="user in users" :key="user.id"><td>{{user.display_name}}<small>{{user.id}}</small></td><td><NSelect v-model:value="user.role" :options="[{label:'管理员',value:'admin'},{label:'受信任用户',value:'trusted'},{label:'普通用户',value:'untrusted'}]"/></td><td><NCheckbox v-model:checked="user.active"/></td><td><NButton :loading="busy===user.id" @click="save(user)">保存</NButton></td></tr></tbody></table></div></template>
