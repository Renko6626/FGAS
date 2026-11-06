<script setup lang="ts">
import { computed, ref } from 'vue';
import { NButton, NInput, NSelect } from 'naive-ui';
import { query } from '../api/client';

const mode = ref<'all' | 'snapshot' | 'changes'>('all');
const start = ref('');
const end = ref('');
const busy = ref(false);
const error = ref('');
const notice = ref('');
const options = [
  { label: '全部台账', value: 'all' },
  { label: '指定时点现状', value: 'snapshot' },
  { label: '时间段内已入账变化', value: 'changes' },
];
const description = computed(() => ({
  all: '全部资金单和货物单明细，包含待审批、待完成、已冲销等状态。',
  snapshot: '截至指定时间的各资金账户余额，以及各内部仓库的 SKU 库存，包含零余额与零库存。',
  changes: '只导出实际入账时间晚于起点、不晚于终点的变化。原单和冲销单都保留，可与起点现状配合计算。',
}[mode.value]));

function time(value: string): string | undefined {
  const text = value.trim();
  if (!text) return undefined;
  // Preserve microseconds when pasting the exact boundary from an earlier bundle.
  const normalized = text.replace(' ', 'T');
  const iso = /(?:Z|[+-]\d{2}:\d{2})$/i.test(normalized) ? normalized : normalized + '+08:00';
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:\d{2})$/i.test(iso)
      || !Number.isFinite(Date.parse(iso))) throw new Error('请输入有效时间，例如 2026-11-06 18:00:00');
  return iso;
}
async function download() {
  if (busy.value) return;
  error.value = notice.value = '';
  busy.value = true;
  try {
    const params: Record<string, string | undefined> = { mode: mode.value };
    if (mode.value === 'snapshot') params.as_of = time(end.value);
    if (mode.value === 'changes') {
      params.start = time(start.value);
      params.end = time(end.value);
      if (!params.start) throw new Error('请填写起始时间');
    }
    const response = await fetch('/api/exports' + query(params), { credentials: 'same-origin' });
    if (!response.ok) {
      if (response.status === 401) window.dispatchEvent(new Event('fgas-session-expired'));
      const data = await response.json().catch(() => null);
      throw new Error(typeof data?.detail === 'string' ? data.detail : '导出失败，请核对时间或稍后重试');
    }
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a');
    link.href = url;
    link.download = response.headers.get('Content-Disposition')?.match(/filename="([^"]+)"/)?.[1] || 'fgas-export.zip';
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    notice.value = '已生成下载文件。压缩包内的说明记录了本次导出的时间范围与行数。';
  } catch (e) { error.value = (e as Error).message; }
  finally { busy.value = false; }
}
</script>

<template>
  <section class="export-panel">
    <p>下载资金与货物 CSV，在表格软件中查看、筛选和核对。</p>
    <form @submit.prevent="download">
      <label>导出内容<NSelect v-model:value="mode" :options="options" :disabled="busy" /></label>
      <p class="export-help">{{ description }}</p>
      <label v-if="mode === 'changes'">起始时间（不包含）
        <NInput v-model:value="start" :disabled="busy" placeholder="例如 2026-11-01 00:00:00" />
      </label>
      <label v-if="mode !== 'all'">截止时间（包含）
        <NInput v-model:value="end" :disabled="busy" placeholder="留空使用导出时的当前时间" />
      </label>
      <p v-if="mode !== 'all'" class="export-help">时间默认按北京时间填写。衔接上次现状时，可直接粘贴压缩包说明中的完整截止时间。</p>
      <NButton attr-type="submit" type="primary" :loading="busy" :disabled="busy">下载 CSV 压缩包</NButton>
    </form>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="notice" role="status">{{ notice }}</p>
    <div class="export-notes">
      <p>每个压缩包包含资金 CSV、货物 CSV 和一份导出说明。金额以元表示，货物每个单据中的一个 SKU 占一行。</p>
      <p>历史现状回溯余额与数量，名称、启用状态和单据状态使用当前资料。附件、审批历史及结算匹配明细不在导出范围内。</p>
    </div>
  </section>
</template>

<style scoped>
.export-panel { max-width:760px; padding:24px; border:1px solid var(--line); border-radius:6px; background:white; }
.export-panel p { line-height:1.7; margin:0 0 18px; }
.export-panel form { max-width:480px; }
.export-panel label { display:grid; gap:8px; margin:20px 0 10px; }
.export-help,.export-notes { color:var(--muted); font-size:12px; }
.export-panel form > button { margin:12px 0 20px; }
.export-notes { border-top:1px solid var(--line); padding-top:18px; }
.export-notes p:last-child { margin-bottom:0; }
@media(max-width:700px) { .export-panel { padding:18px; } }
</style>
