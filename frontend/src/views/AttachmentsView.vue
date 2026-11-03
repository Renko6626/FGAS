<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { NButton, NImage, NInput, NPopconfirm, NSelect } from "naive-ui";
import { attachmentsApi, type AdminAttachmentPage, type Attachment, type AttachmentTarget } from "../api/attachments";

const limit = 24;
const kind = ref<AttachmentTarget | null>(null);
const search = ref("");
const page = ref(1);
const data = ref<AdminAttachmentPage | null>(null);
const busy = ref(false);
const error = ref("");
const removing = ref<string | null>(null);
let searchTimer: number | undefined;

const kindOptions = [
  { label: "全部类型", value: "" },
  { label: "资金单", value: "transfer" },
  { label: "货物单", value: "stock_transfer" },
  { label: "SKU", value: "sku" },
  { label: "资金账户", value: "fund_account" },
  { label: "货物账户", value: "stock_account" },
];
const labels: Record<AttachmentTarget, string> = {
  transfer: "资金单", stock_transfer: "货物单", sku: "SKU",
  fund_account: "资金账户", stock_account: "货物账户",
};
const items = computed(() => data.value?.items || []);
const pages = computed(() => Math.max(1, Math.ceil((data.value?.total || 0) / limit)));
const totalText = computed(() => {
  if (!data.value) return "";
  return `共 ${data.value.total} 张 · ${sizeText(data.value.total_bytes)}`;
});

watch([kind, search], () => {
  window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(() => { page.value = 1; void load(); }, 250);
}, { immediate: true });

function setKind(value: string) {
  kind.value = (value || null) as AttachmentTarget | null;
}
function setPage(value: number) {
  page.value = value;
  void load();
}
async function load() {
  busy.value = true;
  error.value = "";
  try {
    data.value = await attachmentsApi.adminList({
      kind: kind.value || undefined,
      q: search.value.trim() || undefined,
      page: page.value,
      limit,
    });
  } catch (cause) {
    error.value = (cause as Error).message;
  } finally {
    busy.value = false;
  }
}
async function remove(item: Attachment) {
  removing.value = item.id;
  error.value = "";
  try {
    await attachmentsApi.remove(item.id);
    if (items.value.length === 1 && page.value > 1) page.value -= 1;
    await load();
  } catch (cause) {
    error.value = (cause as Error).message;
  } finally {
    removing.value = null;
  }
}
function targetLink(item: Attachment) {
  if (!item.target_code) return "";
  if (item.target_kind === "transfer") return `/#transfers?code=${encodeURIComponent(item.target_code)}`;
  if (item.target_kind === "stock_transfer") return `/#stock?code=${encodeURIComponent(item.target_code)}`;
  return "";
}
function sizeText(bytes: number) {
  return bytes >= 1024 * 1024 ? `${(bytes / 1048576).toFixed(2)} MB` : `${(bytes / 1024).toFixed(1)} KB`;
}
function dateText(value: string) { return new Date(value).toLocaleString("zh-CN", { hour12: false }); }
</script>

<template>
  <div class="page-toolbar">
    <NInput v-model:value="search" clearable placeholder="搜索说明、文件名、上传人或编号" />
    <NSelect :value="kind || ''" :options="kindOptions" style="max-width:170px" @update:value="setKind" />
    <div class="page-tools"><span class="attachment-total">{{ totalText }}</span></div>
  </div>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <div v-if="busy && !items.length" class="empty-state"><p>正在读取图片…</p></div>
  <div v-else-if="!items.length" class="empty-state">
    <h3>还没有图片附件</h3>
    <p>资金/货物单、SKU 和账户上传的图片会集中显示在这里。</p>
  </div>
  <div v-else class="admin-attachment-grid">
    <article v-for="item in items" :key="item.id" class="admin-attachment-card">
      <NImage :src="item.file_url" width="100%" :height="150" object-fit="cover"
        :alt="item.caption || item.original_filename || '图片附件'" />
      <div class="admin-attachment-body">
        <strong>{{ item.caption || item.original_filename || "未命名图片" }}</strong>
        <small>{{ labels[item.target_kind] }} · {{ item.target_code || "已删除对象" }}<template v-if="item.target_name"> · {{ item.target_name }}</template></small>
        <small>{{ item.uploaded_by_name || item.uploaded_by_id }} · {{ dateText(item.created_at) }} · {{ sizeText(item.byte_size) }}</small>
        <div class="admin-attachment-actions">
          <a v-if="targetLink(item)" :href="targetLink(item)">查看原单</a>
          <NPopconfirm @positive-click="remove(item)">
            <template #trigger><NButton size="tiny" :loading="removing === item.id">删除</NButton></template>
            删除后无法恢复，确定删除这张图片？
          </NPopconfirm>
        </div>
      </div>
    </article>
  </div>
  <div v-if="pages > 1" class="admin-attachment-pager">
    <NButton size="small" :disabled="page <= 1" @click="setPage(page - 1)">上一页</NButton>
    <span>{{ page }} / {{ pages }}</span>
    <NButton size="small" :disabled="page >= pages" @click="setPage(page + 1)">下一页</NButton>
  </div>
</template>

<style scoped>
.attachment-total { color:#66707c; font-size:12px; }
.admin-attachment-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); gap:12px; }
.admin-attachment-card { display:flex; flex-direction:column; border:1px solid #e3e8ec; border-radius:8px; background:#fff; overflow:hidden; min-width:0; }
.admin-attachment-card :deep(.n-image) { width:100%; display:block; }
.admin-attachment-body { display:flex; flex-direction:column; gap:3px; padding:8px 10px 10px; min-width:0; }
.admin-attachment-body strong { font-size:13px; overflow-wrap:anywhere; }
.admin-attachment-body small { color:#66707c; font-size:12px; line-height:1.5; overflow-wrap:anywhere; }
.admin-attachment-actions { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-top:4px; }
.admin-attachment-actions a { font-size:12px; color:#345d78; }
.admin-attachment-pager { display:flex; align-items:center; justify-content:center; gap:12px; margin-top:14px; color:#66707c; font-size:13px; }
</style>
