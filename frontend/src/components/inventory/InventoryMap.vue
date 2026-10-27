<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import type { StockAccount } from "../../api/accounts";
import type { InventoryRow, InventoryTotals, Sku, StockTransfer } from "../../api/warehouse";

const props = defineProps<{ selectedSku: string; totals: InventoryTotals[]; rows: InventoryRow[]; locations: StockAccount[]; locationCodes: string[]; skus: Sku[]; transfers: StockTransfer[] }>();
const selectedSku = computed(() => props.selectedSku);
const selectedLocation = ref("");
const selectedRoute = ref("");
const showEmpty = ref(false);
const mapViewport = ref<HTMLElement | null>(null);
const focused = computed(() => props.totals.find(item => item.sku_code === selectedSku.value));
const metadata = computed(() => props.skus.find(item => item.code === selectedSku.value));
const skuRows = computed(() => new Map(props.rows.filter(row => row.sku_code === selectedSku.value).map(row => [row.account_code, row])));
const plans = computed(() => props.transfers.filter(item => item.status === "in_transit" && item.lines.some(line => line.sku_code === selectedSku.value)));
const planSummary = computed(() => {
  const quantities = { incoming: 0n, outgoing: 0n, internal: 0n };
  for (const plan of plans.value) {
    const quantity = BigInt(plan.lines.find(line => line.sku_code === selectedSku.value)!.quantity);
    if (plan.source_kind === "external") quantities.incoming += quantity;
    else if (plan.destination_kind === "external") quantities.outgoing += quantity;
    else quantities.internal += quantity;
  }
  return quantities;
});
const pendingTransfers = computed(() => props.transfers.filter(item => item.lines.some(line => line.sku_code === selectedSku.value)));
const locationPlans = computed(() => {
  const quantities = new Map<string, { incoming: bigint; outgoing: bigint }>();
  for (const plan of plans.value) {
    const quantity = BigInt(plan.lines.find(line => line.sku_code === selectedSku.value)!.quantity);
    const source = quantities.get(plan.source_account_code) || { incoming: 0n, outgoing: 0n };
    source.outgoing += quantity;
    quantities.set(plan.source_account_code, source);
    const destination = quantities.get(plan.destination_account_code) || { incoming: 0n, outgoing: 0n };
    destination.incoming += quantity;
    quantities.set(plan.destination_account_code, destination);
  }
  return quantities;
});
const involvedCodes = computed(() => new Set(plans.value.flatMap(item => [item.source_account_code, item.destination_account_code])));
const internalPlaces = computed(() => props.locations.filter(item => item.kind === "internal" && (involvedCodes.value.has(item.code) || (props.locationCodes.includes(item.code) && (showEmpty.value || BigInt(skuRows.value.get(item.code)?.quantity || "0") !== 0n)))).sort((a, b) => {
  const difference = BigInt(skuRows.value.get(b.code)?.quantity || "0") - BigInt(skuRows.value.get(a.code)?.quantity || "0");
  return difference > 0n ? 1 : difference < 0n ? -1 : a.name.localeCompare(b.name, "zh-CN");
}));

interface MapNode {
  code: string; name: string; member: string | null; kind: "internal" | "external";
  role: "internal" | "source" | "destination"; x: number; y: number; width: number;
  quantity: string; incoming: string; outgoing: string;
}
const twoColumns = computed(() => internalPlaces.value.length > 3);
const mapWidth = computed(() => 1040);
const nodes = computed(() => {
  const result: MapNode[] = internalPlaces.value.map((place, index) => {
    const row = skuRows.value.get(place.code);
    return { code: place.code, name: place.name, member: place.member_name, kind: "internal", role: "internal",
      x: twoColumns.value ? 390 + (index % 2) * 280 : 520,
      y: 140 + (twoColumns.value ? Math.floor(index / 2) : index) * 180,
      width: twoColumns.value ? 210 : 260,
      quantity: row?.quantity || "0", incoming: (locationPlans.value.get(place.code)?.incoming || 0n).toString(), outgoing: (locationPlans.value.get(place.code)?.outgoing || 0n).toString() };
  });
  const sources = new Map<string, string>();
  const destinations = new Map<string, string>();
  for (const plan of plans.value) {
    if (plan.source_kind === "external") sources.set(plan.source_account_code, plan.source_account_name);
    if (plan.destination_kind === "external") destinations.set(plan.destination_account_code, plan.destination_account_name);
  }
  for (const [role, items] of [["source", sources], ["destination", destinations]] as const) {
    [...items].forEach(([code, name], index) => result.push({ code, name, member: props.locations.find(place => place.code === code)?.member_name || null,
      kind: "external", role, x: role === "source" ? 100 : mapWidth.value - 100, y: 140 + index * 180, width: 170,
      quantity: "0", incoming: "0", outgoing: "0" }));
  }
  return result;
});
const mapHeight = computed(() => Math.max(390, ...nodes.value.map(node => node.y + 110)));
const internalNodes = computed(() => nodes.value.filter(node => node.kind === "internal"));
const focusedNode = computed(() => nodes.value.find(node => node.code === selectedLocation.value && node.kind === "internal"));

const routes = computed(() => {
  const grouped = new Map<string, { source: MapNode; destination: MapNode; quantity: bigint; plans: StockTransfer[] }>();
  for (const plan of plans.value) {
    const source = nodes.value.find(node => node.code === plan.source_account_code && (node.role === "internal" || node.role === "source"));
    const destination = nodes.value.find(node => node.code === plan.destination_account_code && (node.role === "internal" || node.role === "destination"));
    if (!source || !destination) continue;
    const key = `${source.code}:${destination.code}`;
    const group = grouped.get(key) || { source, destination, quantity: 0n, plans: [] };
    group.quantity += BigInt(plan.lines.find(line => line.sku_code === selectedSku.value)!.quantity);
    group.plans.push(plan);
    grouped.set(key, group);
  }
  return [...grouped].map(([key, route]) => {
    const { source, destination } = route;
    const sameColumn = source.x === destination.x;
    const direction = destination.x >= source.x ? 1 : -1;
    const startX = source.x + (sameColumn ? 1 : direction) * (source.width / 2 + 4);
    const endX = destination.x - (sameColumn ? -1 : direction) * (destination.width / 2 + 8);
    const controlX = Math.max(startX, endX) + 105;
    const bend = (endX - startX) * 0.5;
    return { ...route, key, quantity: route.quantity.toString(),
      kind: source.kind === "external" ? "incoming" : destination.kind === "external" ? "outgoing" : "internal",
      path: sameColumn
        ? `M ${startX} ${source.y} C ${controlX} ${source.y}, ${controlX} ${destination.y}, ${endX} ${destination.y}`
        : `M ${startX} ${source.y} C ${startX + bend} ${source.y}, ${endX - bend} ${destination.y}, ${endX} ${destination.y}`,
      labelX: sameColumn ? controlX - 20 : (startX + endX) / 2,
      labelY: (source.y + destination.y) / 2,
    };
  });
});
const shownPlans = computed(() => pendingTransfers.value.filter(plan => {
  if (selectedRoute.value) return `${plan.source_account_code}:${plan.destination_account_code}` === selectedRoute.value;
  return !selectedLocation.value || plan.source_account_code === selectedLocation.value || plan.destination_account_code === selectedLocation.value;
}));
function selectNode(node: MapNode) { selectedLocation.value = selectedLocation.value === node.code ? "" : node.code; selectedRoute.value = ""; }
function selectRoute(key: string) { selectedRoute.value = selectedRoute.value === key ? "" : key; selectedLocation.value = ""; }
function routeDimmed(source: string, destination: string, key: string) {
  return !!((selectedLocation.value && selectedLocation.value !== source && selectedLocation.value !== destination) || (selectedRoute.value && selectedRoute.value !== key));
}
function share(quantity: string) {
  const total = BigInt(focused.value?.quantity || "0");
  return total > 0n ? `${Number(BigInt(quantity) * 1000n / total) / 10}%` : "0%";
}
function planQuantity(plan: StockTransfer) { return plan.lines.find(line => line.sku_code === selectedSku.value)?.quantity; }
async function centerMap() {
  await nextTick();
  const viewport = mapViewport.value;
  if (viewport) viewport.scrollLeft = (viewport.scrollWidth - viewport.clientWidth) / 2;
}
watch([selectedSku, () => props.locationCodes.join("|"), () => props.transfers], () => { selectedLocation.value = ""; selectedRoute.value = ""; });
watch([mapWidth, selectedSku], centerMap);
onMounted(centerMap);
</script>

<template>
    <section v-if="focused" class="map-main" aria-label="所选货物的保管分布与待完成转移">
      <header class="map-product">
        <div class="product-identity"><img v-if="metadata?.avatar_url" :src="metadata.avatar_url" :alt="focused.sku_name" /><h3>{{ focused.sku_name }}<small>{{ selectedSku }}</small></h3></div>
        <div class="map-total"><span>社团账面库存</span><strong>{{ focused.quantity }}<small>{{ focused.unit }}</small></strong></div>
      </header>
      <div class="mobile-place-list">
        <button v-for="node in internalNodes" :key="node.code" :class="{ selected: selectedLocation === node.code }" @click="selectNode(node)"><span><strong>{{ node.name }}</strong><small>{{ locationCodes.includes(node.code) ? '' : '关联地点：' }}{{ node.member || '未指定负责人' }}</small></span><span><strong>{{ node.quantity }} <small>{{ focused.unit }}</small></strong><small v-if="BigInt(node.incoming) > 0n">待入 {{ node.incoming }}</small><small v-if="BigInt(node.outgoing) > 0n">待出 {{ node.outgoing }}</small></span></button>
        <p v-if="!internalNodes.length" class="no-plans">当前没有库存或待完成转移。</p>
      </div>
      <div ref="mapViewport" class="map-viewport" tabindex="0" role="region" aria-label="货物沙盘，可左右滚动">
        <svg class="map-stage" :viewBox="`0 0 ${mapWidth} ${mapHeight}`" :style="{ aspectRatio: `${mapWidth} / ${mapHeight}` }" aria-label="货物保管地点和计划转移关系图">
          <defs>
            <pattern id="inventory-map-grid" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="#dce6e5" /></pattern>
            <marker v-for="[kind, color] in [['incoming', '#40887a'], ['outgoing', '#b78a40'], ['internal', '#64859d']]" :id="`inventory-arrow-${kind}`" :key="kind" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L7,3 L0,6" fill="none" :stroke="color" stroke-width="1.8" /></marker>
          </defs>
          <rect width="100%" height="100%" fill="#f7faf9" />
          <rect x="265" y="12" :width="mapWidth - 530" :height="mapHeight - 24" rx="16" fill="#edf4f1" />
          <rect width="100%" height="100%" fill="url(#inventory-map-grid)" />
          <text x="32" y="40" class="lane-label">外部来源</text><text :x="mapWidth / 2" y="40" text-anchor="middle" class="lane-label internal-lane">社团保管</text><text :x="mapWidth - 32" y="40" text-anchor="end" class="lane-label">外部去向</text>
          <g v-for="route in routes" :key="route.key" class="map-route" :class="[route.kind, { dimmed: routeDimmed(route.source.code, route.destination.code, route.key), selected: selectedRoute === route.key }]" tabindex="0" role="button" :aria-label="`${route.source.name}到${route.destination.name}，${route.quantity}${focused.unit}待完成，查看相关单据`" @click="selectRoute(route.key)" @keydown.enter.prevent="selectRoute(route.key)" @keydown.space.prevent="selectRoute(route.key)">
            <path :d="route.path" class="route-hit" /><path :d="route.path" class="route-line" :marker-end="`url(#inventory-arrow-${route.kind})`" />
            <g :transform="`translate(${route.labelX}, ${route.labelY})`" class="route-label"><rect x="-49" y="-14" width="98" height="28" rx="14" /><text text-anchor="middle" dominant-baseline="central">{{ route.kind === 'internal' ? '调拨' : route.kind === 'incoming' ? '待入' : '待出' }} {{ route.quantity }} {{ focused.unit }}</text></g>
          </g>
          <foreignObject v-for="node in nodes" :key="`${node.role}:${node.code}`" :x="node.x - node.width / 2" :y="node.y - 64" :width="node.width" height="134">
            <button xmlns="http://www.w3.org/1999/xhtml" class="map-node" :class="[node.kind, { selected: selectedLocation === node.code, context: node.kind === 'internal' && !locationCodes.includes(node.code) }]" :title="`${node.name}（${node.code}）`" :aria-pressed="selectedLocation === node.code" @click="selectNode(node)">
              <span class="node-caption">{{ node.kind === 'internal' ? `${locationCodes.includes(node.code) ? '' : '关联地点：'}${node.member || '未指定负责人'}` : node.role === 'source' ? '外部来源' : '外部去向' }}</span>
              <strong class="node-name">{{ node.name }}</strong>
              <template v-if="node.kind === 'internal'"><span class="node-quantity">{{ node.quantity }} <small>{{ focused.unit }}</small><span class="node-plans"><small v-if="BigInt(node.incoming) > 0n">待入 {{ node.incoming }}</small><small v-if="BigInt(node.outgoing) > 0n">待出 {{ node.outgoing }}</small></span></span><span class="distribution-track"><span :style="{ width: share(node.quantity) }"></span></span></template>
              <span v-else class="external-note">仅显示与本货物相关的计划</span>
            </button>
          </foreignObject>
          <text v-if="!nodes.some(node => node.role === 'source')" x="125" y="160" text-anchor="middle" class="empty-lane">暂无外部待入</text>
          <text v-if="!nodes.some(node => node.role === 'destination')" :x="mapWidth - 125" y="160" text-anchor="middle" class="empty-lane">暂无对外待出</text>
          <text v-if="!internalNodes.length" :x="mapWidth / 2" y="175" text-anchor="middle" class="empty-lane">当前没有库存或待完成转移</text>
        </svg>
      </div>
      <div class="map-stage-heading"><span class="desktop-map-legend"><i class="stock-symbol"></i>账面库存<i class="route-symbol"></i>待完成转移</span><label><input v-model="showEmpty" type="checkbox" />显示空地点</label></div>
      <div class="map-plans-summary" title="待完成转移尚未改变账面库存">
        <span class="plan-incoming">外部待入 <strong>{{ planSummary.incoming.toString() }}</strong> {{ focused.unit }}</span>
        <span class="plan-outgoing">对外待出 <strong>{{ planSummary.outgoing.toString() }}</strong> {{ focused.unit }}</span>
        <span class="plan-internal">内部调拨 <strong>{{ planSummary.internal.toString() }}</strong> {{ focused.unit }}</span>
      </div>
      <div v-if="selectedLocation || selectedRoute" class="map-context">
        <template v-if="focusedNode"><strong>{{ focusedNode.name }}</strong><span>负责人 {{ focusedNode.member || '未指定' }}</span><span>账面 {{ focusedNode.quantity }} {{ focused.unit }}</span></template>
        <button v-if="selectedLocation || selectedRoute" @click="selectedLocation = ''; selectedRoute = ''">显示全部转移</button>
      </div>
      <section class="map-transfer-section">
        <div class="transfer-heading"><h4>待处理转移 <span>{{ shownPlans.length }} 笔</span></h4><small>仅整笔完成后更新库存</small></div>
        <div v-if="shownPlans.length" class="map-transfer-list">
          <a v-for="plan in shownPlans" :key="plan.code" class="map-transfer" :href="`#stock?code=${encodeURIComponent(plan.code)}`">
            <span class="transfer-direction">{{ plan.source_kind === 'external' ? '外部待入' : plan.destination_kind === 'external' ? '对外待出' : '内部调拨' }}<strong>{{ planQuantity(plan) }} {{ focused.unit }}</strong></span>
            <strong class="transfer-route">{{ plan.source_account_name }}<span>→</span>{{ plan.destination_account_name }}</strong>
            <span class="transfer-meta"><small>{{ plan.code }}</small><small>{{ plan.status === 'pending' ? '待审批' : plan.confirmations.some(item => item.status === 'pending') ? '待完成（有人报告完成，待确认）' : '待完成' }}</small><span>查看单据 ↗</span></span>
          </a>
        </div>
        <p v-else class="no-plans">{{ selectedLocation || selectedRoute ? '此处没有相关的待处理转移。' : '这件货物目前没有待处理转移。' }}</p>
      </section>
    </section>
  <p v-else class="map-empty">没有符合条件的货物，请调整搜索或标签。</p>
</template>

<style scoped>
.map-main { min-width:0; }
.mobile-place-list { display:none; }
.map-product { display:flex; justify-content:space-between; align-items:center; gap:14px; padding:0 0 10px; }
.product-identity { display:flex; gap:12px; align-items:center; min-width:0; }
.product-identity > img { width:32px; height:32px; object-fit:cover; border-radius:4px; }
.product-identity small { color:#839191; font-size:11px; font-weight:400; margin-left:10px; white-space:nowrap; }
.product-identity h3 { margin:0; line-height:1.6; font-size:15px; color:#24473f; }
.map-total { display:flex; align-items:baseline; gap:8px; flex-shrink:0; text-align:right; }
.map-total > span { color:#7a8a85; font-size:11px; }
.map-total > strong { color:#245d50; font-size:24px; font-weight:650; line-height:1.4; font-variant-numeric:tabular-nums; }
.map-total strong small { color:#71867d; font-size:12px; font-weight:400; margin-left:7px; }
.map-plans-summary { display:flex; flex-wrap:wrap; align-items:center; gap:6px 22px; padding:8px 0 12px; font-size:12px; }
.map-plans-summary strong { font-size:16px; font-variant-numeric:tabular-nums; margin-left:4px; }
.map-plans-summary > small { margin-left:auto; font-size:11px; color:#8a9691; }
.plan-incoming { color:#387e6c !important; }
.plan-outgoing { color:#a77c35 !important; }
.plan-internal { color:#607f93 !important; }
.map-stage-heading { display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; font-size:11px; color:#8a9794; margin:8px 0 0; }
.map-stage-heading > span { display:flex; flex-wrap:wrap; align-items:center; gap:6px; }
.stock-symbol { display:inline-block; width:9px; height:9px; border:1px solid #668e7e; border-radius:2px; background:#eef6f0; }
.route-symbol { display:inline-block; width:18px; border-top:2px dashed #638d91; margin-left:10px; }
.map-stage-heading label { display:flex; align-items:center; gap:5px; }
.map-stage-heading input { accent-color:#337a6e; }
.map-viewport { overflow:auto; max-height:580px; border:1px solid #e1eae6; border-radius:10px; scrollbar-width:thin; scrollbar-color:#b6cac2 #f4f8f6; }
.map-stage { display:block; width:100%; min-width:760px; height:auto; }
.lane-label { fill:#87988e; font-size:14px; letter-spacing:1px; }
.internal-lane { fill:#668976; }
.empty-lane { fill:#a6b3ac; font-size:12px; }
.map-route { cursor:pointer; outline:none; }
.map-route.dimmed { opacity:.2; }
.route-line { fill:none; stroke:#64859d; stroke-width:2; stroke-dasharray:6 5; }
.map-route.incoming .route-line { stroke:#40887a; }
.map-route.outgoing .route-line { stroke:#b78a40; }
.map-route.selected .route-line,.map-route:hover .route-line,.map-route:focus .route-line { stroke-width:3.5; }
.route-hit { fill:none; stroke:transparent; stroke-width:24; }
.route-label rect { fill:#fff; stroke:#d8e4de; }
.route-label text { fill:#5f7b87; font-size:13px; font-family:inherit; }
.map-route.incoming .route-label text { fill:#367562; }
.map-route.outgoing .route-label text { fill:#a47a2d; }
.map-node { box-sizing:border-box; display:flex; flex-direction:column; width:calc(100% - 4px); height:125px; margin:2px; border:1px solid #cadfd3; border-radius:9px; padding:14px 16px 11px; background:#fff; text-align:left; color:#33594b; box-shadow:0 4px 10px #254b3610; min-width:0; cursor:pointer; }
.map-node:hover,.map-node.selected { border-color:#398267; box-shadow:0 0 0 2px #3982671a; }
.map-node.context { border-style:dashed; background:#f5f8f6; }
.map-node.external { background:#fafcfb; border-style:dashed; border-color:#bdcdc6; color:#7c8f84; height:105px; margin-top:12px; box-shadow:none; }
.node-caption { display:flex; justify-content:space-between; align-items:center; width:100%; gap:8px; color:#7f988a !important; font-size:12px; }
.node-caption small { color:#9caaa2; font-size:9px; }
.node-name { display:block; font-size:17px; font-weight:600; margin-top:8px; white-space:nowrap; max-width:100%; overflow:hidden; text-overflow:ellipsis; }
.node-quantity { display:flex; align-items:baseline; gap:5px; font-size:30px; line-height:1.3; color:#2e654f !important; font-weight:650; font-variant-numeric:tabular-nums; margin-top:4px; }
.node-quantity > small { font-size:11px; font-weight:400; color:#839b8c; }
.node-plans { display:flex; flex-direction:column; gap:3px; margin-left:auto; font-size:10px; color:#7f9686 !important; font-weight:400; }
.node-plans small { font-size:10px; }
.distribution-track { display:block; height:3px; width:100%; margin-top:auto; border-radius:3px; background:#edf3ef; overflow:hidden; }
.distribution-track > span { display:block; height:100%; background:#85b19a; }
.external-note { font-size:11px; margin-top:12px; color:#9baa9f !important; }
.map-context { min-height:35px; display:flex; align-items:center; flex-wrap:wrap; gap:5px 16px; padding:9px 3px; font-size:11px; color:#8a9792; }
.map-context strong { font-size:12px; color:#4a715c; }
.map-context button { margin-left:auto; min-width:0; border:0; background:transparent; color:#397d65; padding:3px 0; font-size:11px; }
.mobile-map-tip { display:none; }
.map-transfer-section { border-top:1px solid #e5ece8; padding-top:16px; }
.transfer-heading { display:flex; justify-content:space-between; align-items:baseline; flex-wrap:wrap; gap:8px; margin-bottom:12px; }
.transfer-heading h4 { margin:0; color:#496456; font-size:14px; }
.transfer-heading h4 span { color:#8b9b91 !important; font-weight:400; font-size:12px; margin-left:8px; }
.transfer-heading > small { color:#94a197; font-size:10px; }
.map-transfer-list { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }
.map-transfer { display:block; min-width:0; color:#506b5b; text-decoration:none; background:#f8faf8; border:1px solid #e0e9e2; border-radius:7px; padding:13px 14px; }
.map-transfer:hover { border-color:#8bb39a; background:#f0f7f1; }
.transfer-direction { display:flex; align-items:center; justify-content:space-between; gap:8px; font-size:10px; color:#8a9d8d !important; }
.transfer-direction strong { font-size:16px; color:#427258; font-variant-numeric:tabular-nums; }
.transfer-route { display:flex; align-items:center; flex-wrap:wrap; gap:5px; font-size:12px; font-weight:500; margin-top:7px; line-height:1.8; }
.transfer-route span { color:#99ab9d !important; }
.transfer-meta { display:flex; flex-wrap:wrap; align-items:center; gap:4px 10px; margin-top:9px; }
.transfer-meta small { font-size:9px; color:#95a599; }
.transfer-meta > span { margin-left:auto; font-size:10px; color:#628c6c !important; }
.no-plans,.map-empty { font-size:13px; color:#8a9990; padding:20px 0; }
@media(max-width:1100px) {
  .map-product { flex-wrap:wrap; }
  .map-total { margin-left:auto; }
  .map-transfer-list { grid-template-columns:1fr; }
}
@media(max-width:760px) {
  .map-product { gap:8px; padding-bottom:8px; }
  .product-identity { display:none; }
  .map-total { display:flex; justify-content:space-between; align-items:center; width:100%; }
  .map-total > strong { font-size:24px; }
  .map-plans-summary { gap:7px 16px; padding:8px 0 12px; }
  .map-plans-summary > small { width:100%; margin:0; }
  .map-stage-heading { line-height:1.8; }
  .map-viewport,.map-stage-heading .desktop-map-legend { display:none; }
  .mobile-place-list { display:grid; gap:8px; }
  .mobile-place-list > button { display:flex; align-items:center; justify-content:space-between; gap:12px; min-width:0; padding:12px; border:1px solid #e1eae4; border-radius:7px; background:#f8fbf9; text-align:left; color:#3c6250; }
  .mobile-place-list > button.selected { border-color:#589877; background:#edf6ef; }
  .mobile-place-list > button > span:last-child { text-align:right; flex-shrink:0; }
  .mobile-place-list strong { display:block; font-size:13px; font-weight:600; }
  .mobile-place-list small { display:block; color:#83998a; font-size:11px; margin-top:5px; }
  .mobile-place-list strong small { display:inline; font-size:11px; font-weight:400; }
  .mobile-place-list > button > span:last-child > strong { font-size:22px; color:#376f51; font-variant-numeric:tabular-nums; }
  .map-context { line-height:1.7; }
  .desktop-map-tip { display:none; }
  .mobile-map-tip { display:inline; }
}
</style>
