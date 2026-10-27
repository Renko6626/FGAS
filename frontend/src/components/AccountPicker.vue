<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { NInput, NModal } from 'naive-ui';
import type { AccountBase } from '../api/accounts';
import { matchesAccountFilters } from '../composables/accountFilters';
import AccountAvatar from './AccountAvatar.vue';

const props = defineProps<{ show: boolean; accounts: AccountBase[]; selected: string; title: string; kinds: Record<string, string> }>();
const emit = defineEmits<{ close: []; choose: [string] }>();
const category = ref<string | null>(null), tag = ref<string | null>(null), search = ref('');
watch(() => props.show, value => { if (value) { category.value = null; tag.value = null; search.value = ''; } });
const tags = computed(() => [...new Set(props.accounts.filter(a => a.active).flatMap(a => a.tags))].sort());
const options = computed(() => props.accounts.filter(a => matchesAccountFilters(a, { showEnded: false, category: category.value, tag: tag.value, search: search.value })));
</script>
<template>
  <NModal :show="show" preset="card" :title="title" class="account-picker" :style="{ width: '800px', maxWidth: 'calc(100vw - 32px)' }" @close="emit('close')" @update:show="v => { if (!v) emit('close') }">
    <div class="picker-categories" aria-label="账户类型">
      <button :class="{ active: category === null }" :aria-pressed="category === null" @click="category = null">全部账户</button>
      <button v-for="(label, value) in kinds" :key="value" :class="{ active: category === value }" :aria-pressed="category === value" @click="category = value">{{ label }}</button>
    </div>
    <div class="picker-layout">
      <aside class="picker-sidebar">
        <strong>标签</strong>
        <button :class="{ active: tag === null }" :aria-pressed="tag === null" @click="tag = null">全部标签</button>
        <button v-for="item in tags" :key="item" :class="{ active: tag === item }" :aria-pressed="tag === item" @click="tag = item">{{ item }}</button>
      </aside>
      <div class="picker-content">
        <NInput v-model:value="search" clearable placeholder="搜索账户名称、编号或联系人" :input-props="{ 'aria-label': '搜索账户' }" />
        <div v-if="options.length" class="picker-grid">
          <button v-for="account in options" :key="account.code" class="picker-card" :class="{ selected: account.code === selected }" :aria-pressed="account.code === selected" @click="emit('choose', account.code)">
            <AccountAvatar :name="account.name" :url="account.avatar_url" />
            <strong>{{ account.name }}</strong><small>{{ account.code }}　{{ kinds[account.kind] }}</small>
          </button>
        </div>
        <p v-else class="picker-empty">没有符合条件的账户，请调整筛选或搜索。</p>
      </div>
    </div>
  </NModal>
</template>
<style scoped>
.picker-categories { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:18px; }
.picker-categories button { border:0; border-radius:5px; background:#f2f5f7; padding:8px 16px; color:#35404c; }
.picker-categories button:hover, .picker-categories button.active { background:#dce9f2; color:#244a66; font-weight:600; }
.picker-layout { display:grid; grid-template-columns:150px minmax(0,1fr); gap:20px; }
.picker-sidebar { display:flex; flex-direction:column; gap:2px; max-height:55vh; overflow:auto; }
.picker-sidebar strong { padding:10px 10px 4px; color:#697580; font-size:12px; }
.picker-sidebar button { border:0; border-radius:5px; background:transparent; padding:8px 10px; text-align:left; color:#35404c; overflow-wrap:anywhere; }
.picker-sidebar button:hover, .picker-sidebar button.active { background:#e8eff4; color:#244a66; }
.picker-content { min-width:0; }
.picker-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin-top:14px; max-height:48vh; overflow:auto; }
.picker-card { display:flex; align-items:center; flex-direction:column; gap:6px; min-width:0; padding:16px 8px; background:#f6f8fa; border:1px solid transparent; border-radius:7px; color:#20242a; }
.picker-card:hover, .picker-card.selected { border-color:#7597b0; background:#eaf1f6; }
.picker-card :deep(.account-avatar) { width:48px; height:48px; border-radius:50%; margin:0; font-size:20px; }
.picker-card strong, .picker-card small { overflow-wrap:anywhere; text-align:center; }
.picker-empty { padding:32px 0; color:#66707c; }
@media (max-width:600px) { .picker-layout { grid-template-columns:105px minmax(0,1fr); gap:10px; } .picker-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }
</style>
