<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue';
import { NButton, NInput, NModal } from 'naive-ui';
import { handbookApi, type Handbook } from '../api/handbook';
import HandbookReader from './HandbookReader.vue';

const props = defineProps<{ handbook: Handbook }>();
const emit = defineEmits<{ saved: [Handbook]; cancel: [] }>();
const title = ref(props.handbook.title);
const content = ref(props.handbook.content);
const preview = ref(false);
const saving = ref(false);
const error = ref('');
let disposed = false;
onBeforeUnmount(() => { disposed = true; });
async function save() {
  if (saving.value || !title.value.trim()) return;
  saving.value = true;
  error.value = '';
  try {
    const saved = await handbookApi.save({ title: title.value.trim(), content: content.value });
    if (!disposed) emit('saved', saved);
  } catch (e) { if (!disposed) error.value = (e as Error).message; }
  finally { if (!disposed) saving.value = false; }
}
</script>

<template>
  <NModal :show="true" preset="card" title="编辑社团手册" class="handbook-editor-modal" :style="{ width: '1120px', maxWidth: 'calc(100vw - 24px)' }"
    :mask-closable="!saving" :close-on-esc="!saving" :closable="!saving" @update:show="value => { if (!value) emit('cancel'); }">
    <form class="handbook-editor" @submit.prevent="save">
      <label for="handbook-title">手册标题</label>
      <NInput id="handbook-title" v-model:value="title" :maxlength="200" :disabled="saving" placeholder="社团手册" />
      <div class="editor-toolbar"><span>Markdown 正文</span><div><NButton size="small" :type="preview ? 'default' : 'primary'" @click="preview = false">编辑</NButton><NButton size="small" :type="preview ? 'primary' : 'default'" @click="preview = true">预览</NButton></div></div>
      <p class="editor-help">用 ## 和 ### 组织章节，阅读目录会自动更新。支持列表、表格和链接。</p>
      <div v-if="preview" class="handbook-scroll editor-preview"><HandbookReader v-if="content" :content="content" /><p v-else class="editor-help">正文为空</p></div>
      <NInput v-else v-model:value="content" type="textarea" aria-label="Markdown 正文" :maxlength="200000" :disabled="saving"
        :autosize="{ minRows: 15, maxRows: 22 }" placeholder="## 发票与报销&#10;&#10;在这里写下办理流程。&#10;&#10;## 储藏室&#10;&#10;位置与使用规章。" />
      <p v-if="error" class="editor-error" role="alert">{{ error }}</p>
      <div class="editor-actions"><small>保存后所有成员可见</small><NButton :disabled="saving" @click="emit('cancel')">取消</NButton><NButton attr-type="submit" type="primary" :loading="saving" :disabled="saving || !title.trim()">保存手册</NButton></div>
    </form>
  </NModal>
</template>

<style scoped>
.handbook-editor label { display:block; margin-bottom:8px; font-size:12px; color:#60738a; }
.editor-toolbar { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-top:20px; font-size:12px; color:#60738a; }.editor-toolbar > div { display:flex; gap:6px; }
.editor-help { margin:8px 0 12px; color:var(--muted); font-size:12px; line-height:1.6; }
.editor-preview { max-height:55dvh; min-height:260px; overflow:auto; padding:18px; border:1px solid var(--line); border-radius:4px; }
.handbook-scroll :deep(.desktop-contents) { top:0; max-height:calc(55dvh - 38px); }.handbook-scroll :deep(.handbook-prose :is(h1,h2,h3,h4,h5,h6)) { scroll-margin-top:20px; }
.handbook-editor :deep(textarea) { font-family:ui-monospace,SFMono-Regular,Consolas,monospace; font-size:13px; line-height:1.7; }
.editor-actions { display:flex; align-items:center; gap:10px; margin-top:18px; }.editor-actions small { margin-right:auto; color:var(--muted); font-size:11px; }.editor-error { color:#b0443c; font-size:13px; }
@media(max-width:600px) { .editor-preview { padding:12px; }.editor-actions { flex-wrap:wrap; }.editor-actions small { width:100%; } }
</style>
