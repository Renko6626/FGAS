<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue';
import { NButton, NInput, NModal, NPopconfirm, NSelect } from 'naive-ui';
import type { User } from '../api/auth';
import AgentMarkdown from './AgentMarkdown.vue';
import { agentConnections } from '../api/agentConnections';
import { streamChat, webAgentApi, type AgentEvent, type AgentHistory, type ChatMessage, type WebAgentConfig } from '../api/webAgent';

const props = defineProps<{ user: User }>();
const emit = defineEmits<{ changed: [] }>();
const open = ref(new URLSearchParams(window.location.search).get('assistant') === '1');
const expanded = ref(false);
const config = ref<WebAgentConfig | null>(null);
const connection = ref<string | null>(null);
const source = ref<'personal' | 'shared'>('shared');
const model = ref('deepseek-flash');
const key = ref('');
const draft = ref('');
const error = ref('');
const busy = ref(false);
const settings = ref(false);
const configurationFailed = ref(false);
const configLoading = ref(false);
const transcript = ref<HTMLElement | null>(null);
const followLatest = ref(true);
interface ToolProgress { id: string; name: string; done: boolean; outcome?: AgentEvent['outcome']; summary?: string }
interface ChatEntry extends ChatMessage { incomplete?: boolean; tools?: ToolProgress[] }
const messages = ref<ChatEntry[]>([]);
const agentHistory = shallowRef<AgentHistory>([]);
const usage = ref({ input: 0, output: 0, requests: 0 });
const balance = ref('');
const balanceBusy = ref(false);
let controller: AbortController | null = null;
let disposed = false;
const options = computed(() => config.value?.connections.map(item => ({
  value: item.id, label: `${item.level === 'high' ? '可直接办理' : '提交申请，需审批'} — ${item.name}（${item.level}）` + (item.active ? '' : '（已停用）'), disabled: !item.active,
})) || []);
const selectedConnection = computed(() => config.value?.connections.find(item => item.id === connection.value));
const connectionLevel = computed(() => selectedConnection.value?.level);
const connectionReady = computed(() => Boolean(selectedConnection.value?.active));
const modelReady = computed(() => Boolean(config.value?.models.includes(model.value) &&
  (source.value === 'shared' ? config.value.shared_available : key.value.trim())));
const ready = computed(() => connectionReady.value && modelReady.value);
const permissionLabel = computed(() => !connectionReady.value ? '尚未启用办事权限'
  : connectionLevel.value === 'high' ? '可直接办理，须先确认' : '提交申请，需审批');
const examples = [
  { label: '查社团余额', message: '帮我查询社团各个公账的当前余额和公账合计。' },
  { label: '查库存', message: '帮我查询当前库存，说明货物分别由谁保管、放在哪里。' },
  { label: '整理一笔垫付', message: '我想登记一笔替社团垫付的费用，请先告诉我需要提供哪些信息，整理好后让我核对，先不要提交记录。' },
];
const canSend = computed(() => Boolean(draft.value.trim() && !busy.value));
const labels: Record<string, string> = {
  fgas_help: '查看业务指南', fgas_query: '查询业务资料', fgas_propose: '提交待审批申请',
  fgas_execute: '直接办理业务',
};

async function load() {
  configLoading.value = true;
  try {
    const data = await webAgentApi.config();
    if (disposed) return;
    config.value = data;
    const active = data.connections.filter(item => item.active);
    if (!active.some(item => item.id === connection.value)) {
      const low = active.filter(item => item.level === 'low');
      connection.value = low.find(item => item.name === '网页助手')?.id || low[0]?.id || null;
    }
  } catch (e) { if (!disposed) error.value = (e as Error).message; }
  finally { if (!disposed) configLoading.value = false; }
}
function usePersonalKey() { source.value = 'personal'; settings.value = true; }
function openSharedSettings() { settings.value = false; open.value = false; window.location.hash = 'sharedModelSettings'; }
function useExample(message: string) { if (!busy.value && !draft.value.trim()) draft.value = message; }
async function createConnection() {
  if (busy.value) return;
  busy.value = true;
  error.value = '';
  try {
    await agentConnections.create({ name: '网页助手', level: 'low', expires_at: null });
    await load();
  } catch (e) { if (!disposed) error.value = (e as Error).message; }
  finally { if (!disposed) busy.value = false; }
}
function trackScroll() {
  const area = transcript.value;
  if (area) followLatest.value = area.scrollHeight - area.scrollTop - area.clientHeight < 48;
}
async function scroll(force = false) {
  await nextTick();
  if (transcript.value && (force || followLatest.value)) {
    transcript.value.scrollTop = transcript.value.scrollHeight;
    followLatest.value = true;
  }
}
function toolSummary(message: ChatEntry, index: number) {
  const pending = message.tools?.find(tool => !tool.done);
  if (pending) return busy.value && index === messages.value.length - 1
    ? labels[pending.name] || '正在处理' : '有步骤待核对';
  const tools = message.tools || [];
  const success = tools.filter(tool => tool.outcome === 'success').length;
  const failed = tools.filter(tool => tool.outcome === 'failed').length;
  const unknown = tools.length - success - failed;
  return [success ? `${success} 步成功` : '', failed ? `${failed} 步失败` : '', unknown ? `${unknown} 步待核对` : ''].filter(Boolean).join('，');
}
function toolStatus(tool: ToolProgress, index: number) {
  if (!tool.done) return busy.value && index === messages.value.length - 1 ? '进行中' : '待核对';
  return tool.outcome === 'success' ? '成功' : tool.outcome === 'failed' ? '失败' : '待核对';
}
function showToolResults(message: ChatEntry) {
  return message.tools?.some(tool => tool.done &&
    (tool.name === 'fgas_propose' || tool.name === 'fgas_execute' || tool.outcome !== 'success'));
}
async function send() {
  if (!canSend.value) return;
  if (!ready.value || !connection.value || configurationFailed.value) { settings.value = true; return; }
  if (messages.value.length >= 40) { error.value = '这段对话已较长，请清空会话后继续'; return; }
  const previousHistory = agentHistory.value;
  const message = draft.value.trim();
  messages.value.push({ role: 'user', content: message });
  messages.value.push({ role: 'assistant', content: '', incomplete: true, tools: [] });
  const index = messages.value.length - 1;
  const reply = messages.value[index]!;
  const tools = reply.tools!;
  draft.value = '';
  error.value = '';
  void scroll(true);
  busy.value = true;
  controller = new AbortController();
  let changed = false;
  const requestConfiguration = () => {
    configurationFailed.value = true;
    settings.value = true;
    if (!tools.length && !reply.content) {
      messages.value.splice(index - 1, 2);
      agentHistory.value = previousHistory;
      draft.value = message;
    }
  };
  const onEvent = (event: AgentEvent) => {
    if (disposed) return;
    if (event.type === 'start' && event.level) {
      const selected = config.value?.connections.find(item => item.id === connection.value);
      if (selected) selected.level = event.level;
    } else if (event.type === 'text') reply.content += event.text || '';
    else if (event.type === 'tool_start') {
      tools.push({ id: event.id || '', name: event.name || '', done: false });
      if (event.name === 'fgas_propose' || event.name === 'fgas_execute') changed = true;
    } else if (event.type === 'tool_end') {
      const tool = tools.find(item => item.id === event.id);
      if (tool) { tool.done = true; tool.outcome = event.outcome; tool.summary = event.summary; }
    } else if (event.type === 'usage') {
      usage.value.input += event.input_tokens || 0;
      usage.value.output += event.output_tokens || 0;
      usage.value.requests += event.requests || 0;
    } else if (event.type === 'history' && event.history) agentHistory.value = event.history;
    else if (event.type === 'done') reply.incomplete = false;
    else if (event.type === 'error') {
      error.value = event.message || '本轮未能完成';
      if (event.configuration_error) requestConfiguration();
    }
    void scroll();
  };
  try {
    await streamChat({ credential_id: connection.value, message, history: agentHistory.value, model: model.value,
      source: source.value, ...(source.value === 'personal' ? { api_key: key.value } : {}) }, controller.signal, onEvent);
  } catch (e) {
    if (!disposed) {
      error.value = (e as Error).name === 'AbortError'
        ? '已停止接收回复。已经提交的业务请到记录中核对。' : (e as Error).message;
      if ((e as Error & { configurationError?: boolean }).configurationError) requestConfiguration();
    }
  } finally {
    controller = null;
    if (!disposed) { busy.value = false; if (changed) emit('changed'); }
  }
}
function clear() {
  if (busy.value) return;
  messages.value = [];
  agentHistory.value = [];
  followLatest.value = true;
  usage.value = { input: 0, output: 0, requests: 0 };
  error.value = '';
}
async function queryBalance() {
  balanceBusy.value = true;
  error.value = '';
  try {
    const result = await webAgentApi.balance();
    if (!disposed) balance.value = result.balances.map(item => item.total_balance + ' ' + item.currency).join('，') +
      '（' + new Date().toLocaleTimeString('zh-CN') + ' 查询）';
  } catch (e) { if (!disposed) error.value = (e as Error).message; }
  finally { if (!disposed) balanceBusy.value = false; }
}
function openWithDraft(message: string) {
  if (!draft.value.trim() && !busy.value) draft.value = message;
  open.value = true;
}
defineExpose({ openWithDraft });
watch([source, model, key, connection], () => { configurationFailed.value = false; });
watch(open, visible => {
  if (!visible) settings.value = false;
  else {
    if (!busy.value) void load();
    void scroll();
  }
});
watch(settings, visible => { if (visible) void load(); });
watch(expanded, () => { void scroll(); });
onMounted(load);
onBeforeUnmount(() => { disposed = true; controller?.abort(); key.value = ''; });
</script>

<template>
  <Teleport to="body">
  <button v-show="!open || !expanded" class="agent-launcher" :class="{ 'agent-launcher-open': open }" type="button" :aria-label="busy ? '网页助手正在回复' : open ? '收起网页助手' : '打开网页助手'" :title="open ? '收起网页助手' : '打开网页助手'" :aria-expanded="open" aria-controls="web-agent-panel" @click="open = !open">
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M5 4h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-9l-5 3v-3H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M7 9h10M7 13h6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
    <span>{{ busy ? '回复中…' : open ? '收起助手' : '网页助手' }}</span>
  </button>
  <section v-show="open" id="web-agent-panel" class="web-agent-panel" :class="{ 'agent-expanded': expanded }" aria-label="网页助手">
    <header class="agent-header"><strong>网页助手</strong><div class="agent-window-actions">
      <button class="agent-expand-button" type="button" :aria-pressed="expanded" :aria-label="expanded ? '还原聊天窗口' : '展开聊天窗口'" @click="expanded = !expanded">{{ expanded ? '还原' : '展开' }}</button>
      <button class="agent-minimize-button" type="button" aria-label="收起网页助手" @click="open = false">−</button>
    </div></header>
    <div class="agent-toolbar">
      <span>{{ permissionLabel }}</span>
      <span>{{ modelReady ? source === 'shared' ? '使用社团模型' : '使用个人模型 Key' : '模型尚未就绪' }}</span>
      <button :disabled="busy" @click="settings = true">助手设置</button>
    </div>
    <p class="agent-session-note">对话仅保留在当前页面，刷新或关闭网页后会清空。收起助手不会清空对话；已提交的业务记录仍会保留。</p>
    <div class="agent-reading">
    <div ref="transcript" class="agent-transcript" aria-live="polite" @scroll="trackScroll">
      <div class="agent-conversation">
      <div v-if="!messages.length" class="agent-welcome">
        <h2>有什么需要一起处理？</h2>
        <p>可以帮你查账、查库存，或整理需要登记的事情。缺少的信息，助手会向你询问。</p>
      </div>
      <div v-if="!config" class="agent-setup">
        <p>{{ configLoading ? '正在读取助手配置…' : '暂时未能读取助手配置，请重试。' }}</p>
        <NButton v-if="!configLoading" size="small" @click="load">重新读取</NButton>
      </div>
      <div v-else-if="!ready" class="agent-setup">
        <template v-if="!connectionReady">
          <p v-if="modelReady && source === 'shared'">使用社团提供的模型，无需填写 Key。</p>
          <p>启用后可以查询资料、提交申请。申请需要审批，通过后才会生效。</p>
          <div class="agent-setup-actions">
            <NButton type="primary" :loading="busy" :disabled="configLoading" @click="createConnection">启用网页助手</NButton>
            <button v-if="options.some(item => !item.disabled)" class="agent-text-button" :disabled="busy" @click="settings = true">选择已有权限连接</button>
          </div>
        </template>
        <div v-if="!modelReady" class="agent-model-guide">
          <template v-if="config.shared_available">
            <p>社团已提供模型，可以直接使用，无需填写 Key。</p>
            <NButton size="small" :disabled="busy" @click="source = 'shared'">使用社团模型</NButton>
          </template>
          <template v-else>
            <p>{{ user.role === 'admin' ? '社团模型尚未开通。设置公共模型后，成员就可以直接使用。' : '社团模型尚未开通，请联系管理员；也可以使用自己的 DeepSeek Key。' }}</p>
            <div class="agent-setup-actions">
              <NButton v-if="user.role === 'admin'" size="small" :disabled="busy" @click="openSharedSettings">设置社团公共模型</NButton>
              <NButton size="small" :disabled="busy" @click="usePersonalKey">使用自己的 DeepSeek Key</NButton>
              <button class="agent-text-button" :disabled="busy || configLoading" @click="load">刷新配置</button>
            </div>
          </template>
        </div>
      </div>
      <div v-if="!messages.length && ready" class="agent-examples">
        <p>可以从这些事情开始：</p>
        <div class="agent-example-buttons"><NButton v-for="example in examples" :key="example.label" size="small" :disabled="busy || !!draft.trim()" @click="useExample(example.message)">{{ example.label }}</NButton></div>
        <small>{{ draft.trim() ? '已有输入，发送或清除后可选择示例。' : '点击只填入输入框，核对后再发送。' }}</small>
      </div>
      <article v-for="(message, index) in messages" :key="index" class="agent-message" :class="message.role">
        <div class="agent-message-meta">
          <small>{{ message.role === 'user' ? user.display_name : '网页助手' }}</small>
          <small v-if="message.incomplete && !(busy && index === messages.length - 1)" class="agent-interrupted">本轮未完成</small>
          <details v-if="message.tools?.length" class="agent-tools" :open="showToolResults(message)">
            <summary>{{ toolSummary(message, index) }}</summary>
            <div v-for="(tool, toolIndex) in message.tools" :key="toolIndex" class="agent-tool-result" :class="tool.outcome">
              <div><span>{{ toolStatus(tool, index) }}</span>{{ labels[tool.name] || tool.name }}</div>
              <p v-if="tool.summary">{{ tool.summary }}</p>
            </div>
          </details>
        </div>
        <AgentMarkdown v-if="message.role === 'assistant' && message.content" :content="message.content" />
        <p v-else>{{ message.content || (busy && index === messages.length - 1 ? '正在处理…' : '') }}</p>
      </article>
      </div>
    </div>
    <button v-if="!followLatest && messages.length" class="agent-latest" type="button" @click="scroll(true)">回到最新</button>
    </div>
    <p v-if="error && !settings" class="agent-error" role="alert">{{ error }}</p>
    <footer class="agent-composer"><div class="agent-composer-content">
      <p v-if="messages.length >= 32" class="agent-limit-note" role="status">{{ messages.length >= 40 ? '本段对话已达 20 轮上限。' : `本段对话还可发送 ${Math.ceil((40 - messages.length) / 2)} 轮。` }}请先保存需要的内容，再清空对话继续；业务记录不会删除。</p>
      <div class="agent-usage"><span>本页用量 {{ usage.input.toLocaleString() }} 输入 / {{ usage.output.toLocaleString() }} 输出 token</span>
        <NPopconfirm :disabled="busy || !messages.length" positive-text="清空对话" negative-text="保留对话" @positive-click="clear">
          <template #trigger><button :disabled="busy || !messages.length">清空对话</button></template>
          清空后无法找回这段对话，已提交的业务记录不会删除。
        </NPopconfirm>
      </div><NInput v-model:value="draft" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" :disabled="busy" placeholder="描述要查询或办理的事…" @keydown.ctrl.enter.prevent="send" /><div class="agent-send"><small>{{ permissionLabel }}</small><NButton v-if="busy" @click="controller?.abort()">停止</NButton><NButton v-else type="primary" :disabled="!canSend" @click="send">{{ ready && !configurationFailed ? '发送' : '设置后发送' }}</NButton></div>
    </div></footer>
  </section>
  <NModal v-model:show="settings" preset="card" title="助手设置" class="dialog compact-dialog agent-settings-dialog" :mask-closable="!busy" :closable="!busy" :close-on-esc="!busy">
    <div class="agent-settings">
      <label>助手的办事权限<NSelect v-model:value="connection" :options="options" :disabled="busy" placeholder="选择你的办事权限" @update:show="visible => { if (visible) void load(); }" /></label>
      <p>权限连接决定助手能替你做哪些事。提交申请需要审批；直接办理须先说明操作并获得你的明确确认。</p>
      <NButton v-if="config && !connectionReady" size="small" :loading="busy" :disabled="configLoading" @click="createConnection">启用网页助手（提交申请，需审批）</NButton>
      <label>使用谁提供的模型<NSelect v-model:value="source" :disabled="busy" :options="[{ label: '社团提供，无需填写 Key', value: 'shared', disabled: !config?.shared_available }, { label: '使用自己的 DeepSeek Key', value: 'personal' }]" /></label>
      <p>{{ source === 'shared' ? '模型调用费用由社团配置的公共账户承担。' : '模型调用费用由你自己的 DeepSeek 账户承担。' }}</p>
      <label>模型<NSelect v-model:value="model" :disabled="busy" :options="(config?.models || []).map(value => ({ value, label: value }))" /></label>
      <label v-if="source === 'personal'">个人 DeepSeek API Key<NInput v-model:value="key" type="password" show-password-on="click" :disabled="busy" autocomplete="off" placeholder="粘贴你在 DeepSeek 平台创建的 API Key" /></label>
      <template v-if="config && !config.shared_available">
        <p>{{ user.role === 'admin' ? '社团模型尚未开通，可前往公共模型设置。' : '社团模型尚未开通，请联系管理员；也可以选择使用自己的 Key。' }}</p>
        <NButton v-if="user.role === 'admin'" size="small" :disabled="busy" @click="openSharedSettings">设置社团公共模型</NButton>
      </template>
      <template v-if="user.role === 'admin'"><NButton size="small" :loading="balanceBusy" :disabled="!config?.shared_available" @click="queryBalance">查询公共账户余额</NButton><p v-if="balance">{{ balance }}</p></template>
      <small>个人 Key 和对话仅保留在当前页面，刷新后清空。社团公共模型配置不受影响。</small>
      <p v-if="error" class="agent-error" role="alert">{{ error }}</p>
    </div>
    <template #footer><div class="agent-settings-actions"><NButton type="primary" :disabled="!ready || busy || configLoading" @click="configurationFailed = false; settings = false">完成设置，返回对话</NButton></div></template>
  </NModal>
  </Teleport>
</template>

<style scoped>
.agent-launcher { position:fixed; z-index:1199; right:24px; bottom:22px; display:flex; align-items:center; gap:8px; padding:10px 15px; border:1px solid #26313c; border-radius:6px; color:white; background:#26313c; box-shadow:0 3px 12px #0002; font:inherit; font-size:13px; }
.agent-launcher svg { width:21px; height:21px; flex:none; }
.agent-launcher span { color:inherit; }
.agent-launcher:hover { background:#3b4856; }
.web-agent-panel { position:fixed; z-index:1200; right:24px; top:96px; bottom:80px; width:min(560px, calc(100vw - 48px)); display:flex; flex-direction:column; color:var(--ink); background:var(--paper); border:1px solid #bfc7cf; border-radius:7px; box-shadow:0 8px 30px #0002; text-align:left; font-size:13px; overflow:hidden; }
.web-agent-panel.agent-expanded { top:16px; right:16px; bottom:16px; width:calc(100vw - 32px); }
.agent-header { display:flex; justify-content:space-between; align-items:center; padding:10px 15px; border-bottom:1px solid var(--line); flex:none; }
.agent-header strong { font-family:var(--serif); font-weight:normal; font-size:20px; }
.agent-window-actions { display:flex; align-items:center; gap:14px; }
.agent-header button { border:0; background:none; font:inherit; padding:3px; color:var(--muted); }
.agent-header .agent-expand-button { font-size:12px; }
.agent-header .agent-minimize-button { font-size:25px; line-height:1; padding:0 3px; }
.agent-toolbar { display:flex; flex-wrap:wrap; align-items:center; gap:8px 16px; padding:8px 15px; border-bottom:1px solid var(--line); font-size:12px; color:var(--muted); }
.agent-toolbar button { margin-left:auto; }
.agent-toolbar button,.agent-usage button { padding:0; border:0; background:none; text-decoration:underline; text-underline-offset:3px; font:inherit; color:inherit; }
.agent-settings { max-height:min(60dvh, 520px); overflow:auto; }
.agent-settings-actions { display:flex; justify-content:flex-end; }
.agent-settings label { display:block; margin:16px 0 8px; }
.agent-settings label:first-child { margin-top:0; }
.agent-settings p { margin:8px 0; font-size:12px; }
.agent-reading { flex:1; display:flex; min-height:90px; position:relative; overflow:hidden; }
.agent-transcript { flex:1; min-width:0; overflow:auto; overflow-anchor:none; padding:14px 16px; overscroll-behavior:contain; scrollbar-gutter:stable; }
.agent-welcome { margin:12px 0 20px; }
.agent-welcome h2 { margin:0 0 10px; font-size:20px; font-weight:500; }
.agent-welcome p,.agent-setup p,.agent-examples p { margin:0 0 12px; line-height:1.7; color:var(--muted); }
.agent-setup { margin-bottom:20px; padding:16px; border:1px solid var(--line); border-radius:6px; background:white; }
.agent-setup-actions,.agent-example-buttons { display:flex; flex-wrap:wrap; align-items:center; gap:10px; }
.agent-model-guide:not(:first-child) { border-top:1px solid var(--line); margin-top:16px; padding-top:16px; }
.agent-text-button { border:0; background:none; padding:4px 0; color:var(--muted); text-decoration:underline; text-underline-offset:3px; font:inherit; cursor:pointer; }
.agent-examples small { display:block; margin-top:10px; color:var(--muted); font-size:12px; }
.agent-session-note { flex:none; margin:0; padding:8px 15px; border-bottom:1px solid var(--line); color:var(--muted); font-size:12px; line-height:1.5; }
.agent-limit-note { margin:0 0 8px; color:#8a4c20; font-size:12px; line-height:1.5; }
.agent-latest { position:absolute; right:16px; bottom:12px; border:1px solid #c8ced5; border-radius:5px; padding:5px 10px; background:white; color:var(--ink); font:inherit; font-size:12px; box-shadow:0 2px 8px #0001; }
.agent-message { margin-bottom:16px; }
.agent-message-meta { display:flex; align-items:baseline; flex-wrap:wrap; gap:4px 10px; margin-bottom:4px; color:var(--muted); }
.agent-message-meta small { font-size:11px; }
.agent-message-meta .agent-interrupted { color:#8a4c20; }
.agent-message p { margin:0; white-space:pre-wrap; overflow-wrap:anywhere; }
.agent-message.user { padding:9px 11px; background:#eee; border-radius:4px; }
.agent-tools { margin-left:auto; max-width:100%; font-size:12px; color:var(--muted); }
.agent-tools[open] { flex-basis:100%; margin-left:0; }
.agent-tools summary { cursor:pointer; overflow-wrap:anywhere; }
.agent-tools div { margin:3px 0; }
.agent-tools span { display:inline-block; width:54px; }
.agent-tool-result { padding:6px 8px; border-left:2px solid var(--line); }
.agent-tool-result.success { border-left-color:#387454; }
.agent-tool-result.failed,.agent-tool-result.unknown { border-left-color:#a65c2b; }
.agent-tool-result p { color:var(--ink); line-height:1.6; }
.agent-error { padding:8px 14px; margin:0; color:#8a2020; background:#fff1ef; border-top:1px solid #e3c7c2; overflow-wrap:anywhere; }
.agent-composer { border-top:1px solid var(--line); padding:8px 12px 10px; flex:none; }
.agent-usage { display:flex; justify-content:space-between; gap:8px; margin-bottom:6px; font-size:10px; color:#727c87; }
.agent-send { display:flex; justify-content:space-between; align-items:center; gap:8px; margin-top:6px; }
.agent-send small { font-size:12px; }
@media(min-width:701px) {
  .agent-expanded .agent-conversation,.agent-expanded .agent-composer-content { width:100%; max-width:1040px; margin-inline:auto; }
  .agent-expanded .agent-transcript { padding:24px 32px; font-size:15px; }
  .agent-expanded .agent-composer { padding:12px 32px 16px; }
  .agent-expanded .agent-send small,.agent-expanded .agent-usage { font-size:12px; }
}
@media(max-width:700px) {
  .web-agent-panel,.web-agent-panel.agent-expanded { top:0; right:0; bottom:auto; width:100%; height:100dvh; border:0; border-radius:0; }
  .agent-launcher { right:12px; bottom:max(12px,env(safe-area-inset-bottom)); width:42px; height:42px; justify-content:center; padding:0; border-radius:50%; }
  .agent-launcher span { display:none; }
  .agent-launcher-open,.agent-expand-button { display:none; }
  .agent-header { padding:calc(9px + env(safe-area-inset-top)) 13px 9px; }
  .agent-transcript { padding:12px; }
  .agent-composer { padding-bottom:calc(10px + env(safe-area-inset-bottom)); }
  .agent-usage { flex-wrap:wrap; }
}
</style>
