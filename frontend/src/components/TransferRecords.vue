<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { NButton } from "naive-ui";
import type { Transfer } from "../api/funds";
import { fundRecord } from "../presentation/records";
import TransferRecordList from "./TransferRecordList.vue";
import type { Account } from "../api/accounts";
import TransferDetail from "./TransferDetail.vue";
const props = defineProps<{
  targetCode?: string; items: Transfer[]; accounts: Account[]; approvals: boolean; trusted: boolean;
  loading?: boolean; hasFilters: boolean; hideCreate?: boolean; error?: string;
}>();
const emit = defineEmits<{ changed: []; notice: [string]; create: []; reset: [] }>();
const detailDialog = ref<InstanceType<typeof TransferDetail> | null>(null);
const detailError = ref("");
const selectedCode = ref("");
const rows = computed(() => props.items.map(fundRecord));
function open(item: Pick<Transfer, "code">) { selectedCode.value = item.code; void detailDialog.value?.open(item); }
onMounted(() => { if (props.targetCode) open({ code: props.targetCode }); });
watch(() => props.targetCode, code => { if (code) open({ code }); }, { flush: "post" });
watch(() => props.items, () => { detailError.value = ""; });
</script>

<template>
  <p v-if="error || detailError" class="error" role="alert">{{ error || detailError }}</p>
  <div v-if="!items.length" class="empty-state">
    <p>{{ loading ? '正在读取流水' : hasFilters ? '没有符合条件的流水' : approvals ? '暂无待审批的资金申请' : '暂无资金流水' }}</p>
    <NButton v-if="hasFilters" @click="emit('reset')">清空筛选</NButton><NButton v-else-if="!approvals && !hideCreate" @click="emit('create')">登记资金</NButton>
  </div>
  <TransferRecordList v-else :rows="rows" value-label="金额" :selected-code="selectedCode" :loading="loading" @open="open" />
  <TransferDetail ref="detailDialog" :accounts="accounts" :approvals="approvals" :trusted="trusted" @changed="emit('changed')" @notice="emit('notice', $event)" @error="detailError = $event" />
</template>
