<script setup lang="ts">
import { h, ref } from "vue";
import { NButton, NInput, NModal, NSelect, type SelectOption } from "naive-ui";
import type { StockAccount, Account } from "../api/accounts";
import type { Sku } from "../api/warehouse";
import { useFundTransferOptions } from "../composables/useFundTransferOptions";
import { warehouse, type StockInput } from "../api/warehouse";
import { today } from "../presentation/warehouse";
import StockAccountSelector from "./StockAccountSelector.vue";
import EndpointSelector from "./EndpointSelector.vue";
import TagInput from "./TagInput.vue";
import AccountRoute from "./AccountRoute.vue";
import AccountLabel from "./AccountLabel.vue";
const props = defineProps<{
  locations: StockAccount[];
  skus: Sku[];
  accounts: Account[];
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
  lines = ref([{ sku_code: "", quantity: "" }]);
const { options: fundOptions, loading: fundLoading, search: searchFunds } = useFundTransferOptions(() => refs.value);
const moneyMode = ref("none"),
  moneySource = ref(""),
  moneyDestination = ref(""),
  amount = ref("");
function open(initial: Partial<StockInput> = props.initial || {}) {
  if (busy.value) return;
  source.value = initial.source_account_id || "";
  destination.value = initial.destination_account_id || "";
  date.value = today();
  description.value = initial.description || "";
  tags.value = [...(initial.tags || [])];
  reference.value = "";
  related.value = initial.related_transfer_id || "";
  refs.value = [];
  lines.value = initial.lines?.map((l) => ({ ...l })) || [
    { sku_code: "", quantity: "" },
  ];
  moneyMode.value = "none";
  moneySource.value = "";
  moneyDestination.value = "";
  amount.value = "";
  error.value = "";
  show.value = true;
  searchFunds("");
}
function renderSkuLabel(option: SelectOption) {
  const sku = props.skus.find((s) => s.code === option.value);
  return h("span", { class: "sku-option" }, [
    h(AccountLabel, {
      name: sku ? `${sku.code} ${sku.name}` : String(option.label || ""),
      url: sku?.avatar_url,
    }),
    h("span", sku ? `（${sku.unit}）` : ""),
  ]);
}
defineExpose({ open });
async function save() {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    const stock: StockInput = {
      source_account_id: source.value,
      destination_account_id: destination.value,
      effective_date: date.value,
      description: description.value,
      tags: tags.value,
      source_reference: reference.value || null,
      related_transfer_id: related.value || null,
      fund_transfer_ids: moneyMode.value === "none" ? refs.value : [],
      lines: lines.value,
    };
    if (moneyMode.value === "none") await warehouse.submit(stock);
    else
      await warehouse.operation({
        stock,
        money: {
          source_account_id: moneySource.value,
          destination_account_id: moneyDestination.value,
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
    >新建货物转移</NButton
  >
  <NModal
    v-model:show="show"
    preset="card"
    title="货物转移"
    class="dialog"
    :mask-closable="!busy"
    :closable="!busy"
    :close-on-esc="!busy"
  >
    <fieldset :disabled="busy">
      <div class="stock-endpoints">
        <StockAccountSelector
          v-model="source"
          :locations="locations"
          label="来源"
          :disabled="busy"
        />
        <StockAccountSelector
          v-model="destination"
          :locations="locations"
          label="去向"
          :disabled="busy"
        />
      </div>
      <AccountRoute
        v-if="source && destination"
        :accounts="locations"
        :source-id="source"
        :destination-id="destination"
      />
      <label>日期<input v-model="date" type="date" /></label>
      <h3>货物明细</h3>
      <div v-for="(line, i) in lines" :key="i" class="stock-line">
        <NSelect
          v-model:value="line.sku_code"
          filterable
          :render-label="renderSkuLabel"
          :disabled="busy"
          :options="
            skus
              .filter((s) => s.active)
              .map((s) => ({ label: `${s.code} ${s.name}（${s.unit}）`, value: s.code }))
          "
          placeholder="选择货物"
        />
        <NInput
          v-model:value="line.quantity"
          :disabled="busy"
          placeholder="正整数数量"
        />
        <NButton
          :disabled="busy || lines.length === 1"
          @click="lines.splice(i, 1)"
          >删除</NButton
        >
      </div>
      <NButton
        :disabled="busy"
        @click="lines.push({ sku_code: '', quantity: '' })"
        >增加货物</NButton
      >
      <details class="stock-extra">
        <summary>补充说明、标签与单据</summary>
        <label
          >说明<NInput
            v-model:value="description"
            type="textarea"
            :disabled="busy"
        /></label>
        <label>标签<TagInput v-model="tags" :disabled="busy" /></label>
        <label
          >原始单据编号<NInput v-model:value="reference" :disabled="busy"
        /></label>
        <label
          >关联转移编号<NInput
            v-model:value="related"
            :disabled="busy"
            placeholder="可留空"
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
    <div class="actions">
      <NButton :disabled="busy" @click="show = false">关闭</NButton
      ><NButton type="primary" :loading="busy" :disabled="busy" @click="save"
        >提交</NButton
      >
    </div>
  </NModal>
</template>
<style scoped>
.sku-option {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.stock-endpoints {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}
.stock-line {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 140px auto;
  gap: 12px;
  margin-bottom: 12px;
  align-items: center;
}
.stock-extra {
  margin-top: 24px;
}
.stock-extra summary {
  cursor: pointer;
  margin-bottom: 16px;
}
@media (max-width: 600px) {
  .stock-endpoints {
    grid-template-columns: 1fr;
    gap: 0;
  }
  .stock-line {
    grid-template-columns: minmax(0, 1fr) 100px auto;
  }
}
</style>
