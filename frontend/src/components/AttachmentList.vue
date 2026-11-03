<script setup lang="ts">
import { defineAsyncComponent, ref, watch } from "vue";
import { NButton, NImage, NPopconfirm } from "naive-ui";
import { attachmentsApi, type Attachment, type AttachmentTarget, type AttachmentUpload } from "../api/attachments";
import { currentUser } from "../composables/currentUser";

const ImagePrepareDialog = defineAsyncComponent(() => import("./ImagePrepareDialog.vue"));

const props = defineProps<{
  targetKind: AttachmentTarget;
  targetCode: string | null;
  aspect?: number | null;
  uploadLabel?: string;
}>();
const emit = defineEmits<{ updated: [Attachment[]]; uploaded: [Attachment]; error: [string] }>();

const items = ref<Attachment[]>([]);
const loading = ref(false);
const uploading = ref(false);
const removing = ref<string | null>(null);
const error = ref("");
const showPrepare = ref(false);

function canDelete(item: Attachment) {
  return currentUser.value?.role === "admin" || item.uploaded_by_id === currentUser.value?.id;
}
function fail(cause: unknown) {
  error.value = (cause as Error).message;
  emit("error", error.value);
}
function notify(next: Attachment[]) {
  items.value = next;
  emit("updated", next);
}
async function load() {
  if (!props.targetCode) {
    notify([]);
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    notify(await attachmentsApi.list(props.targetKind, props.targetCode));
  } catch (cause) {
    fail(cause);
  } finally {
    loading.value = false;
  }
}
async function upload(image: AttachmentUpload) {
  showPrepare.value = false;
  if (!props.targetCode) return;
  uploading.value = true;
  error.value = "";
  try {
    const item = await attachmentsApi.upload(props.targetKind, props.targetCode, image);
    notify([...items.value, item]);
    emit("uploaded", item);
  } catch (cause) {
    fail(cause);
  } finally {
    uploading.value = false;
  }
}
async function remove(item: Attachment) {
  removing.value = item.id;
  error.value = "";
  try {
    await attachmentsApi.remove(item.id);
    notify(items.value.filter((entry) => entry.id !== item.id));
  } catch (cause) {
    fail(cause);
  } finally {
    removing.value = null;
  }
}
watch(() => [props.targetKind, props.targetCode], () => { void load(); }, { immediate: true });
defineExpose({ reload: load });
</script>

<template>
  <div class="attachment-list">
    <div v-if="items.length" class="attachment-grid">
      <figure v-for="item in items" :key="item.id" class="attachment-item">
        <NImage :src="item.file_url" :width="96" :height="96" object-fit="cover"
          :alt="item.caption || item.original_filename || '图片附件'" />
        <figcaption>{{ item.caption || item.original_filename || "未命名图片" }}</figcaption>
        <NPopconfirm v-if="canDelete(item)" @positive-click="remove(item)">
          <template #trigger><NButton size="tiny" :loading="removing === item.id">删除</NButton></template>
          删除后无法恢复，确定删除这张图片？
        </NPopconfirm>
      </figure>
    </div>
    <p v-if="loading" class="attachment-hint">正在读取图片…</p>
    <p v-else-if="!items.length" class="attachment-hint">暂无图片。票据、付款截图或货物凭据可以拍照后上传。</p>
    <p v-if="error" class="attachment-hint attachment-error" role="alert">{{ error }}</p>
    <NButton size="small" :loading="uploading" :disabled="!targetCode" @click="showPrepare = true">
      {{ uploadLabel || "上传图片" }}
    </NButton>
    <p v-if="!targetCode" class="attachment-hint">保存后可上传图片。</p>
    <ImagePrepareDialog v-model:show="showPrepare" :aspect="aspect ?? null" @confirm="upload" />
  </div>
</template>

<style scoped>
.attachment-list { display: flex; flex-direction: column; gap: 8px; }
.attachment-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(104px, 1fr)); gap: 10px; }
.attachment-item { display: flex; flex-direction: column; align-items: flex-start; gap: 4px; margin: 0; min-width: 0; }
.attachment-item :deep(.n-image) { border: 1px solid #e3e8ec; border-radius: 6px; overflow: hidden; }
.attachment-item figcaption { font-size: 12px; color: #66707c; line-height: 1.4; overflow-wrap: anywhere; }
.attachment-hint { color: #66707c; font-size: 12px; line-height: 1.6; margin: 0; }
.attachment-error { color: #a33; }
</style>
