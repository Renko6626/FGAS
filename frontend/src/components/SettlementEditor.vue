<script setup lang="ts">
import { computed, h, ref, watch } from "vue";
import { NButton, NInput, NModal, NSelect, type SelectOption } from "naive-ui";
import { money } from "../presentation/funds";
import { type Account } from "../api/accounts";
import {
  settlementsApi,
  type SettlementItem,
  type SettlementPayment,
} from "../api/settlements";
import { today } from "../presentation/warehouse";
import AccountLabel from "./AccountLabel.vue";
import AccountRoute from "./AccountRoute.vue";
import TagInput from "./TagInput.vue";
const props = defineProps<{
  show: boolean;
  direction: "expense" | "receipt";
  account: Account;
  accounts: Account[];
  items: SettlementItem[];
  payments: SettlementPayment[];
}>();
const emit = defineEmits<{ close: []; saved: [] }>();
const mode = ref("new"),
  publicId = ref(""),
  paymentId = ref(""),
  amount = ref(""),
  date = ref(today()),
  description = ref(""),
  tags = ref<string[]>([]),
  allocations = ref<Record<string, string>>({}),
  busy = ref(false),
  error = ref("");
const items = computed(() =>
  props.items.filter(
    (i) => i.transfer.status === "posted" && i.outstanding_minor > 0,
  ),
);
const paymentOptions = computed(() =>
  props.payments
    .filter(
      (p) =>
        p.transfer.status === "posted" &&
        p.unmatched_minor > 0 &&
        (props.direction === "expense"
          ? p.transfer.destination_account_code === props.account.code
          : p.transfer.source_account_code === props.account.code),
    )
    .map((p) => ({
      label: `${p.transfer.code}，${p.transfer.effective_date}，${p.transfer.source_account_name} → ${p.transfer.destination_account_name}，¥${money(p.transfer.amount_minor)}，未匹配 ¥${money(p.unmatched_minor)}`,
      value: p.transfer.code,
    })),
);
function renderAccountLabel(option: SelectOption) {
  const account = props.accounts.find((a) => a.code === option.value);
  return h(AccountLabel, {
    name: account?.name || String(option.label ?? option.value),
    code: account?.code,
    url: account?.avatar_url,
  });
}
function renderPaymentLabel(option: SelectOption) {
  const payment = props.payments.find((p) => p.transfer.code === option.value);
  if (!payment) return String(option.label ?? option.value);
  const transfer = payment.transfer;
  return h("span", { class: "payment-option" }, [
    h("span", `${transfer.code}，${transfer.effective_date}，`),
    h(AccountRoute, {
      accounts: props.accounts,
      sourceId: transfer.source_account_code,
      destinationId: transfer.destination_account_code,
      sourceName: transfer.source_account_name,
      destinationName: transfer.destination_account_name,
    }),
    h(
      "span",
      `¥${money(transfer.amount_minor)}，可匹配 ¥${money(payment.unmatched_minor)}`,
    ),
  ]);
}
const selectedPayment = computed(() =>
  props.payments.find((payment) => payment.transfer.code === paymentId.value),
);
watch(
  () => props.show,
  (show) => {
    if (show) {
      mode.value = "new";
      publicId.value = "";
      paymentId.value = "";
      amount.value = "";
      date.value = today();
      description.value = "";
      tags.value = [];
      allocations.value = {};
      error.value = "";
    }
  },
);
async function save() {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    const selected = Object.entries(allocations.value)
      .filter(([, v]) => v.trim())
      .map(([item_transfer_code, amount]) => ({ item_transfer_code, amount }));
    if (mode.value === "existing")
      await settlementsApi.add(paymentId.value, selected);
    else
      await settlementsApi.create(
        {
          source_account_code:
            props.direction === "expense" ? publicId.value : props.account.code,
          destination_account_code:
            props.direction === "expense" ? props.account.code : publicId.value,
          amount: amount.value,
          effective_date: date.value,
          description: description.value,
          tags: tags.value,
          counterparty: null,
        },
        selected,
      );
    emit("saved");
    emit("close");
  } catch (e) {
    error.value = (e as Error).message + "。请查看结算记录后再操作。";
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <NModal
    :show="show"
    preset="card"
    :title="direction === 'expense' ? '报销支出' : '交回代收款'"
    class="dialog"
    :closable="!busy"
    :mask-closable="!busy"
    :close-on-esc="!busy"
    @close="emit('close')"
  >
    <AccountLabel :name="account.name" :url="account.avatar_url" />
    <section class="editor-section">
      <h3>付款资料</h3>
      <NSelect
        v-model:value="mode"
        :disabled="busy"
        :options="[
          { label: '新建结算转移', value: 'new' },
          { label: '追加已有付款的匹配', value: 'existing' },
        ]"
      />
      <template v-if="mode === 'new'">
        <label
          >公账账户<NSelect
            v-model:value="publicId"
            :disabled="busy"
            :options="
              accounts
                .filter((a) => a.kind === 'public' && a.active)
                .map((a) => ({ label: `${a.name}（${a.code}）`, value: a.code }))
            "
            :render-label="renderAccountLabel"
        /></label>
        <div v-if="publicId" class="payment-route">
          <AccountRoute
            :accounts="accounts"
            :source-id="direction === 'expense' ? publicId : account.code"
            :destination-id="direction === 'expense' ? account.code : publicId"
          />
        </div>
        <div class="pair">
          <label
            >实际付款或交回金额（元）<NInput
              v-model:value="amount"
              :disabled="busy"
              placeholder="0.00" /></label
          ><label
            >日期<input v-model="date" type="date" required :disabled="busy"
          /></label>
        </div>
        <details class="disclosure">
          <summary>说明与标签（选填）</summary>
          <label
            >说明<NInput v-model:value="description" :disabled="busy" /></label
          ><label>标签<TagInput v-model="tags" :disabled="busy" /></label>
        </details>
      </template>
      <template v-else>
        <label
          >已有付款<NSelect
            v-model:value="paymentId"
            :disabled="busy"
            :options="paymentOptions"
            :render-label="renderPaymentLabel"
            placeholder="选择已有结算转移"
        /></label>
        <div v-if="selectedPayment" class="payment-route">
          <p>{{ selectedPayment.transfer.code }}</p>
          <AccountRoute
            :accounts="accounts"
            :source-id="selectedPayment.transfer.source_account_code"
            :destination-id="selectedPayment.transfer.destination_account_code"
            :source-name="selectedPayment.transfer.source_account_name"
            :destination-name="
              selectedPayment.transfer.destination_account_name
            "
          />
          <p>
            实际金额 ¥{{ money(selectedPayment.transfer.amount_minor) }}，可匹配
            ¥{{ money(selectedPayment.unmatched_minor) }}
          </p>
        </div>
      </template>
    </section>
    <section class="editor-section">
      <h3>逐笔匹配</h3>
      <div v-if="items.length" class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>日期 / 原收支</th>
              <th class="numeric">未结</th>
              <th>本次匹配（元）</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.transfer.code">
              <td>
                <p class="item-date">
                  {{ item.transfer.effective_date }}（{{ item.transfer.code }}）
                </p>
                <AccountRoute
                  :accounts="accounts"
                  :source-id="item.transfer.source_account_code"
                  :destination-id="item.transfer.destination_account_code"
                  :source-name="item.transfer.source_account_name"
                  :destination-name="item.transfer.destination_account_name"
                />
                <div v-if="item.transfer.description" class="item-description">
                  {{ item.transfer.description }}
                </div>
                <span
                  v-for="tag in item.transfer.tags"
                  :key="tag"
                  class="tag"
                  >{{ tag }}</span
                >
              </td>
              <td class="numeric">¥{{ money(item.outstanding_minor) }}</td>
              <td class="allocation-input">
                <NInput
                  :value="allocations[item.transfer.code] || ''"
                  :disabled="busy"
                  placeholder="留空不匹配"
                  :input-props="{
                    'aria-label': `${item.transfer.code} ${item.transfer.effective_date} ${item.transfer.description || item.transfer.source_account_name + ' → ' + item.transfer.destination_account_name} 本次匹配金额`,
                  }"
                  @update:value="allocations[item.transfer.code] = $event"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else>暂无未结条目</p>
      <p class="matching-note">
        匹配金额不超过实际付款金额，未匹配部分保留在结算记录中。
      </p>
    </section>
    <p v-if="error" class="error">{{ error }}</p>
    <div class="actions">
      <NButton :disabled="busy" @click="emit('close')">取消</NButton
      ><NButton :loading="busy" @click="save">保存结算</NButton>
    </div>
  </NModal>
</template>

<style scoped>
.payment-option {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.editor-section {
  margin-top: 24px;
}
.editor-section h3 {
  margin-bottom: 12px;
}
.payment-route {
  margin-top: 16px;
}
.payment-route p {
  margin: 12px 0 0;
}
.item-date {
  margin: 0 0 8px;
}
.item-description {
  margin-top: 8px;
}
.allocation-input {
  min-width: 140px;
  width: 170px;
}
.matching-note {
  margin-top: 16px;
  margin-bottom: 0;
}
</style>
