<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { NButton, NInput, NModal } from "naive-ui";
import { fundsApi, type TransferInput } from "../api/funds";
import { statuses } from "../presentation/funds";
import { type Account } from "../api/accounts";
import { kinds } from "../presentation/accounts";
import TransferRouteEditor from "./TransferRouteEditor.vue";
import TagInput from "./TagInput.vue";

const props = defineProps<{
  show: boolean;
  accounts: Account[];
  opening?: boolean;
  initial?: Partial<TransferInput>;
}>();
const emit = defineEmits<{ close: []; saved: [string] }>();
const fresh = (): TransferInput => ({
  source_account_code: props.opening
    ? props.accounts.find((a) => a.name === "期初")?.code || ""
    : "",
  destination_account_code: props.opening
    ? props.accounts.find((a) => a.kind === "public" && a.active)?.code || ""
    : "",
  amount: "",
  effective_date: new Date().toLocaleDateString("sv-SE"),
  description: props.opening ? "期初资金" : "",
  counterparty: null,
  tags: [],
  ...props.initial,
});
const form = ref<TransferInput>(fresh()),
  error = ref(""),
  busy = ref(false);
const source = computed(() =>
  props.accounts.find((a) => a.code === form.value.source_account_code),
);
const destination = computed(() =>
  props.accounts.find((a) => a.code === form.value.destination_account_code),
);
const ready = computed(
  () =>
    !!source.value &&
    !!destination.value &&
    source.value.code !== destination.value.code &&
    /^\d+(?:\.\d{1,2})?$/.test(form.value.amount) &&
    Number(form.value.amount) > 0,
);
watch(
  () => props.show,
  (value) => {
    if (value) {
      form.value = fresh();
      error.value = "";
    }
  },
);
function close() {
  if (!busy.value) emit("close");
}
async function submit() {
  if (busy.value || !ready.value) return;
  busy.value = true;
  error.value = "";
  try {
    const result = await fundsApi.submit({
      ...form.value,
      tags: [...form.value.tags],
    });
    emit("saved", statuses[result.status] || result.status);
    emit("close");
  } catch (e) {
    error.value =
      (e as Error).message + "。请查看流水记录后再决定是否重新提交。";
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <NModal
    :show="show"
    preset="card"
    :title="opening ? '登记期初资金' : '资金转移'"
    class="transfer-dialog fantasy-dialog"
    :style="{
      width: '560px',
      maxWidth: 'calc(100vw - 32px)',
      maxHeight: 'calc(100dvh - 32px)',
    }"
    :header-style="{
      padding: '16px 24px 12px',
      borderBottom: '1px solid #ccc',
    }"
    :content-style="{
      padding: '14px 24px',
      maxHeight: 'calc(100dvh - 112px)',
      overflowY: 'auto',
    }"
    :closable="!busy"
    :mask-closable="!busy"
    :close-on-esc="!busy"
    @close="close"
    @update:show="
      (value) => {
        if (!value) close();
      }
    "
  >
    <TransferRouteEditor v-model:source="form.source_account_code" v-model:destination="form.destination_account_code" :accounts="accounts" :kinds="kinds" :disabled="busy" />
    <label class="transfer-amount">金额（元）
      <NInput v-model:value="form.amount" :disabled="busy" placeholder="0.00" :input-props="{ inputmode: 'decimal', 'aria-label': '转移金额（元）' }" />
    </label>
    <section class="transfer-details">
      <fieldset :disabled="busy">
        <div class="primary-fields">
          <label class="form-field">业务日期<input v-model="form.effective_date" type="date" /></label>
          <label class="form-field">备注<NInput v-model:value="form.description" type="textarea" :autosize="{ minRows: 1, maxRows: 4 }" :disabled="busy" placeholder="填写说明（选填）" /></label>
        </div>
        <details class="disclosure">
          <summary>补充信息</summary>
          <label class="form-field"
            >往来方<NInput
              :value="form.counterparty || ''"
              :disabled="busy"
              placeholder="姓名或单位"
              @update:value="form.counterparty = $event || null"
          /></label>
          <label class="form-field"
            >标签<TagInput v-model="form.tags" :disabled="busy"
          /></label>
        </details>
      </fieldset>
    </section>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div class="transfer-submit">
      <NButton
        type="primary"
        size="large"
        :loading="busy"
        :disabled="busy || !ready"
        @click="submit"
        >保存转移</NButton
      >
    </div>
  </NModal>

</template>

<style scoped>
.transfer-amount { display:block; max-width:240px; margin:0 auto 12px; text-align:center; color:#66707c; font-size:13px; }
.transfer-amount :deep(.n-input) { margin-top:7px; }
.transfer-amount :deep(.n-input__input-el) { text-align:center; font-size:22px; font-weight:600; height:44px; }
.transfer-details { border-top:1px solid #e2e6ea; padding-top:12px; }
.primary-fields { display:grid; grid-template-columns:160px minmax(0,1fr); gap:12px; align-items:start; }
.form-field { margin:0 0 8px; font-size:13px; }
.form-field input[type="date"] { width:100%; height:36px; border:1px solid #ccc; padding:6px 10px; margin-top:7px; }
.transfer-submit { display:flex; justify-content:flex-end; border-top:1px solid #e2e6ea; padding-top:12px; }
.transfer-submit .n-button { min-width:120px; }
@media (max-width:480px) { .primary-fields { grid-template-columns:1fr; gap:0; } }
</style>
