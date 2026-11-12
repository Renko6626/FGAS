<script setup lang="ts">
import { defineAsyncComponent, onBeforeUnmount, ref, watch } from 'vue';
import { NButton, NModal } from 'naive-ui';
import { handbookApi, type Handbook } from '../api/handbook';
import HandbookReader from './HandbookReader.vue';
const HandbookEditor = defineAsyncComponent(() => import('./HandbookEditor.vue'));

const props = defineProps<{ trusted: boolean; revision: number }>();
const handbook = ref<Handbook | null>(null);
const loading = ref(false);
const error = ref('');
const notice = ref('');
const expanded = ref(false);
const full = ref(false);
const editing = ref(false);
let disposed = false;
onBeforeUnmount(() => { disposed = true; });
async function load() {
  if (loading.value) return;
  loading.value = true;
  error.value = '';
  try {
    const result = await handbookApi.read();
    if (!disposed) handbook.value = result;
  } catch (e) { if (!disposed) error.value = (e as Error).message; }
  finally { if (!disposed) loading.value = false; }
}
function saved(value: Handbook) {
  handbook.value = value;
  editing.value = false;
  notice.value = '手册已保存';
}
function edit() { notice.value = ''; editing.value = true; }
function updatedAt(value: string) { return new Date(value).toLocaleString('zh-CN', { hour12: false }); }
watch(() => props.revision, load, { immediate: true });
watch(() => props.trusted, value => { if (!value) editing.value = false; });
</script>

<template>
  <section class="shared-handbook" aria-label="社团手册" :aria-busy="loading">
    <header class="handbook-header">
      <div><h2>{{ handbook?.title || '社团手册' }}</h2><p v-if="handbook?.updated_at" class="handbook-meta">{{ handbook.updated_by_name || '成员' }} 修改于 <time :datetime="handbook.updated_at">{{ updatedAt(handbook.updated_at) }}</time></p><p v-else class="handbook-meta">发票流程、储藏室位置与社团规章</p></div>
      <div class="handbook-actions"><NButton v-if="handbook?.content" text size="small" @click="full = true">完整阅读</NButton><NButton v-if="trusted && handbook" size="small" :disabled="loading" @click="edit">{{ handbook.updated_at ? '编辑' : '编写手册' }}</NButton></div>
    </header>
    <p v-if="error" class="handbook-error" role="alert">{{ error }} <NButton text size="small" :disabled="loading" @click="load">重新读取</NButton></p>
    <p v-if="notice" class="handbook-notice" role="status">{{ notice }}</p>
    <template v-if="handbook?.content">
      <HandbookReader :content="handbook.content" :preview="!expanded" />
      <div class="handbook-footer"><NButton text size="small" @click="expanded = !expanded">{{ expanded ? '收起正文' : '展开全文与章节目录' }}</NButton></div>
    </template>
    <p v-else class="handbook-empty">{{ loading ? '正在读取手册…' : handbook ? (trusted ? '还没有内容，可以开始编写。' : '手册尚未编写。') : '暂时无法读取手册。' }}</p>
    <NModal v-model:show="full" preset="card" :title="handbook?.title || '社团手册'" :style="{ width: '1200px', maxWidth: 'calc(100vw - 24px)' }">
      <div class="handbook-scroll full-handbook"><HandbookReader v-if="handbook?.content" :content="handbook.content" /></div>
    </NModal>
    <HandbookEditor v-if="editing && trusted && handbook" :handbook="handbook" @cancel="editing = false" @saved="saved" />
  </section>
</template>

<style scoped>
.shared-handbook { grid-column:1/-1; min-width:0; padding:18px; border:1px solid var(--line); border-radius:6px; background:white; }
.handbook-header { display:flex; align-items:flex-start; justify-content:space-between; gap:16px; margin-bottom:16px; }.handbook-header > div:first-child { min-width:0; }.handbook-header h2 { margin:0; color:#35465a; font-size:15px; font-weight:650; overflow-wrap:anywhere; }
.handbook-meta { margin:5px 0 0; color:#8b97a6; font-size:11px; line-height:1.6; }.handbook-actions { display:flex; align-items:center; flex-shrink:0; gap:14px; }.handbook-actions .n-button { font-size:12px; }
.handbook-footer { margin-top:16px; padding-top:10px; border-top:1px solid var(--line); }.handbook-footer .n-button { font-size:12px; color:#526d88; }
.handbook-empty { color:var(--muted); font-size:13px; margin:12px 0; }.handbook-error { color:#b0443c; font-size:12px; }.handbook-notice { font-size:12px; color:#53816b; }
.full-handbook { max-height:75dvh; overflow:auto; padding:4px 12px 16px 0; }.handbook-scroll :deep(.desktop-contents) { top:0; max-height:calc(75dvh - 24px); }.handbook-scroll :deep(.handbook-prose :is(h1,h2,h3,h4,h5,h6)) { scroll-margin-top:20px; }
@media(max-width:600px) { .shared-handbook { padding:14px; }.handbook-header { flex-wrap:wrap; gap:8px; }.handbook-actions { margin-left:auto; }.full-handbook { padding-right:0; } }
</style>
