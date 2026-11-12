<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue';
import { renderHandbookMarkdown } from '../lib/handbookMarkdown';
import HandbookContents from './HandbookContents.vue';

const props = withDefaults(defineProps<{ content: string; preview?: boolean }>(), { preview: false });
const prefix = `handbook-${useId()}`;
const rendered = computed(() => renderHandbookMarkdown(props.content, prefix));
const article = ref<HTMLElement | null>(null);
const active = ref('');
const mobileOpen = ref(false);
let frame = 0;

function updateActive() {
  if (props.preview || !article.value) return;
  const scrollArea = article.value.closest('.handbook-scroll');
  const top = scrollArea ? scrollArea.getBoundingClientRect().top + 24
    : parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--workspace-header-height')) + 24;
  let current = rendered.value.headings[0]?.id || '';
  for (const heading of Array.from(article.value.querySelectorAll<HTMLElement>('h1,h2,h3,h4,h5,h6'))) {
    if (heading.getBoundingClientRect().top > top) break;
    current = heading.id;
  }
  active.value = current;
}
function onScroll() {
  cancelAnimationFrame(frame);
  frame = requestAnimationFrame(updateActive);
}
async function select(id: string) {
  mobileOpen.value = false;
  await nextTick();
  const heading = document.getElementById(id);
  if (!heading || !article.value?.contains(heading)) return;
  heading.scrollIntoView({ block: 'start', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' });
  heading.focus({ preventScroll: true });
  active.value = id;
}
function followLink(event: MouseEvent) {
  const anchor = (event.target as HTMLElement).closest('a');
  const href = anchor?.getAttribute('href');
  if (!href?.startsWith('#')) return;
  event.preventDefault();
  let fragment: string;
  try { fragment = decodeURIComponent(href.slice(1)); } catch { return; }
  const heading = rendered.value.headings.find(item => item.id === fragment || item.id === `${prefix}-${fragment}`);
  if (heading) void select(heading.id);
}
watch([rendered, () => props.preview], async () => {
  active.value = rendered.value.headings[0]?.id || '';
  await nextTick();
  onScroll();
}, { immediate: true });
onMounted(() => {
  window.addEventListener('scroll', onScroll, true);
  window.addEventListener('resize', onScroll);
});
onBeforeUnmount(() => {
  cancelAnimationFrame(frame);
  window.removeEventListener('scroll', onScroll, true);
  window.removeEventListener('resize', onScroll);
});
</script>

<template>
  <div class="handbook-reader" :class="{ 'is-preview': preview, 'has-contents': rendered.headings.length > 0 }">
    <div v-if="!preview && rendered.headings.length" class="mobile-contents">
      <button type="button" class="contents-toggle" :aria-expanded="mobileOpen" :aria-controls="`${prefix}-mobile-contents`" @click="mobileOpen = !mobileOpen">目录 <span aria-hidden="true">{{ mobileOpen ? '⌃' : '⌄' }}</span></button>
      <nav v-if="mobileOpen" :id="`${prefix}-mobile-contents`" aria-label="章节目录"><HandbookContents :headings="rendered.outline" :active="active" @select="select" /></nav>
    </div>
    <div ref="article" class="handbook-prose" :inert="preview" @click="followLink" v-html="rendered.html"></div>
    <nav v-if="!preview && rendered.headings.length" class="desktop-contents" aria-label="章节目录">
      <strong>本页目录</strong><HandbookContents :headings="rendered.outline" :active="active" @select="select" />
    </nav>
    <p v-if="!preview && !rendered.headings.length" class="contents-hint">使用 Markdown 标题（如 ## 发票流程）可以生成章节目录。</p>
  </div>
</template>

<style scoped>
.handbook-reader { min-width:0; }
.handbook-reader.has-contents:not(.is-preview) { display:grid; grid-template-columns:minmax(0,1fr) 220px; align-items:start; gap:32px; }
.handbook-prose { min-width:0; color:#354357; font-size:14px; line-height:1.85; overflow-wrap:anywhere; }
.handbook-prose :deep(> :first-child) { margin-top:0; }
.handbook-prose :deep(> :last-child) { margin-bottom:0; }
.handbook-prose :deep(h1),.handbook-prose :deep(h2),.handbook-prose :deep(h3),.handbook-prose :deep(h4),.handbook-prose :deep(h5),.handbook-prose :deep(h6) { margin:28px 0 12px; color:#283d54; font-family:inherit; line-height:1.5; font-weight:650; scroll-margin-top:calc(var(--workspace-header-height, 54px) + 24px); }
.handbook-prose :deep(h1) { font-size:24px; }.handbook-prose :deep(h2) { font-size:20px; padding-bottom:8px; border-bottom:1px solid var(--line); }.handbook-prose :deep(h3) { font-size:17px; }.handbook-prose :deep(h4),.handbook-prose :deep(h5),.handbook-prose :deep(h6) { font-size:14px; }
.handbook-prose :deep(p),.handbook-prose :deep(ul),.handbook-prose :deep(ol) { margin:10px 0; }.handbook-prose :deep(ul),.handbook-prose :deep(ol) { padding-left:24px; }
.handbook-prose :deep(li) { margin:4px 0; }.handbook-prose :deep(blockquote) { margin:16px 0; padding:1px 16px; border-left:3px solid #c0cedb; background:#f6f8fa; color:#6c7e90; }
.handbook-prose :deep(a) { color:#245785; text-decoration:underline; text-underline-offset:3px; }
.handbook-prose :deep(code) { font-family:ui-monospace,SFMono-Regular,Consolas,monospace; font-size:.9em; border-radius:3px; background:#edf1f5; padding:2px 4px; }
.handbook-prose :deep(pre) { max-width:100%; overflow:auto; padding:14px; border:1px solid var(--line); border-radius:5px; background:#f5f7f9; }
.handbook-prose :deep(pre code) { padding:0; background:none; white-space:pre; overflow-wrap:normal; }
.handbook-prose :deep(table) { display:block; max-width:100%; overflow:auto; border-collapse:collapse; margin:16px 0; font-size:13px; }
.handbook-prose :deep(th),.handbook-prose :deep(td) { padding:8px 12px; border:1px solid var(--line); text-align:left; }.handbook-prose :deep(th) { background:#f4f6f8; }
.handbook-prose :deep(hr) { border:0; border-top:1px solid var(--line); margin:24px 0; }
.desktop-contents { position:sticky; top:calc(var(--workspace-header-height, 54px) + 20px); max-height:calc(100dvh - var(--workspace-header-height, 54px) - 48px); overflow:auto; border-left:1px solid var(--line); padding-left:16px; }
.desktop-contents > strong { display:block; margin:0 8px 8px; color:#4b6076; font-size:11px; font-weight:600; }
.mobile-contents { display:none; }.contents-hint { font-size:12px; color:var(--muted); }
.is-preview { max-height:160px; overflow:hidden; pointer-events:none; user-select:text; }
@media(max-width:800px) {
  .handbook-reader.has-contents:not(.is-preview) { display:block; }.desktop-contents { display:none; }.mobile-contents { display:block; margin-bottom:18px; border-bottom:1px solid var(--line); padding-bottom:10px; }
  .contents-toggle { display:flex; width:100%; justify-content:space-between; background:none; border:0; padding:6px 0; color:#425b75; font:inherit; font-size:13px; cursor:pointer; }.mobile-contents nav { max-height:45dvh; overflow:auto; margin-top:8px; }
  .handbook-prose { font-size:14px; }.handbook-prose :deep(h1) { font-size:22px; }.handbook-prose :deep(h2) { font-size:18px; }
}
</style>
