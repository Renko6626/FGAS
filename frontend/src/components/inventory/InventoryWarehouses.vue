<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { NDrawer, NDrawerContent } from "naive-ui";
import type { StockAccount } from "../../api/accounts";
import type { InventoryRow, InventoryTotals, StockTransfer } from "../../api/warehouse";
import { useWarehouseGraph } from "./useWarehouseGraph";

// Inventory and transfer rules stay upstream; this view only presents their results.
const props = defineProps<{ locations: StockAccount[]; locationCodes: string[]; rows: InventoryRow[]; totals: InventoryTotals[]; transfers: StockTransfer[]; onlyPending: boolean }>();
const selectedWarehouse = defineModel<string>("selectedWarehouse", { default: "" });
const selectedGoods = ref("");
const routeKey = ref("");
const drawerOpen = ref(false);
const visibleSkus = computed(() => new Set(props.totals.map(item => item.sku_code)));
const plans = computed(() => props.transfers.filter(plan => plan.lines.some(line => visibleSkus.value.has(line.sku_code))));
const scope = computed(() => new Set(props.locationCodes));
const place = computed(() => props.locations.find(item => item.code === selectedWarehouse.value && item.kind === "internal"));
const localRows = computed(() => props.rows.filter(row => row.account_code === selectedWarehouse.value && visibleSkus.value.has(row.sku_code)));
const goods = computed(() => props.totals.flatMap(item => {
  const row = localRows.value.find(row => row.sku_code === item.sku_code && BigInt(row.quantity) > 0n);
  return row ? [row] : [];
}));
const rackArea = ref<HTMLElement | null>(null);
const columns = ref(6);
const rackPage = ref(1);
const pageSize = computed(() => columns.value * 4);
const pageCount = computed(() => Math.max(1, Math.ceil(goods.value.length / pageSize.value)));
const shelves = computed(() => {
  const items = goods.value.slice((rackPage.value - 1) * pageSize.value, rackPage.value * pageSize.value);
  return Array.from({ length: 4 }, (_, index) => {
    const start = (3 - index) * columns.value;
    return items.slice(start, start + columns.value);
  });
});
function binSize(quantity: string) { const value = BigInt(quantity); return value < 10n ? "small" : value < 50n ? "medium" : "large"; }
let rackObserver: ResizeObserver | undefined;
onMounted(() => {
  rackObserver = new ResizeObserver(entries => {
    const width = entries[0]?.contentRect.width;
    if (width) columns.value = Math.max(3, Math.min(6, Math.floor(width / 145)));
  });
  if (rackArea.value) rackObserver.observe(rackArea.value);
});
watch(rackArea, (area, previous) => {
  if (previous) rackObserver?.unobserve(previous);
  if (area) rackObserver?.observe(area);
});
onBeforeUnmount(() => rackObserver?.disconnect());
watch([selectedWarehouse, goods, columns], () => { rackPage.value = 1; selectedGoods.value = ""; });
watch(rackPage, () => { selectedGoods.value = ""; });
const localPlans = computed(() => plans.value.filter(plan => plan.source_account_code === selectedWarehouse.value || plan.destination_account_code === selectedWarehouse.value));
const shownPlans = computed(() => localPlans.value.filter(plan => !selectedGoods.value || plan.lines.some(line => line.sku_code === selectedGoods.value)));
function countGoods(code: string) { return props.rows.filter(row => row.account_code === code && visibleSkus.value.has(row.sku_code) && BigInt(row.quantity) > 0n).length; }
function countPlans(code: string) { return plans.value.filter(plan => plan.source_account_code === code || plan.destination_account_code === code).length; }
function status(plan: StockTransfer) { return plan.status === "pending" ? "待审批" : plan.confirmations.some(item => item.status === "pending") ? "已报告完成，待确认" : "待完成"; }
function lineSummary(plan: StockTransfer) { return plan.lines.map(line => `${line.sku_name} × ${line.quantity} ${line.unit}`).join("，"); }

const nodes = computed(() => {
  const involved = new Set(plans.value.flatMap(plan => [plan.source_account_code, plan.destination_account_code]));
  const internal = props.locations.filter(item => item.kind === "internal" &&
    ((scope.value.has(item.code) && (!props.onlyPending || involved.has(item.code))) || involved.has(item.code)));
  const external = props.locations.filter(item => item.kind === "external" && involved.has(item.code));
  return [
    ...internal.map((item, index) => ({ ...item, x: 330 + index % 2 * 350, y: 92 + Math.floor(index / 2) * 240, width: 230, height: 138 })),
    ...external.map((item, index) => ({ ...item, x: 22, y: 100 + index * 220, width: 190, height: 120 })),
  ];
});
const graphHeight = computed(() => Math.max(480, ...nodes.value.map(node => node.y + node.height + 80)));
const graphBounds = computed(() => {
  const left = nodes.value.length ? Math.min(...nodes.value.map(node => node.x)) - 65 : 0;
  const right = nodes.value.length ? Math.max(...nodes.value.map(node => node.x + node.width)) + 65 : 1000;
  return { x: left, y: 0, width: right - left, height: graphHeight.value };
});
const graph = useWarehouseGraph(graphBounds);
const graphViewport = graph.viewport;
const hasExternalNodes = computed(() => nodes.value.some(node => node.kind === "external"));
const routes = computed(() => {
  const groups = new Map<string, StockTransfer[]>();
  for (const plan of plans.value) {
    const key = `${plan.source_account_code}:${plan.destination_account_code}:${plan.status}`;
    groups.set(key, [...(groups.get(key) || []), plan]);
  }
  return [...groups].flatMap(([key, items]) => {
    const first = items[0]!;
    const source = nodes.value.find(node => node.code === first.source_account_code);
    const destination = nodes.value.find(node => node.code === first.destination_account_code);
    if (!source || !destination) return [];
    const sx = source.x + source.width / 2, sy = source.y + source.height / 2;
    const dx = destination.x + destination.width / 2, dy = destination.y + destination.height / 2;
    const vx = dx - sx, vy = dy - sy, length = Math.hypot(vx, vy) || 1;
    const sourceScale = Math.min((source.width / 2 + 9) / (Math.abs(vx) || 1), (source.height / 2 + 9) / (Math.abs(vy) || 1));
    const destScale = Math.min((destination.width / 2 + 12) / (Math.abs(vx) || 1), (destination.height / 2 + 12) / (Math.abs(vy) || 1));
    const x1 = sx + vx * sourceScale, y1 = sy + vy * sourceScale;
    const x2 = dx - vx * destScale, y2 = dy - vy * destScale;
    const bend = first.status === "pending" ? 70 : -34;
    const cx = (x1 + x2) / 2 - vy / length * bend, cy = (y1 + y2) / 2 + vx / length * bend;
    return [{ key, items, pending: first.status === "pending", source: source.name, destination: destination.name,
      path: `M ${x1} ${y1} Q ${cx} ${cy} ${x2} ${y2}`,
      labelX: (x1 + 2 * cx + x2) / 4, labelY: (y1 + 2 * cy + y2) / 4 }];
  });
});
const activeRoute = computed(() => routes.value.find(route => route.key === routeKey.value));
function openRoute(key: string) { routeKey.value = key; drawerOpen.value = true; }
function enter(code: string) { selectedWarehouse.value = code; selectedGoods.value = ""; }
watch(() => props.locationCodes.join("|"), () => { if (selectedWarehouse.value && !scope.value.has(selectedWarehouse.value)) selectedWarehouse.value = ""; });
</script>

<template>
  <section class="warehouse-view">
    <template v-if="!place">
      <header class="sketch-heading">
        <div><h2>仓库之间</h2><p>点一个仓库进去看看，点虚线查看交接单。</p></div>
        <div class="sketch-key"><span><i></i>待完成</span><span class="approval"><i></i>待审批</span></div>
      </header>
      <div v-if="nodes.length" class="graph-toolbar" role="group" aria-label="关系图缩放">
        <span>拖动画布移动，滚轮缩放</span>
        <button :disabled="graph.scale.value <= graph.minScale.value" aria-label="缩小关系图" @click="graph.zoom(1 / 1.2)">−</button>
        <output aria-label="当前缩放比例">{{ graph.percentage.value }}%</output>
        <button :disabled="graph.scale.value >= 2" aria-label="放大关系图" @click="graph.zoom(1.2)">＋</button>
        <button class="fit-graph" @click="graph.fit">适应画布</button>
      </div>
      <div v-if="nodes.length" ref="graphViewport" class="graph-viewport" :class="{ dragging: graph.dragging.value }" :style="{ aspectRatio: `${graphBounds.width} / ${graphBounds.height}` }" tabindex="0" role="region" aria-label="仓库关系图，可拖动和缩放；方向键移动，加减键缩放，Home 键适应画布"
        @pointerdown="graph.pointerDown" @pointermove="graph.pointerMove" @pointerup="graph.pointerEnd" @pointercancel="graph.pointerEnd" @lostpointercapture.self="graph.pointerEnd" @pointerleave="graph.pointerLeave" @click.capture="graph.click" @wheel.prevent="graph.wheel" @keydown="graph.keydown">
        <div class="graph-paper" :style="{ height: `${graphHeight}px`, transform: graph.transform.value }">
          <span v-if="hasExternalNodes" class="graph-label external-label">外部联系</span><span class="graph-label internal-label">仓库与代管地点</span>
          <svg class="graph-lines" width="1000" :height="graphHeight" aria-label="待处理货物转移">
            <defs>
              <marker id="warehouse-arrow-green" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" orient="auto-start-reverse"><path d="M 1 1 L 9 5 L 1 9" /></marker>
              <marker id="warehouse-arrow-amber" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" orient="auto-start-reverse"><path d="M 1 1 L 9 5 L 1 9" /></marker>
            </defs>
            <g v-for="route in routes" :key="route.key" class="graph-route" :class="{ approval: route.pending }" role="button" tabindex="0" :aria-label="`${route.source}到${route.destination}，${route.items.length}笔${route.pending ? '待审批' : '待完成'}，查看单据`" @click="openRoute(route.key)" @keydown.enter.prevent="openRoute(route.key)" @keydown.space.prevent="openRoute(route.key)">
              <path :d="route.path" class="route-hit" /><path :d="route.path" class="route-stroke" :marker-end="`url(#warehouse-arrow-${route.pending ? 'amber' : 'green'})`" />
              <g :transform="`translate(${route.labelX},${route.labelY})`"><rect x="-48" y="-14" width="96" height="28" rx="5" /><text text-anchor="middle" dominant-baseline="central">{{ route.items.length }} 笔{{ route.pending ? '待审批' : '待完成' }}</text></g>
            </g>
          </svg>
          <template v-for="node in nodes" :key="node.code">
            <button v-if="node.kind === 'internal'" class="warehouse-node" :class="{ context: !scope.has(node.code) }" :style="{ left: `${node.x}px`, top: `${node.y}px`, width: `${node.width}px`, height: `${node.height}px` }" @click="enter(node.code)">
              <span class="node-top"><span>{{ !scope.has(node.code) ? '关联地点' : node.member_name || '未指定负责人' }}</span><span aria-hidden="true">↗</span></span>
              <strong>{{ node.name }}</strong>
              <span class="node-foot"><span>{{ countGoods(node.code) }} 种货物</span><span v-if="countPlans(node.code)" class="pending-count">{{ countPlans(node.code) }} 笔待处理</span><span v-else>暂无交接</span></span>
            </button>
            <div v-else class="external-node" :style="{ left: `${node.x}px`, top: `${node.y}px`, width: `${node.width}px`, height: `${node.height}px` }"><small>外部账户</small><strong>{{ node.name }}</strong><span>仅显示交接关系</span></div>
          </template>
        </div>
      </div>
      <p v-else class="empty-sketch">当前没有符合筛选的仓库或待处理转移。</p>
      <footer class="sketch-foot"><span>虚线表示待处理转移，完成后才计入库存。</span><span>地点位置仅为示意</span></footer>
    </template>

    <template v-else>
      <header class="room-navigation"><button @click="enter('')">← 全部仓库</button><span>{{ place.code }}</span></header>
      <header class="sketch-heading room-heading"><div><h2>{{ place.name }}</h2><p>负责人：{{ place.member_name || '未指定' }}</p></div><span class="room-count">{{ goods.length }} 种货物在库</span></header>
      <div class="room-floor">
        <div class="room-label"><span>在库货物</span><small>点箱子查看相关交接</small></div>
        <div ref="rackArea" class="goods-floor">
          <div class="storage-rack" :style="{ '--rack-columns': columns }">
            <div v-for="(shelf, shelfIndex) in shelves" :key="shelfIndex" class="rack-shelf">
              <p v-if="!goods.length && shelfIndex === 1" class="rack-empty">{{ localPlans.length ? '货物还没入库，交接单在下面。' : '当前筛选范围内，这里还没有已入账货物。' }}</p>
              <button v-for="item in shelf" :key="item.sku_code" class="goods-bin" :class="[binSize(item.quantity), { selected: selectedGoods === item.sku_code }]" :aria-label="`${item.sku_name}，${item.quantity}${item.unit}，查看相关交接`" :title="`${item.sku_code}　${item.sku_name} × ${item.quantity} ${item.unit}`" :aria-pressed="selectedGoods === item.sku_code" @click="selectedGoods = selectedGoods === item.sku_code ? '' : item.sku_code">
                <span class="bin-label"><strong>{{ item.sku_name }}</strong><span>× {{ item.quantity }} <small>{{ item.unit }}</small></span></span>
              </button>
            </div>
          </div>
        </div>
        <nav v-if="pageCount > 1" class="rack-pagination" aria-label="货架分页">
          <button :disabled="rackPage === 1" @click="rackPage--">上一页</button>
          <span aria-live="polite">第 {{ rackPage }} / {{ pageCount }} 页</span>
          <button :disabled="rackPage === pageCount" @click="rackPage++">下一页</button>
          <small>每页最多 {{ pageSize }} 种货物</small>
        </nav>
        <p class="room-note">每个箱形代表一种货物，数量以标签为准。</p>
      </div>
      <section class="handoff-area">
        <header><div><h3>待交接 <small>{{ shownPlans.length }} 笔</small></h3><p>{{ selectedGoods ? '只看所选货物的相关单据' : '待入货物尚未入库，待出货物仍计入当前库存。' }}</p></div><button v-if="selectedGoods" @click="selectedGoods = ''">显示全部交接</button></header>
        <div class="handoff-list">
          <a v-for="plan in shownPlans" :key="plan.code" :href="`#stock?code=${encodeURIComponent(plan.code)}`" class="handoff-card" :class="{ approval: plan.status === 'pending' }">
            <span class="handoff-status"><span>{{ plan.destination_account_code === place.code ? '待入' : '待出' }}</span><span>{{ status(plan) }}</span></span>
            <strong>{{ plan.source_account_name }} → {{ plan.destination_account_name }}</strong><p>{{ lineSummary(plan) }}</p><span class="handoff-code">{{ plan.code }}<span>查看单据 ↗</span></span>
          </a>
        </div>
        <p v-if="!shownPlans.length" class="empty-handoffs">目前没有相关的待交接单据。</p>
      </section>
    </template>

    <NDrawer v-model:show="drawerOpen" :width="440" style="max-width:100vw" placement="right">
      <NDrawerContent title="仓库间的交接" closable>
        <template v-if="activeRoute"><p class="route-title">{{ activeRoute.source }} → {{ activeRoute.destination }}</p>
          <a v-for="plan in activeRoute.items" :key="plan.code" :href="`#stock?code=${encodeURIComponent(plan.code)}`" class="handoff-card drawer-plan" :class="{ approval: plan.status === 'pending' }"><span class="handoff-status">{{ status(plan) }}</span><strong>{{ plan.code }}</strong><p>{{ lineSummary(plan) }}</p><span class="handoff-code">{{ plan.effective_date }}<span>查看单据 ↗</span></span></a>
        </template><p v-else>这条连线已没有符合条件的待处理转移。</p>
      </NDrawerContent>
    </NDrawer>
  </section>
</template>

<style scoped>
.warehouse-view { --sketch-ink:#365550; --sketch-muted:#6d817b; --sketch-line:#8ca79b; --sketch-green:#387562; --sketch-amber:#946a2d; color:var(--sketch-ink); min-width:0; }
.warehouse-view button { font:inherit; cursor:pointer; color:inherit; }
.warehouse-view button:focus-visible,.graph-route:focus-visible { outline:2px solid #387562; outline-offset:5px; }
.sketch-heading { display:flex; align-items:center; justify-content:space-between; gap:20px; padding:20px 4px 18px; }
.sketch-heading h2 { margin:0 0 7px; font-size:25px; font-weight:500; font-family:var(--serif,serif); }
.sketch-heading p,.handoff-area header p { font-size:12px; color:var(--sketch-muted); margin:0; }
.sketch-key { display:flex; gap:20px; font-size:12px; white-space:nowrap; }
.sketch-key span { display:flex; align-items:center; gap:7px; }
.sketch-key i { width:22px; border-top:2px dashed var(--sketch-green); }
.sketch-key .approval i { border-color:var(--sketch-amber); }
.graph-toolbar { display:flex; align-items:center; gap:6px; padding:0 0 9px; font-size:12px; color:var(--sketch-muted); }
.graph-toolbar > span { margin-right:auto; font-size:11px; }.graph-toolbar output { min-width:44px; text-align:center; font-variant-numeric:tabular-nums; }
.graph-toolbar button { min-width:30px; height:28px; border:1px solid #c8d5ca; border-radius:3px; background:#fff; padding:0 7px; }.graph-toolbar button:disabled { opacity:.4; cursor:default; }.graph-toolbar .fit-graph { margin-left:5px; }
.graph-viewport { position:relative; width:100%; min-width:0; min-height:280px; max-height:min(65vh,640px); overflow:hidden; border:1px solid #dbe5df; border-radius:9px 3px 10px 4px; background:#fbfdfb; cursor:grab; touch-action:none; user-select:none; }
.graph-viewport.dragging,.graph-viewport.dragging * { cursor:grabbing !important; }
.graph-paper { position:absolute; top:0; left:0; width:1000px; transform-origin:0 0; background-image:radial-gradient(#cddbd2 .7px,transparent .7px); background-size:20px 20px; }
.graph-label { position:absolute; top:26px; font-size:12px; color:var(--sketch-muted); }
.external-label { left:30px; }.internal-label { left:330px; }
.graph-lines { position:absolute; inset:0; overflow:visible; }
.graph-route { cursor:pointer; color:var(--sketch-green); outline:none; }
.graph-route.approval { color:var(--sketch-amber); }
.route-stroke { fill:none; stroke:currentColor; stroke-width:1.7; stroke-dasharray:7 6; }
.route-hit { fill:none; stroke:transparent; stroke-width:25; }
.graph-route:hover .route-stroke,.graph-route:focus .route-stroke { stroke-width:3; }
.graph-route rect { fill:#fbfdfb; stroke:#dbe5df; }
.graph-route text { fill:currentColor; font-size:11px; font-family:inherit; }
#warehouse-arrow-green path { stroke:#387562; fill:none; stroke-width:1.3; }
#warehouse-arrow-amber path { stroke:#946a2d; fill:none; stroke-width:1.3; }
.warehouse-node,.external-node { position:absolute; box-sizing:border-box; display:flex; flex-direction:column; justify-content:space-between; text-align:left; padding:17px 20px; }
.warehouse-node { background:#fcfefd; border:1.5px solid #789688; border-radius:5px 8px 3px 7px; box-shadow:4px 5px 0 #ecf2ed; }
.warehouse-node::before { content:''; position:absolute; inset:4px -5px -5px 4px; border:1px solid #bdcec2; border-radius:7px 3px 8px 4px; pointer-events:none; }
.warehouse-node:hover { background:#eef6ef; border-color:#387562; }
.warehouse-node.context { border-style:dashed; }
.node-top,.node-foot { display:flex; justify-content:space-between; align-items:center; gap:8px; font-size:11px; color:var(--sketch-muted); }
.warehouse-node strong { font-size:18px; font-weight:550; overflow:hidden; white-space:nowrap; text-overflow:ellipsis; }
.pending-count { color:var(--sketch-amber); }
.external-node { border:1px dashed #a8b6ad; border-radius:4px 9px 4px 3px; background:#f6f9f6; }
.external-node small,.external-node span { font-size:11px; color:var(--sketch-muted); }.external-node strong { font-size:15px; }
.sketch-foot { display:flex; flex-wrap:wrap; justify-content:space-between; gap:8px; padding:13px 3px; font-size:11px; color:var(--sketch-muted); }
.room-navigation { display:flex; justify-content:space-between; align-items:center; padding:14px 0 0; font-size:12px; color:var(--sketch-muted); }
.room-navigation button,.handoff-area header button { background:none; border:0; padding:4px 0; font-size:12px; color:var(--sketch-green); }
.room-heading { padding:10px 0 14px; }.room-count { font-size:12px; }
.room-floor { padding:12px 16px 0; border-top:1px solid #d8ded8; background:#fdfefc; }
.room-label { display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px; font-size:11px; color:#777e70; }
.room-label small { font-size:11px; }
.goods-floor { padding:18px 0 12px; }
.storage-rack { position:relative; width:100%; padding:6px 8px 16px; border-top:3px double #8b978c; }
.storage-rack::before,.storage-rack::after { content:''; position:absolute; top:-3px; bottom:0; width:5px; border:1px solid #8b978c; background:#eef1eb; }
.storage-rack::before { left:0; }.storage-rack::after { right:0; }
.rack-shelf { display:grid; grid-template-columns:repeat(var(--rack-columns),minmax(0,1fr)); align-items:end; justify-items:center; min-height:124px; gap:8px; padding:12px 8px 0; border-bottom:4px solid #9ba699; }
.warehouse-view .goods-bin { position:relative; display:flex; align-items:center; justify-content:center; min-width:0; width:96%; min-height:104px; padding:20px 8px 10px; border:1px solid #9da999; border-top:5px double #9da999; border-radius:0; background:#e9eee4; box-shadow:none; color:#485345; text-align:center; }
.warehouse-view .goods-bin.small { width:76%; min-height:76px; }.warehouse-view .goods-bin.medium { width:86%; min-height:88px; }
.goods-bin::before { content:''; position:absolute; top:6px; left:calc(50% - 13px); width:26px; height:4px; border:1px solid #a2ae9c; background:#fdfefc; }
.warehouse-view .goods-bin:hover { background:#e0e8da; border-color:#60846a; }.warehouse-view .goods-bin.selected { background:#dce8d8; border-color:#387562; outline:2px solid #387562; outline-offset:1px; }
.bin-label { display:flex; flex-direction:column; justify-content:center; gap:4px; width:100%; padding:3px 2px; background:#fafbf6; }
.bin-label strong { font-size:12px; font-weight:500; line-height:1.4; overflow-wrap:anywhere; display:-webkit-box; -webkit-box-orient:vertical; -webkit-line-clamp:2; overflow:hidden; }
.bin-label > span { font-size:18px; font-variant-numeric:tabular-nums; line-height:1.3; overflow-wrap:anywhere; }.bin-label small { font-size:10px; }
.rack-empty { grid-column:1 / -1; align-self:center; margin:0; font-size:12px; color:var(--sketch-muted); text-align:center; }
.rack-pagination { display:flex; justify-content:center; align-items:center; flex-wrap:wrap; gap:12px; padding:4px 0 10px; font-size:12px; }
.rack-pagination button { padding:4px 10px; border:1px solid #b3beb1; background:transparent; border-radius:2px; }.rack-pagination button:disabled { color:#a5ada2; cursor:default; border-color:#dde2d9; }.rack-pagination small { font-size:11px; color:var(--sketch-muted); }
.room-note { margin:0; padding:4px 0 10px; text-align:right; color:#8b9083; font-size:10px; }
.handoff-area { margin-top:20px; }.handoff-area header { display:flex; align-items:center; justify-content:space-between; gap:15px; margin-bottom:10px; }
.handoff-area h3 { font-size:16px; font-weight:500; margin:0 0 6px; }.handoff-area h3 small { font-size:12px; color:var(--sketch-muted); margin-left:8px; }
.handoff-list { display:block; }
.handoff-list .handoff-card { display:grid; grid-template-columns:100px minmax(0,1fr) minmax(0,1.2fr) 86px; align-items:center; gap:12px; border:0; border-top:1px solid #e4e7df; border-radius:0; background:transparent; padding:10px 0; }
.handoff-list .handoff-card:hover { background:#f5f7f1; }.handoff-list .handoff-status { flex-direction:column; gap:2px; margin:0; }.handoff-list .handoff-card p { margin:0; }.handoff-list .handoff-code { flex-direction:column; gap:3px; }
.handoff-card { display:block; border:1px dashed #8fae9d; border-radius:3px 6px 4px 8px; padding:15px 18px; text-decoration:none; color:#365550; background:#fcfefd; }
.handoff-card.approval { border-color:#c4aa80; }.handoff-card:hover { background:#f1f7f1; }
.handoff-status { display:flex; justify-content:space-between; gap:10px; font-size:11px; color:#387562; margin-bottom:10px; }.approval .handoff-status { color:#946a2d; }
.handoff-card > strong { font-weight:500; font-size:13px; line-height:1.6; }.handoff-card p { margin:9px 0 16px; font-size:12px; line-height:1.8; color:#60766c; }
.handoff-code { display:flex; justify-content:space-between; gap:10px; font-size:10px; color:#6d817b; }
.drawer-plan { margin-bottom:14px; }.route-title { font-size:14px; color:#365550; }
.empty-sketch { padding:55px 16px; text-align:center; font-size:13px; color:var(--sketch-muted); }.empty-handoffs { padding:14px 0; font-size:12px; color:var(--sketch-muted); }
@media(max-width:760px) {
  .sketch-heading { align-items:flex-start; gap:12px; flex-wrap:wrap; }.sketch-heading h2 { font-size:23px; }.sketch-key { gap:16px; }
  .graph-toolbar { flex-wrap:wrap; }.graph-toolbar > span { flex-basis:100%; margin-bottom:3px; }.room-floor { padding:10px 0 0; }.goods-floor { padding:14px 4px 12px; }
  .storage-rack { padding:4px 5px 12px; }.rack-shelf { gap:5px; padding:12px 5px 0; }.warehouse-view .goods-bin { padding:18px 3px 7px; }.warehouse-view .goods-bin.small { width:86%; min-height:84px; }.warehouse-view .goods-bin.medium { width:92%; min-height:94px; }.bin-label strong { font-size:11px; }.bin-label > span { font-size:16px; }
  .room-count { font-size:12px; }.handoff-area header { align-items:flex-start; }.room-label { padding:0 8px; }
  .handoff-list .handoff-card { grid-template-columns:70px minmax(0,1fr); gap:5px 12px; }.handoff-list .handoff-status { grid-row:span 2; }.handoff-list .handoff-card p { grid-column:2; }.handoff-list .handoff-code { grid-column:2; flex-direction:row; }
}
</style>
