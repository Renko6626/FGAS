<script setup lang="ts">
import { computed, ref } from 'vue';
import type { AccountBase } from '../api/accounts';
import AccountAvatar from './AccountAvatar.vue';
import AccountPicker from './AccountPicker.vue';
const props = defineProps<{ accounts: AccountBase[]; source: string; destination: string; kinds: Record<string,string>; disabled?: boolean }>();
const emit = defineEmits<{ 'update:source': [string]; 'update:destination': [string] }>();
const selecting = ref<'source' | 'destination' | null>(null);
const sourceAccount = computed(() => props.accounts.find(a => a.code === props.source));
const destinationAccount = computed(() => props.accounts.find(a => a.code === props.destination));
function choose(code: string) { if (selecting.value === 'source') emit('update:source', code); else emit('update:destination', code); selecting.value = null; }
</script>
<template>
  <div class="route">
    <div class="endpoint"><span>来源</span><button type="button" :disabled="disabled" aria-label="选择来源账户" @click="selecting = 'source'"><AccountAvatar v-if="sourceAccount" :name="sourceAccount.name" :url="sourceAccount.avatar_url" /><span v-else class="empty">＋</span><strong>{{ sourceAccount?.name || '选择来源' }}</strong><small v-if="sourceAccount">{{ sourceAccount.code }}</small></button></div>
    <div class="arrow" aria-label="从来源转向去向">⟶</div>
    <div class="endpoint"><span>去向</span><button type="button" :disabled="disabled" aria-label="选择去向账户" @click="selecting = 'destination'"><AccountAvatar v-if="destinationAccount" :name="destinationAccount.name" :url="destinationAccount.avatar_url" /><span v-else class="empty">＋</span><strong>{{ destinationAccount?.name || '选择去向' }}</strong><small v-if="destinationAccount">{{ destinationAccount.code }}</small></button></div>
  </div>
  <p v-if="source && source === destination" class="error">来源与去向需要不同。</p>
  <AccountPicker :show="!!selecting" :accounts="accounts" :selected="selecting === 'source' ? source : destination" :title="selecting === 'source' ? '选择来源账户' : '选择去向账户'" :kinds="kinds" @close="selecting = null" @choose="choose" />
</template>
<style scoped>
.route { display:grid; grid-template-columns:minmax(0,1fr) minmax(70px, 180px) minmax(0,1fr); align-items:start; gap:8px; padding:2px 0 8px; }
.endpoint { display:flex; flex-direction:column; align-items:center; gap:4px; min-width:0; color:#66707c; font-size:13px; }
.endpoint button { display:flex; flex-direction:column; align-items:center; gap:4px; width:100%; padding:0; border:0; background:none; color:#20242a; }
.endpoint button strong { font-size:15px; overflow-wrap:anywhere; }
.endpoint button small { font-size:12px; }
.endpoint :deep(.account-avatar), .empty { width:60px; height:60px; border-radius:50%; margin:0; font-size:25px; }
.empty { display:grid; place-items:center; background:#f2f5f7; border:1px dashed #9aabb8; color:#61798b; }
.arrow { text-align:center; padding-top:22px; font-size:44px; line-height:1; color:#61798b; }
</style>
