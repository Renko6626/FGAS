<script setup lang="ts">
import { computed } from 'vue';
import { renderAgentMarkdown } from '../lib/agentMarkdown';
const props = defineProps<{ content: string }>();
const rendered = computed(() => renderAgentMarkdown(props.content));
</script>

<template><div class="agent-markdown" v-html="rendered"></div></template>

<style scoped>
.agent-markdown { line-height:1.65; overflow-wrap:anywhere; }
.agent-markdown :deep(> :first-child) { margin-top:0; }
.agent-markdown :deep(> :last-child) { margin-bottom:0; }
.agent-markdown :deep(p) { margin:7px 0; }
.agent-markdown :deep(h1),.agent-markdown :deep(h2),.agent-markdown :deep(h3),.agent-markdown :deep(h4),.agent-markdown :deep(h5),.agent-markdown :deep(h6) { margin:12px 0 6px; line-height:1.4; font-family:inherit; font-weight:600; }
.agent-markdown :deep(h1) { font-size:19px; }
.agent-markdown :deep(h2) { font-size:17px; }
.agent-markdown :deep(h3),.agent-markdown :deep(h4),.agent-markdown :deep(h5),.agent-markdown :deep(h6) { font-size:14px; }
.agent-markdown :deep(ul),.agent-markdown :deep(ol) { margin:7px 0; padding-left:22px; }
.agent-markdown :deep(li) { margin:3px 0; }
.agent-markdown :deep(blockquote) { margin:9px 0; padding:1px 12px; border-left:3px solid #c8ced5; color:var(--muted); }
.agent-markdown :deep(code) { font-family:ui-monospace, SFMono-Regular, Consolas, monospace; font-size:12px; background:#e9edf1; padding:1px 4px; border-radius:3px; }
.agent-markdown :deep(pre) { max-width:100%; margin:9px 0; overflow:auto; padding:10px 12px; background:#edf0f3; border:1px solid #e0e5ea; border-radius:4px; }
.agent-markdown :deep(pre code) { background:none; padding:0; overflow-wrap:normal; white-space:pre; }
.agent-markdown :deep(a) { color:#245785; text-decoration:underline; text-underline-offset:2px; }
.agent-markdown :deep(table) { display:block; max-width:100%; overflow:auto; border-collapse:collapse; margin:9px 0; font-size:12px; }
.agent-markdown :deep(th),.agent-markdown :deep(td) { padding:5px 8px; border:1px solid #cfd6dd; text-align:left; white-space:normal; }
.agent-markdown :deep(th) { background:#edf0f3; font-weight:600; }
.agent-markdown :deep(hr) { height:0; border:0; border-top:1px solid #d6dce2; margin:12px 0; }
</style>
