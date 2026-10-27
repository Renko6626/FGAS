<script setup lang="ts">
import { computed, ref } from "vue";
import { NButton, NInput, NModal, NSelect } from "naive-ui";
import type { StockAccount, Account } from "../api/accounts";
import type { Sku } from "../api/warehouse";
import { useFundTransferOptions } from "../composables/useFundTransferOptions";
import { warehouse, type StockInput } from "../api/warehouse";
import { today } from "../presentation/warehouse";
import TransferRouteEditor from "./TransferRouteEditor.vue";
import AccountAvatar from "./AccountAvatar.vue";
import { stockKinds } from "../presentation/accounts";
import EndpointSelector from "./EndpointSelector.vue";
import TagInput from "./TagInput.vue";
import AccountRoute from "./AccountRoute.vue";

const props = defineProps<{
  locations: StockAccount[];
  skus: Sku[];
  accounts: Account[];
  trusted: boolean;
  hideTrigger?: boolean;
  initial?: Partial<StockInput>;
}>();
const emit = defineEmits<{ saved: [] }>();
const show = ref(false),
  busy = ref(false),
  error = ref(""),
  source = ref(""),
  destination = ref(""),
  date = ref(today()),
  description = ref(""),
  tags = ref<string[]>([]),
  reference = ref(""),
  related = ref(""),
  refs = ref<string[]>([]),
  lines = ref<{ sku_code: string; quantity: string }[]>([]);
const skuPicker = ref(false), skuSearch = ref("");
const availableSkus = computed(() => { const q = skuSearch.value.trim().toLocaleLowerCase(); return props.skus.filter(s => s.active && (!q || [s.name, s.code, ...s.tags].some(v => v.toLocaleLowerCase().includes(q)))); });
function addSku(code: string) { lines.value.push({ sku_code: code, quantity: "" }); skuPicker.value = false; }
function skuFor(code: string) { return props.skus.find(s => s.code === code); }
const { options: fundOptions, loading: fundLoading, search: searchFunds } = useFundTransferOptions(() => refs.value);
const moneyMode = ref("none"),
  moneySource = ref(""),
  moneyDestination = ref(""),
  amount = ref("");
function open(initial: Partial<StockInput> = props.initial || {}) {
  if (busy.value) return;
  source.value = initial.source_account_code || "";
  destination.value = initial.destination_account_code || "";
  date.value = today();
  description.value = initial.description || "";
  tags.value = [...(initial.tags || [])];
  reference.value = "";
  related.value = initial.related_transfer_code || "";
  refs.value = [];
  lines.value = initial.lines?.map((l) => ({ ...l })) || [];
  skuSearch.value = "";
  moneyMode.value = "none";
  moneySource.value = "";
  moneyDestination.value = "";
  amount.value = "";
  error.value = "";
  show.value = true;
  searchFunds("");
}
defineExpose({ open });
async function save() {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    const stock: StockInput = {
      source_account_code: source.value,
      destination_account_code: destination.value,
      effective_date: date.value,
      description: description.value,
      tags: tags.value,
      source_reference: reference.value || null,
      related_transfer_code: related.value || null,
      fund_transfer_codes: moneyMode.value === "none" ? refs.value : [],
      lines: lines.value,
    };
    if (moneyMode.value === "none") await warehouse.submit(stock);
    else
      await warehouse.operation({
        stock,
        money: {
          source_account_code: moneySource.value,
          destination_account_code: moneyDestination.value,
          amount: amount.value,
          effective_date: date.value,
          description: description.value,
          tags: tags.value,
          counterparty: null,
        },
      });
    show.value = false;
    emit("saved");
  } catch (e) {
    error.value = (e as Error).message + "。结果不确定时，请先查看记录。";
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <NButton v-if="!hideTrigger" type="primary" :disabled="busy" @click="open()"
    >{{ trusted ? "登记转移" : "申请转移" }}</NButton
  >
  <NModal
    v-model:show="show"
    preset="card"
    :title="trusted ? '登记转移' : '申请转移'"
    class="dialog stock-dialog"
    :mask-closable="!busy"
    :closable="!busy"
    :close-on-esc="!busy"
  >
    <fieldset :disabled="busy">
      <TransferRouteEditor v-model:source="source" v-model:destination="destination" :accounts="locations" :kinds="stockKinds" :disabled="busy" />
      <div class="stock-items">
        <div class="items-heading"><h3>货物明细</h3><small>填写每种货物的数量</small></div>
        <div v-for="(line, i) in lines" :key="i" class="stock-line">
          <AccountAvatar :name="skuFor(line.sku_code)?.name || line.sku_code" :url="skuFor(line.sku_code)?.avatar_url" />
          <div class="stock-name"><strong>{{ skuFor(line.sku_code)?.name || line.sku_code }}</strong><small>{{ line.sku_code }}</small></div>
          <label class="quantity">数量<NInput v-model:value="line.quantity" :disabled="busy" placeholder="数量" :input-props="{ inputmode: 'numeric', 'aria-label': `${skuFor(line.sku_code)?.name || line.sku_code} 数量` }" /></label>
          <span class="unit">{{ skuFor(line.sku_code)?.unit }}</span>
          <button type="button" class="remove-line" :disabled="busy" :aria-label="`删除${skuFor(line.sku_code)?.name || line.sku_code}`" @click="lines.splice(i, 1)">删除</button>
        </div>
        <button type="button" class="add-line" :disabled="busy" @click="skuSearch = ''; skuPicker = true"><span>＋</span> 添加货物</button>
      </div>
      <div class="primary-fields">
        <label>业务日期<input v-model="date" type="date" /></label>
        <label>备注<NInput v-model:value="description" type="textarea" :autosize="{ minRows: 1, maxRows: 4 }" :disabled="busy" placeholder="填写说明（选填）" /></label>
      </div>
      <details class="stock-extra">
        <summary>标签与单据</summary>
        <label>标签<TagInput v-model="tags" :disabled="busy" /></label>
        <label
          >原始单据编号<NInput v-model:value="reference" :disabled="busy"
        /></label>
        <label
          >关联的原货物单编号<NInput
            v-model:value="related"
            :disabled="busy"
            placeholder="填写 ST 编号，选填"
        /></label>
      </details>
      <details class="stock-extra">
        <summary>
          资金关联{{
            moneyMode === "new"
              ? "（同时新建）"
              : refs.length
                ? `（${refs.length} 条）`
                : ""
          }}
        </summary>
        <label
          >关联方式<NSelect
            v-model:value="moneyMode"
            :disabled="busy"
            :options="[
              { label: '已有记录或不关联', value: 'none' },
              { label: '同时新建资金转移', value: 'new' },
            ]"
        /></label>
        <NSelect
          v-if="moneyMode === 'none'"
          v-model:value="refs"
          :disabled="busy"
          multiple
          clearable
          filterable
          remote
          :loading="fundLoading"
          :options="fundOptions"
          placeholder="搜索已有资金记录"
          @search="searchFunds"
        />
        <template v-else>
          <p>资金按原规则审批过账，货物须另外确认完成。</p>
          <div class="stock-endpoints">
            <EndpointSelector
              v-model="moneySource"
              :accounts="accounts"
              label="资金来源"
              :disabled="busy"
            />
            <EndpointSelector
              v-model="moneyDestination"
              :accounts="accounts"
              label="资金去向"
              :disabled="busy"
            />
          </div>
          <AccountRoute
            v-if="moneySource && moneyDestination"
            :accounts="accounts"
            :source-id="moneySource"
            :destination-id="moneyDestination"
          />
          <label
            >金额（元）<NInput v-model:value="amount" :disabled="busy"
          /></label>
        </template>
      </details>
    </fieldset>
    <p v-if="error" class="error">{{ error }}</p>
    <div class="actions stock-actions">
      <NButton :disabled="busy" @click="show = false">关闭</NButton
      ><NButton type="primary" :loading="busy" :disabled="busy" @click="save"
        >{{ trusted ? "登记转移" : "申请转移" }}</NButton
      >
    </div>
  </NModal>
  <NModal v-model:show="skuPicker" preset="card" title="选择货物" class="sku-picker" :style="{ width: '720px', maxWidth: 'calc(100vw - 32px)' }">
    <NInput v-model:value="skuSearch" clearable placeholder="搜索货物名称、SKU 或标签" :input-props="{ 'aria-label': '搜索货物' }" />
    <div v-if="availableSkus.length" class="sku-grid">
      <button v-for="sku in availableSkus" :key="sku.code" type="button" @click="addSku(sku.code)"><AccountAvatar :name="sku.name" :url="sku.avatar_url" /><strong>{{ sku.name }}</strong><small>{{ sku.code }}　{{ sku.unit }}</small></button>
    </div>
    <p v-else class="sku-empty">没有符合条件的货物。</p>
  </NModal>
</template>
<style scoped>
.stock-dialog { width:min(600px, calc(100vw - 32px)) !important; }
.primary-fields { display:grid; grid-template-columns:160px minmax(0,1fr); gap:12px; align-items:start; }
.primary-fields label { margin:4px 0 0; font-size:13px; }
.primary-fields input[type="date"] { width:100%; height:34px; margin-top:8px; }
.stock-items { margin:0 0 8px; }
.items-heading { display:flex; align-items:baseline; justify-content:space-between; margin-bottom:10px; }
.items-heading h3 { margin:0; font-size:15px; }
.stock-line { display:flex; align-items:center; gap:12px; background:#f5f7f9; border-radius:7px; padding:8px 12px; margin-bottom:6px; }
.stock-line :deep(.account-avatar) { width:40px; height:40px; margin:0; border-radius:7px; }
.stock-name { flex:1; min-width:0; }
.stock-name strong, .stock-name small { display:block; overflow-wrap:anywhere; }
.quantity { width:96px; margin:0; color:#66707c; font-size:12px; }
.quantity :deep(.n-input) { margin:3px 0 0; }
.unit { color:#66707c; font-size:13px; padding-top:18px; }
.remove-line { border:0; background:none; color:#9b4d47; padding:8px; }
.add-line { width:100%; border:1px dashed #a7b7c4; border-radius:7px; background:#fff; padding:7px; color:#345c78; }
.add-line span { font-size:19px; vertical-align:middle; }
.stock-endpoints { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:20px; }
.stock-extra { margin-top:12px; }

.stock-actions { margin-top:14px; }
.stock-extra summary { cursor:pointer; margin-bottom:8px; }
.sku-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; max-height:50vh; overflow:auto; margin-top:14px; }
.sku-grid button { display:flex; flex-direction:column; align-items:center; gap:6px; min-width:0; padding:16px 8px; border:1px solid transparent; border-radius:7px; background:#f5f7f9; }
.sku-grid button:hover { border-color:#7597b0; background:#eaf1f6; }
.sku-grid button :deep(.account-avatar) { width:48px; height:48px; margin:0; border-radius:8px; }
.sku-grid strong, .sku-grid small { text-align:center; overflow-wrap:anywhere; }
.sku-empty { padding:24px 0; color:#66707c; }
@media (max-width:480px) { .primary-fields { grid-template-columns:1fr; gap:0; } }
@media (max-width:600px) { .stock-line { gap:6px; padding:8px; } .quantity { width:70px; } .stock-endpoints { grid-template-columns:1fr; gap:0; } .sku-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }
</style>
