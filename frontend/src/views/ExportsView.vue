<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { NButton, NCheckbox, NDatePicker, NInput, NSpin } from 'naive-ui';
import { query, request } from '../api/client';

type ExportMode = 'all' | 'snapshot' | 'changes';
interface PreviewFile { name: string; columns: string[]; total_rows: number; rows: string[][] }
interface ExportPreview { files: PreviewFile[]; generated_at: string; cutoff: string; scope: string }
const mode = ref<ExportMode>('all');
const start = ref<string | null>(null);
const end = ref<string | null>(null);
const precise = ref(false);
const preciseStart = ref('');
const preciseEnd = ref('');
const downloading = ref(false);
const previewing = ref(false);
const locked = computed(() => downloading.value || previewing.value);
const error = ref('');
const notice = ref('');
const preview = ref<ExportPreview | null>(null);
const selectedFile = ref(0);
const currentFile = computed(() => preview.value?.files[selectedFile.value]);
const options: { label: string; value: ExportMode; text: string }[] = [
  { label: '全部台账', value: 'all', text: '全部资金与货物单据，保留各处理状态。' },
  { label: '时点余额与库存', value: 'snapshot', text: '查看某个时间点的钱和货物结余。' },
  { label: '期间变化', value: 'changes', text: '仅导出一段时间内实际入账的变化。' },
];
const fileNames = computed(() => mode.value === 'snapshot'
  ? ['资金余额.csv', '仓库库存.csv'] : ['资金台账.csv', '货物台账.csv']);

watch([mode, start, end, precise, preciseStart, preciseEnd], () => {
  preview.value = null;
  selectedFile.value = 0;
  error.value = notice.value = '';
});
function time(value: string | null): string | undefined {
  const text = value?.trim();
  if (!text) return undefined;
  const normalized = text.replace(' ', 'T');
  const iso = /(?:Z|[+-]\d{2}:\d{2})$/i.test(normalized) ? normalized : normalized + '+08:00';
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:\d{2})$/i.test(iso)
      || !Number.isFinite(Date.parse(iso))) throw new Error('请填写有效的日期和时间');
  return iso;
}
function parameters() {
  const params: Record<string, string | undefined> = { mode: mode.value };
  const from = precise.value ? preciseStart.value : start.value;
  const to = precise.value ? preciseEnd.value : end.value;
  if (mode.value === 'snapshot') params.as_of = time(to);
  if (mode.value === 'changes') {
    params.start = time(from);
    params.end = time(to);
    if (!params.start) throw new Error('请选择开始时间');
  }
  return params;
}
function setPrecision(value: boolean) {
  precise.value = value;
  if (value) {
    preciseStart.value = start.value || '';
    preciseEnd.value = end.value || '';
  }
}
function preset(value: 'today' | 'week' | 'month') {
  // Use Beijing wall-clock values independently of the device timezone.
  const now = new Date(Date.now() + 8 * 60 * 60 * 1000);
  if (value === 'week') now.setUTCDate(now.getUTCDate() - 6);
  if (value === 'month') now.setUTCDate(1);
  start.value = now.toISOString().slice(0, 10) + ' 00:00:00';
  end.value = null;
  precise.value = false;
}
function displayTime(value: string) {
  return new Date(value).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false });
}
function previewCell(value: string, column: string | undefined) {
  const timestamp = column?.endsWith('时间')
    ? /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})/.exec(value) : null;
  return timestamp ? `${timestamp[1]}\n${timestamp[2]}` : value || '—';
}
async function loadPreview() {
  if (locked.value) return;
  error.value = notice.value = '';
  previewing.value = true;
  try {
    preview.value = await request<ExportPreview>('/exports/preview' + query(parameters()));
    selectedFile.value = 0;
  } catch (e) { error.value = (e as Error).message; }
  finally { previewing.value = false; }
}
async function download() {
  if (locked.value) return;
  error.value = notice.value = '';
  downloading.value = true;
  try {
    const response = await fetch('/api/exports' + query(parameters()), { credentials: 'same-origin' });
    if (!response.ok) {
      if (response.status === 401) window.dispatchEvent(new Event('fgas-session-expired'));
      const data = await response.json().catch(() => null);
      throw new Error(typeof data?.detail === 'string' ? data.detail : '导出失败，请稍后重试');
    }
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a');
    link.href = url;
    link.download = response.headers.get('Content-Disposition')?.match(/filename="([^"]+)"/)?.[1] || 'fgas-export.zip';
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    notice.value = '下载已开始，压缩包内含两份 CSV 和导出说明。';
  } catch (e) { error.value = (e as Error).message; }
  finally { downloading.value = false; }
}
onMounted(loadPreview);
</script>

<template>
  <section class="export-panel" aria-label="台账导出">
    <p class="export-intro">选择要核对的台账，预览后下载到表格软件中查看。</p>
    <div class="export-layout">
      <form class="export-controls" @submit.prevent="download">
        <fieldset class="export-modes" :disabled="locked">
          <legend>导出内容</legend>
          <label v-for="option in options" :key="option.value" class="export-mode" :class="{ selected: mode === option.value }">
            <input v-model="mode" type="radio" name="export-mode" :value="option.value" />
            <span><strong>{{ option.label }}</strong><small>{{ option.text }}</small></span>
          </label>
        </fieldset>
        <div v-if="mode !== 'all'" class="export-times">
          <div class="time-heading"><strong>时间范围</strong><span>北京时间</span></div>
          <div v-if="mode === 'changes'" class="export-presets" aria-label="常用时间范围">
            <NButton size="tiny" :disabled="locked" @click="preset('today')">今天</NButton>
            <NButton size="tiny" :disabled="locked" @click="preset('week')">近 7 天</NButton>
            <NButton size="tiny" :disabled="locked" @click="preset('month')">本月</NButton>
          </div>
          <template v-if="!precise">
            <label v-if="mode === 'changes'" class="time-field">开始时间
              <NDatePicker v-model:formatted-value="start" type="datetime" value-format="yyyy-MM-dd HH:mm:ss" format="yyyy-MM-dd HH:mm:ss" :disabled="locked" clearable placeholder="选择开始日期和时间" />
            </label>
            <label class="time-field">{{ mode === 'snapshot' ? '截至时间' : '结束时间' }}
              <NDatePicker v-model:formatted-value="end" type="datetime" value-format="yyyy-MM-dd HH:mm:ss" format="yyyy-MM-dd HH:mm:ss" :disabled="locked" clearable placeholder="留空表示当前时间" />
            </label>
          </template>
          <template v-else>
            <label v-if="mode === 'changes'" class="time-field">开始时间
              <NInput v-model:value="preciseStart" :disabled="locked" placeholder="粘贴上次导出的完整截止时间" />
            </label>
            <label class="time-field">{{ mode === 'snapshot' ? '截至时间' : '结束时间' }}
              <NInput v-model:value="preciseEnd" :disabled="locked" placeholder="留空表示当前时间" />
            </label>
          </template>
          <p v-if="mode === 'changes'" class="export-help">按实际入账时间筛选，不包含开始时刻，包含结束时刻。</p>
          <NCheckbox :checked="precise" :disabled="locked" @update:checked="setPrecision">粘贴精确时间</NCheckbox>
          <p v-if="precise" class="export-help precision-help">可粘贴说明文件中的完整时间，保留微秒与时区，衔接上次导出。</p>
        </div>
        <div class="export-buttons">
          <NButton :loading="previewing" :disabled="downloading" @click="loadPreview">预览内容</NButton>
          <NButton attr-type="submit" type="primary" :loading="downloading" :disabled="previewing">下载 CSV 压缩包</NButton>
        </div>
        <p v-if="error" class="export-feedback error" role="alert">{{ error }}</p>
        <p v-if="notice" class="export-feedback success" role="status">{{ notice }}</p>
      </form>
      <section class="export-preview" aria-labelledby="export-preview-title" :aria-busy="previewing">
        <div class="preview-heading"><h2 id="export-preview-title">内容预览</h2><span>每份文件显示前 10 行</span></div>
        <NSpin :show="previewing">
          <template v-if="preview && currentFile">
            <div class="preview-files" role="group" aria-label="预览文件">
              <button v-for="(file, index) in preview.files" :key="file.name" type="button" :aria-pressed="selectedFile === index" @click="selectedFile = index">
                {{ file.name }}<span>{{ file.total_rows.toLocaleString() }} 行</span>
              </button>
            </div>
            <p class="preview-scope">{{ preview.scope }}</p>
            <div class="preview-table-scroll" tabindex="0" role="region" :aria-label="currentFile.name + '内容，可横向滚动'">
              <table class="export-table">
                <caption class="sr-only">{{ currentFile.name }}，共 {{ currentFile.total_rows }} 行，显示前 10 行</caption>
                <thead><tr><th scope="col" class="row-number">行</th><th v-for="column in currentFile.columns" :key="column" scope="col">{{ column }}</th></tr></thead>
                <tbody><tr v-for="(row, index) in currentFile.rows" :key="index"><td class="row-number">{{ index + 1 }}</td><td v-for="(cell, cellIndex) in row" :key="cellIndex" :title="cell" :class="{ 'preview-time': currentFile.columns[cellIndex]?.endsWith('时间') }">{{ previewCell(cell, currentFile.columns[cellIndex]) }}</td></tr></tbody>
              </table>
              <p v-if="!currentFile.rows.length" class="preview-empty">这个范围内没有记录。下载文件仍会保留表头。</p>
            </div>
            <p class="preview-timestamp">预览生成于 {{ displayTime(preview.generated_at) }}。下载时会按所选条件重新读取最新数据。</p>
          </template>
          <div v-else class="preview-placeholder">
            <div class="preview-file-list"><span v-for="name in fileNames" :key="name">{{ name }}</span><span>说明.txt</span></div>
            <strong>{{ previewing ? '正在读取台账…' : '选择条件后，预览实际导出内容' }}</strong>
            <p>在左侧设置内容与时间，再点击“预览内容”。</p>
          </div>
        </NSpin>
      </section>
    </div>
    <details class="export-notes">
      <summary>文件格式与统计口径</summary>
      <p>ZIP 内含资金 CSV、货物 CSV 和说明.txt。CSV 使用 UTF-8 编码，可用 Excel 等表格软件打开。金额以元表示，货物按每个单据的每个 SKU 各占一行。</p>
      <p>时点现状保留零余额、零库存和停用对象；余额与库存按历史回溯，名称、启用状态和单据状态使用当前资料。期间变化保留原单和冲销单。</p>
      <p>附件、审批历史及结算匹配明细不在导出范围内。导出文件用于核对台账，不能替代数据库备份。</p>
    </details>
  </section>
</template>

<style scoped>
.export-panel { min-width:0; }
.export-intro { margin:0 0 20px; color:var(--muted); font-size:13px; }
.export-layout { display:grid; grid-template-columns:300px minmax(0,1fr); gap:28px; align-items:start; }
.export-controls { min-width:0; }
.export-modes { border:0; margin:0; padding:0; display:grid; gap:8px; }
.export-modes legend { padding:0; margin-bottom:12px; font-weight:650; font-size:13px; }
.export-mode { display:flex; align-items:flex-start; gap:10px; margin:0; padding:13px 12px; border:1px solid #dfe4eb; border-radius:6px; cursor:pointer; }
.export-mode.selected { border-color:#8192a8; background:#f2f5f8; }
.export-mode input { accent-color:#46566b; margin:4px 0 0; flex:none; }
.export-mode strong { display:block; font-size:13px; font-weight:600; }
.export-mode small { display:block; color:#788391; font-size:12px; line-height:1.6; margin-top:3px; }
.export-modes:disabled .export-mode { cursor:default; opacity:.7; }
.export-times { margin-top:24px; }
.time-heading { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; font-size:13px; }
.time-heading span { color:var(--muted); font-size:12px; }
.export-presets { display:flex; gap:8px; margin-bottom:14px; }
.time-field { display:grid; gap:7px; margin:0 0 14px; font-size:12px; color:#596579; }
.time-field :deep(.n-date-picker) { width:100%; }
.time-field :deep(.n-input) { margin-top:0; }
.export-help { color:var(--muted); font-size:12px; line-height:1.7; margin:0 0 12px; }
.precision-help { margin:8px 0 0; }
.export-times :deep(.n-checkbox__label) { font-size:12px; color:var(--muted); }
.export-buttons { display:flex; gap:8px; flex-wrap:wrap; margin-top:24px; }
.export-buttons :deep(.n-button) { padding-left:12px; padding-right:12px; }
.export-feedback { margin:12px 0 0; font-size:12px; line-height:1.7; }
.export-preview { min-width:0; border-left:1px solid #e5e9ee; padding-left:28px; }
.preview-heading { display:flex; align-items:baseline; flex-wrap:wrap; gap:8px 16px; margin-bottom:16px; }
.preview-heading h2 { font-size:15px; margin:0; }
.preview-heading>span { margin-left:auto; color:#7b8797; font-size:12px; }
.preview-files { display:flex; gap:20px; border-bottom:1px solid #e1e6ed; overflow-x:auto; }
.preview-files button { display:flex; align-items:center; gap:8px; border:0; border-bottom:2px solid transparent; border-radius:0; background:none; padding:0 0 12px; color:#7a8696; font-size:13px; white-space:nowrap; min-width:0; }
.preview-files button[aria-pressed=true] { color:#40566f; border-bottom-color:#536a83; font-weight:600; }
.preview-files button span { font-size:11px; background:#eef1f5; border-radius:3px; padding:1px 5px; color:inherit; }
.preview-scope { font-size:12px; color:#758194; line-height:1.7; margin:14px 0; }
.preview-table-scroll { overflow:auto; border:1px solid #e5e9ee; border-radius:5px; max-height:460px; }
.export-table { width:100%; border-collapse:collapse; font-size:12px; text-align:left; }
.export-table th,.export-table td { padding:9px 10px; border:0; border-bottom:1px solid #edf0f4; white-space:nowrap; text-align:left; font-weight:400; max-width:280px; overflow:hidden; text-overflow:ellipsis; }
.export-table th { color:#7c8796; background:#f5f7fa; font-size:11px; position:sticky; top:0; border-bottom-color:#dfe4eb !important; }
.export-table tbody tr:last-child td { border-bottom:0; }
.export-table tbody tr:hover { background:#f8f9fb; }
.export-table .row-number { width:35px; color:#99a3b1; font-variant-numeric:tabular-nums; }
.export-table .preview-time { white-space:pre-line; min-width:100px; line-height:1.4; font-variant-numeric:tabular-nums; }
.preview-timestamp { font-size:11px; color:#8b97a6; margin:12px 0 0; line-height:1.7; }
.preview-empty { text-align:center; padding:38px 16px; font-size:13px; color:#7b8797; margin:0; }
.preview-placeholder { min-height:280px; display:flex; flex-direction:column; justify-content:center; align-items:center; padding:24px; text-align:center; background:#f8f9fb; border:1px dashed #dfe4eb; border-radius:6px; }
.preview-file-list { display:flex; flex-wrap:wrap; justify-content:center; gap:8px; margin-bottom:24px; }
.preview-file-list span { padding:6px 10px; background:white; border:1px solid #e1e6ed; border-radius:4px; color:#7b8797; font-size:12px; }
.preview-placeholder strong { font-size:14px; font-weight:500; color:#657286; }
.preview-placeholder p { color:#8b97a6; font-size:12px; margin:8px 0 0; }
.export-notes { border-top:1px solid #e5e9ee; margin-top:24px; padding-top:16px; color:var(--muted); font-size:12px; }
.export-notes summary { cursor:pointer; width:fit-content; }
.export-notes p { margin:12px 0 0; line-height:1.8; max-width:85em; }
.sr-only { position:absolute; width:1px; height:1px; padding:0; overflow:hidden; clip-path:inset(50%); white-space:nowrap; }
@media(max-width:1100px) { .export-layout { grid-template-columns:270px minmax(0,1fr); gap:20px; }.export-preview { padding-left:20px; }.preview-files { gap:12px; } }
@media(max-width:900px) { .export-layout { grid-template-columns:minmax(0,1fr); gap:24px; }.export-preview { border-left:0; border-top:1px solid #e5e9ee; padding:20px 0 0; }.export-modes { grid-template-columns:repeat(3,minmax(0,1fr)); }.export-mode { padding:12px 10px; gap:7px; }.export-times { max-width:440px; } }
@media(max-width:580px) { .export-modes { grid-template-columns:minmax(0,1fr); }.export-mode { padding:12px; }.preview-heading>span { margin-left:0; }.preview-files { gap:16px; }.preview-files button { font-size:12px; }.export-intro { margin-bottom:16px; } }
</style>
