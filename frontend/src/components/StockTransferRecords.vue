<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { NButton } from "naive-ui";
import { money, statuses as fundStatuses } from "../presentation/funds";
import { type StockAccount, type Account } from "../api/accounts";
import { type Sku } from "../api/warehouse";
import { type StockTransfer } from "../api/warehouse";
import { stockStatuses } from "../presentation/warehouse";
import AccountRoute from "./AccountRoute.vue";
import AccountLabel from "./AccountLabel.vue";
import StockTransferDetail from "./StockTransferDetail.vue";
const props = defineProps<{
  items: StockTransfer[];
  locations: StockAccount[];
  trusted: boolean;
  skus: Sku[];
  accounts: Account[];
  approvals?: boolean;
  loading?: boolean;
  error?: string;
}>();
const emit = defineEmits<{
  changed: [];
}>();
const detailDialog = ref<InstanceType<typeof StockTransferDetail> | null>(null);
const detailError = ref("");
watch(() => props.items, () => {
  detailError.value = "";
});
defineExpose({ busy: computed(() => detailDialog.value?.busy ?? false) });
</script>

<template>
  <p v-if="error || detailError" class="error">{{ error || detailError }}</p>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>日期 / 用途</th>
          <th>来源 → 去向</th>
          <th>货物数量</th>
          <th>货物状态</th>
          <th>关联资金</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="t in items" :key="t.id">
          <td>
            <div>{{ t.effective_date }}</div>
            <div v-if="t.description">{{ t.description }}</div>
            <small v-if="t.tags.length">{{ t.tags.join("，") }}</small>
          </td>
          <td>
            <AccountRoute
              :accounts="locations"
              :source-id="t.source_account_id"
              :destination-id="t.destination_account_id"
              :source-name="t.source_account_name"
              :destination-name="t.destination_account_name"
            />
          </td>
          <td>
            <div v-for="l in t.lines" :key="l.id">
              <AccountLabel
                :name="`${l.sku_code} ${l.sku_name}`"
                :url="skus.find((s) => s.code === l.sku_code)?.avatar_url"
              />
              <strong>{{ l.quantity }} {{ l.unit }}</strong>
            </div>
          </td>
          <td>
            <span class="status-pill" :class="`status-${t.status}`">{{
              stockStatuses[t.status] || t.status
            }}</span>
            <div
              v-if="t.confirmations.some((c) => c.status === 'pending')"
              class="confirmation-state"
            >
              完成申报待审阅
            </div>
          </td>
          <td>
            <div
              v-for="f in t.fund_references"
              :key="f.id"
              class="stock-fund-status"
            >
              <span class="status-pill" :class="`status-${f.status}`">{{
                fundStatuses[f.status] || f.status
              }}</span
              ><span>¥ {{ money(f.amount_minor) }}</span>
            </div>
            <span v-if="!t.fund_references.length">未关联</span>
          </td>
          <td>
            <NButton :disabled="detailDialog?.busy" @click="detailDialog?.open(t.id)">详情 / 处理</NButton>
          </td>
        </tr>
        <tr v-if="!items.length">
          <td colspan="6">{{ loading ? "正在读取货物转移" : "暂无符合条件的货物转移" }}</td>
        </tr>
      </tbody>
    </table>
  </div>
  <StockTransferDetail ref="detailDialog" :locations="locations" :trusted="trusted" :skus="skus" :accounts="accounts"
    @changed="emit('changed')" @error="detailError = $event" />
</template>

<style scoped>
.stock-fund-status { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.confirmation-state { margin-top: 8px; }
</style>
