<script setup lang="ts">
import { ref } from "vue";
import { NButton, NModal } from "naive-ui";
import type { StockAccount } from "../api/accounts";
import type { Sku } from "../api/warehouse";
import AccountRoute from "./AccountRoute.vue";
import AccountLabel from "./AccountLabel.vue";
import { warehouse, type StockTransfer } from "../api/warehouse";
import { today } from "../presentation/warehouse";
const props = defineProps<{
  item: StockTransfer;
  trusted: boolean;
  locations?: StockAccount[];
  skus?: Sku[];
  disabled?: boolean;
}>();
const emit = defineEmits<{ changed: [] }>();
const show = ref(false),
  busy = ref(false),
  error = ref(""),
  date = ref(today());
async function save() {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    await warehouse.action(`/stock-transfers/${props.item.code}/completion`, {
      effective_date: date.value,
    });
    show.value = false;
    emit("changed");
  } catch (e) {
    error.value = (e as Error).message + "。请刷新查看当前记录后再操作。";
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <NButton
    :disabled="disabled || busy"
    @click="
      date = today();
      error = '';
      show = true;
    "
    >{{ trusted ? "确认完成" : "报告已完成" }}</NButton
  >
  <NModal
    v-model:show="show"
    preset="card"
    :title="trusted ? '确认完成' : '报告整笔转移已完成'"
    class="dialog"
    :mask-closable="!busy"
    :closable="!busy"
    :close-on-esc="!busy"
  >
    <AccountRoute
      :accounts="locations || []"
      :source-id="item.source_account_code"
      :destination-id="item.destination_account_code"
      :source-name="item.source_account_name"
      :destination-name="item.destination_account_name"
    />
    <h3>完成数量</h3>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>货物</th>
            <th>数量</th>
            <th>库存变化</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="l in item.lines" :key="l.sku_code">
            <td>
              <AccountLabel
                :name="`${l.sku_code} ${l.sku_name}`"
                :url="skus?.find((s) => s.code === l.sku_code)?.avatar_url"
              />
            </td>
            <td>{{ l.quantity }} {{ l.unit }}</td>
            <td>
              <div v-if="item.source_kind !== 'external'">
                {{ item.source_account_name }} 扣减 {{ l.quantity }}
                {{ l.unit }}
              </div>
              <div v-if="item.destination_kind !== 'external'">
                {{ item.destination_account_name }} 增加 {{ l.quantity }}
                {{ l.unit }}
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <label>完成日期<input v-model="date" type="date" :disabled="busy" /></label>
    <p v-if="!trusted">提交后等待有权限的人核实并确认，转移仍待完成，库存不变。</p>
    <p v-if="error" class="error">{{ error }}</p>
    <div class="actions">
      <NButton :disabled="busy" @click="show = false">关闭</NButton
      ><NButton type="primary" :loading="busy" :disabled="busy" @click="save">{{
        trusted ? "确认完成" : "提交完成报告"
      }}</NButton>
    </div>
  </NModal>
</template>
