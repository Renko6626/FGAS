<script setup lang="ts">
import { computed, h, ref } from "vue";
import { NSelect, NCheckbox, type SelectOption } from "naive-ui";
import AccountLabel from "./AccountLabel.vue";
import { kinds, type AccountBase } from "../api/funds";
const props = defineProps<{
  accounts: AccountBase[];
  modelValue: string;
  label: string;
  disabled?: boolean;
}>();
const emit = defineEmits<{ "update:modelValue": [string] }>();
const showEnded = ref(false),
  category = ref<string | null>(null),
  tag = ref<string | null>(null);
const tags = computed(() =>
  [...new Set(props.accounts.flatMap((a) => a.tags))].map((value) => ({
    label: value,
    value,
  })),
);
const options = computed(() =>
  props.accounts
    .filter(
      (a) =>
        a.id === props.modelValue ||
        (a.active &&
          (showEnded.value || a.stocktake?.status !== "ended") &&
          (!category.value || a.kind === category.value) &&
          (!tag.value || a.tags.includes(tag.value))),
    )
    .map((a) => ({ label: a.name, value: a.id })),
);
function renderLabel(option: SelectOption) {
  const account = props.accounts.find((a) => a.id === option.value);
  return h(AccountLabel, {
    name: account?.name || String(option.label || ""),
    url: account?.avatar_url,
  });
}
</script>
<template>
  <div class="endpoint">
    <label>{{ label }}</label>
    <NSelect
      :disabled="disabled"
      :value="modelValue || null"
      :options="options"
      :render-label="renderLabel"
      filterable
      placeholder="选择账户"
      @update:value="emit('update:modelValue', $event || '')"
    />
    <details class="endpoint-filters">
      <summary>筛选账户</summary>
      <div class="filters">
        <NSelect
          v-model:value="category"
          :disabled="disabled"
          clearable
          placeholder="所有类型"
          :options="
            Object.entries(kinds).map(([value, label]) => ({ value, label }))
          "
        /><NSelect
          v-model:value="tag"
          :disabled="disabled"
          clearable
          placeholder="所有标签"
          :options="tags"
        />
      </div>
      <NCheckbox v-model:checked="showEnded" :disabled="disabled"
        >显示已结束盘点账户</NCheckbox
      >
    </details>
  </div>
</template>
<style scoped>
.endpoint-filters {
  margin: 8px 0 0;
  color: #666;
  font-size: 12px;
}
.endpoint-filters summary {
  cursor: pointer;
  display: inline-block;
}
.endpoint-filters summary::before {
  content: "＋";
  margin-right: 4px;
}
.endpoint-filters[open] summary::before {
  content: "−";
}
.endpoint-filters .filters {
  margin: 12px 0;
}
</style>
