<script setup lang="ts">
import { computed, ref } from 'vue';
import { NButton } from 'naive-ui';

defineProps<{ assistantAvailable: boolean }>();
const emit = defineEmits<{ assistant: [message: string]; connections: [] }>();
const kind = ref<'funds' | 'stock'>('funds');
const step = ref(0);
const reimbursed = ref(false);
const steps = computed(() => kind.value === 'funds'
  ? ['提交申请', '审批通过'] : ['提交申请', '审批通过', '确认完成']);
const posted = computed(() => step.value === steps.value.length - 1);
const explanation = computed(() => kind.value === 'funds'
  ? ['申请付给供应商 100 元，此时余额不变。', '审批通过，公账减少 100 元，留下正式流水。'][step.value]
  : ['申请把 10 本刊物从社团仓库交给小林，此时库存不变。', '批准后进入待完成，表示计划已获批，库存仍不变。', '整笔交接确认完成，仓库减少 10 本，小林代管增加 10 本，社团总量不变。'][step.value]);
const prompt = '我是新成员。我想办理一件事，请先帮我判断应该登记资金、货物，还是处理私账结算，再告诉我需要提供哪些信息。先不要提交记录。';
function selectKind(value: 'funds' | 'stock') { kind.value = value; step.value = 0; }
</script>

<template>
  <article class="quick-start">
    <header class="guide-intro">
      <h1>先看懂东西在哪里，怎样流动</h1>
      <p>FGAS 记录社团的钱和货物。记住账户和转移，就可以开始使用。</p>
      <p class="intro-ai">这里支持 AI Agent 接入。看懂基本规则后，就可以把日常登记、核对和整理交给 Agent。</p>
    </header>

    <section class="guide-section" aria-labelledby="places-title">
      <h2 id="places-title">账户记录钱，仓库保管货物</h2>
      <div class="places">
        <div><h3>资金账户</h3><p>公账是社团的钱，私账记录成员与社团的往来，外部账户表示供应商、客户等往来方。</p><span class="examples">社团支付宝 / 小林的私账 / 印厂</span></div>
        <div><h3>货物账户</h3><p>记录货物由谁保管、放在哪里。社团仓库和成员代管都属于内部账户，外部账户表示供应商、客户等。</p><span class="examples">社团仓库 / 小林代管 / 印厂</span></div>
      </div>
    </section>

    <section class="guide-section" aria-labelledby="transfer-title">
      <div class="section-heading"><h2 id="transfer-title">一次变化，就是一笔转移</h2><span>以下均为演示，不会记账</span></div>
      <div class="example-tabs" role="group" aria-label="转移示例">
        <button :aria-pressed="kind === 'funds'" @click="selectKind('funds')">付一笔钱</button>
        <button :aria-pressed="kind === 'stock'" @click="selectKind('stock')">交接一批货</button>
      </div>
      <div class="flow" :key="kind">
        <div class="flow-end"><small>来源</small><strong>{{ kind === 'funds' ? '社团公账' : '社团仓库' }}</strong><span>{{ kind === 'funds' ? (posted ? '¥ 900' : '¥ 1,000') : (posted ? '10 本' : '20 本') }}</span></div>
        <div class="flow-path"><div class="flow-line" aria-hidden="true"></div><span class="flow-packet" :class="{ moved: posted }" :key="step">{{ kind === 'funds' ? '¥ 100' : '10 本刊物' }}</span><small>{{ posted ? '已入账' : step === 0 ? '待审批' : '待完成' }}</small></div>
        <div class="flow-end"><small>去向</small><strong>{{ kind === 'funds' ? '供应商' : '小林代管' }}</strong><span>{{ kind === 'funds' ? (posted ? '收到 ¥ 100' : '待收款') : (posted ? '10 本' : '0 本') }}</span></div>
      </div>
      <div class="demo-steps" role="group" aria-label="查看示例步骤"><button v-for="(label, index) in steps" :key="label" :aria-pressed="step === index" @click="step = index"><span>{{ index + 1 }}</span>{{ label }}</button></div>
      <p class="step-explanation" aria-live="polite">{{ explanation }}</p>
      <p class="guide-note">这里演示普通成员的申请流程。受信任用户和管理员可以直接登记；货物仍需确认完成才改变库存。钱和货物分开记录，一次采购可能两种都要登记。</p>
    </section>

    <section class="guide-section" aria-labelledby="private-title">
      <h2 id="private-title">私账不为零，表示还有款项待结清</h2>
      <p>小林先用自己的钱替社团买了 100 元物料。登记垫付后，社团欠小林 100 元；完成报销和对应的结算匹配后，这笔往来结清。</p>
      <div class="private-flow" aria-label="垫付与报销的资金流向">
        <div class="flow-end" :class="{ 'awaiting-payment': !reimbursed }"><small>报销方</small><strong>社团公账</strong></div>
        <div class="flow-path">
          <template v-if="reimbursed"><div class="flow-line reimbursement-edge" aria-hidden="true"></div><span class="flow-packet moved">¥ 100</span><small>报销</small></template>
        </div>
        <div class="flow-end"><small>成员</small><strong>小林</strong></div>
        <div class="flow-path"><div class="flow-line" aria-hidden="true"></div><span class="flow-packet">¥ 100</span><small>垫付</small></div>
        <div class="flow-end"><small>收款方</small><strong>供应商</strong></div>
      </div>
      <div class="private-demo">
        <div><span>小林的私账</span><strong :key="String(reimbursed)" class="private-balance">{{ reimbursed ? '¥ 0' : '− ¥ 100' }}</strong><span aria-live="polite">{{ reimbursed ? '这笔往来已结清' : '社团应报销给小林 100 元' }}</span></div>
        <NButton @click="reimbursed = !reimbursed">{{ reimbursed ? '重看垫付示例' : '演示报销并结清' }}</NButton>
      </div>
      <div class="balance-meaning"><p><strong>负数</strong>社团应付给成员</p><p><strong>正数</strong>成员应交回社团</p><p><strong>零</strong>当前往来已平</p></div>
      <p class="guide-note">私账余额表示与社团的往来，不表示成员银行卡里有多少钱。结算匹配只标明款项对应关系，本身不会产生付款。</p>
    </section>

    <section class="guide-section guide-next" aria-labelledby="next-title">
      <h2 id="next-title">把繁复的文书工作交给 Agent</h2>
      <p class="ai-lead">FGAS 支持 Agent 接入。在资金、货物和结算等日常业务中，AI 可以覆盖几乎所有网页操作。你可以直接描述事情，让它帮你查资料、整理明细，再按你的授权办理。</p>
      <ul class="ai-capabilities">
        <li><strong>查清楚</strong><span>查余额、库存和历史流水，找出垫付、报销及尚未结清的款项。</span></li>
        <li><strong>整理好</strong><span>把你提供的采购、交接和收支明细整理成记录，核对账户、货物和金额，追问缺少的信息。</span></li>
        <li><strong>交给它办</strong><span>登记资金和货物转移、提交申请；有相应权限时，还能维护目录、审批、确认完成和建立结算匹配。</span></li>
      </ul>
      <blockquote class="ai-example">“这次活动我垫了 100 元印刷费，还把 10 本刊物交给小林保管。帮我查一下对应账户和货物，整理需要登记的内容，先给我核对。”</blockquote>
      <p>你负责说明实际发生的事、补齐信息和核对结果。查找页面、拆分步骤、填写表单这些工作，大可以交给 Agent。</p>
      <div v-if="assistantAvailable" class="next-option"><div><h3>直接用网页 AI</h3><p>打开右下角的网页助手，用日常语言描述要办的事，无需另外配置 Agent 客户端。模型尚未配置时，按面板提示设置即可。</p></div><NButton type="primary" @click="emit('assistant', prompt)">打开网页 AI</NButton></div>
      <p v-else class="guide-note">当前环境未启用网页 AI，可以连接自己的 Agent 使用。</p>
      <div class="next-option"><div><h3>也可以用自己的 coding agent</h3><p>支持 MCP 的 Agent 可以直接接入同一套业务工具，继续使用你熟悉的客户端。</p><ol class="agent-setup"><li>前往“Agent 连接”，创建本人连接。</li><li>把 MCP 地址、本人密钥和接入指南交给 Agent，让它帮你配置。</li><li>先让它核对身份和权限、做一次只读查询，再开始办理业务。</li></ol><a href="/agent-setup.md" target="_blank" rel="noopener">查看 Agent 接入指南</a></div><NButton @click="emit('connections')">前往 Agent 连接</NButton></div>
      <p class="ai-permissions">Agent 遵守你的权限。低权限连接提交的写申请仍需人工审批；高权限连接可直接办理，须先说明具体操作并获得你的明确确认。账号权限和连接密钥仍在网页管理。</p>
      <p class="guide-note">网页 AI 按钮只打开对话并预填示例，不会自动发送；已有输入会保留。办理前请核对 AI 说明的具体操作和影响。</p>
    </section>
  </article>
</template>

<style scoped>
.quick-start{max-width:960px;margin:0 auto;padding:28px 36px 40px;background:#fff;color:#222;line-height:1.8}
.guide-intro h1{font-size:24px;line-height:1.45;margin:0 0 12px;font-weight:600}.guide-intro p{color:#555;margin:0}
.guide-section{border-top:1px solid #ddd;margin-top:32px;padding-top:24px}.guide-section h2{font-size:18px;font-weight:600;margin:0 0 16px}.guide-section h3{font-size:15px;margin:0 0 8px}.guide-section p{margin:0 0 12px}
.places{display:grid;grid-template-columns:1fr 1fr;gap:32px}.places p{max-width:34em}.examples,.guide-note{font-size:13px;color:#666}.examples{display:block;border-left:2px solid #aaa;padding-left:10px}.section-heading{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:8px}.section-heading>span{font-size:12px;color:#777}
.example-tabs{display:flex;gap:20px;margin:4px 0 24px}.example-tabs button{border:0;border-bottom:2px solid transparent;background:none;padding:5px 0;font:inherit;color:#666;cursor:pointer}.example-tabs button[aria-pressed=true]{border-color:#222;color:#111;font-weight:600}
.flow{display:grid;grid-template-columns:1fr 1.2fr 1fr;gap:12px;align-items:center;padding:24px 12px;background:#f6f7f8}.flow-end{display:flex;flex-direction:column;text-align:center;gap:4px}.flow-end small{color:#777}.flow-end strong{font-size:17px}.flow-end>span{font-variant-numeric:tabular-nums;font-size:14px}.flow-path{position:relative;text-align:center;display:grid;justify-items:center;gap:12px}.flow-line{position:absolute;top:20px;left:0;right:0;border-top:1px solid #9aabb7}.flow-line:after{content:'';position:absolute;right:0;top:-4px;width:6px;height:6px;border-top:1px solid #9aabb7;border-right:1px solid #9aabb7;transform:rotate(45deg)}.flow-packet{position:relative;background:#e5edf2;border:1px solid #b5c8d6;padding:5px 12px;font-weight:600;font-size:14px;white-space:nowrap}.flow-packet.moved{animation:transfer .7s ease-out both}.flow-path small{color:#666}
.demo-steps{display:flex;flex-wrap:wrap;gap:8px;margin:20px 0 12px}.demo-steps button{display:flex;align-items:center;gap:8px;background:#fff;border:1px solid #ccc;padding:6px 12px;font:inherit;font-size:13px;cursor:pointer}.demo-steps button[aria-pressed=true]{border-color:#222;background:#f0f0f0}.demo-steps button span{color:#777}.step-explanation{min-height:3.6em}.private-demo{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:20px 24px;background:#f6f7f8;margin:20px 0}.private-demo>div{display:flex;flex-direction:column;font-size:13px;color:#555}.private-balance{font-size:30px;line-height:1.6;font-weight:500;color:#222;font-variant-numeric:tabular-nums;animation:balance .35s ease-out}.balance-meaning{display:flex;flex-wrap:wrap;gap:12px 28px}.balance-meaning p{font-size:13px}.balance-meaning strong{margin-right:10px}.next-option{display:flex;align-items:center;justify-content:space-between;gap:24px;padding:18px 0}.next-option p{font-size:13px;color:#555;max-width:42em;margin:0}.next-option+.next-option{border-top:1px solid #eee}.guide-next>.guide-note{margin-top:14px}
button:focus-visible{outline:2px solid #387454;outline-offset:3px}
.guide-intro .intro-ai{margin-top:12px;color:#333}.guide-next{border-top:3px solid #26313c;padding-top:28px}.guide-next h2{font-size:22px}.ai-lead{font-size:16px;line-height:1.9}.ai-capabilities{list-style:none;padding:0;margin:22px 0;display:grid;gap:14px}.ai-capabilities li{display:grid;grid-template-columns:6em 1fr;gap:14px}.ai-capabilities li>span{color:#444}.ai-example{margin:24px 0;padding:16px 20px;border-left:3px solid #9aabb7;background:#f6f7f8;color:#333}.agent-setup{padding-left:20px;font-size:13px;color:#555;margin:12px 0}.next-option a{color:#26313c;text-underline-offset:3px;font-size:13px}.ai-permissions{border-top:1px solid #ddd;padding-top:16px;color:#555;font-size:13px}
.private-flow{display:grid;grid-template-columns:1fr .9fr 1fr .9fr 1fr;gap:12px;align-items:center;background:#f6f7f8;padding:24px 12px;margin-top:20px}.private-flow .flow-path{min-height:70px}.private-flow .flow-packet{padding:5px 7px;font-size:13px}.awaiting-payment{opacity:.45}.private-flow+.private-demo{margin-top:2px}.reimbursement-edge{transform-origin:left;animation:draw-edge .5s ease-out both}
@keyframes draw-edge{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@keyframes transfer{from{transform:translateX(-45%);opacity:.4}to{transform:translateX(0);opacity:1}}@keyframes balance{from{opacity:.3;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
@media(max-width:640px){.quick-start{padding:20px 16px 32px}.guide-intro h1{font-size:21px}.places{grid-template-columns:1fr;gap:22px}.flow{gap:4px;padding:20px 4px;grid-template-columns:1fr 1fr 1fr}.flow-end strong{font-size:14px}.flow-packet{font-size:12px;padding:5px 7px}.private-demo,.next-option{align-items:flex-start;flex-direction:column;gap:16px}.guide-section{margin-top:24px}.demo-steps button{padding:5px 8px}}
@media(max-width:640px){.private-flow{gap:4px;padding:20px 4px}.private-flow .flow-end strong{font-size:13px}.private-flow .flow-packet{font-size:11px;padding:5px 3px}.private-flow .flow-end small{font-size:11px}}
@media(prefers-reduced-motion:reduce){.flow-packet.moved,.private-balance,.reimbursement-edge{animation:none}}
</style>
