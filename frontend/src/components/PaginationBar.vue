<script setup lang="ts">
import { computed } from "vue";
import { NButton, NSelect } from "naive-ui";

const props = defineProps<{ page: number; limit: number; total: number }>();
const emit = defineEmits<{ "update:page": [number]; "update:limit": [number] }>();
const pages = computed(() => Math.max(1, Math.ceil(props.total / props.limit)));
const sizes = [20, 50, 100].map((value) => ({ label: `${value} 条/页`, value }));
</script>

<template>
  <div class="pagination-bar">
    <span>共 {{ total }} 条</span>
    <div class="pagination-actions">
      <NSelect
        :value="limit"
        :options="sizes"
        size="small"
        class="pagination-size"
        @update:value="emit('update:limit', $event)"
      />
      <NButton
        size="small"
        :disabled="page <= 1"
        @click="emit('update:page', page - 1)"
        >上一页</NButton
      >
      <span class="pagination-position">{{ page }} / {{ pages }}</span>
      <NButton
        size="small"
        :disabled="page >= pages"
        @click="emit('update:page', page + 1)"
        >下一页</NButton
      >
    </div>
  </div>
</template>

<style scoped>
.pagination-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin-top: 16px;
  color: #666;
  font-size: 12px;
}
.pagination-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.pagination-size {
  width: 110px;
}
.pagination-position {
  min-width: 56px;
  text-align: center;
  font-variant-numeric: tabular-nums;
}
</style>
