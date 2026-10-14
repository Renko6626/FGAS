<script setup lang="ts">
import AccountAvatar from "./AccountAvatar.vue";
defineProps<{ name: string; url?: string | null }>();
</script>

<template>
  <span class="account-label"
    ><AccountAvatar :name="name" :url="url" /><span
      class="account-label-name"
      >{{ name }}</span
    ></span
  >
</template>

<style scoped>
.account-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  vertical-align: middle;
}
.account-label :deep(.account-avatar) {
  width: 28px;
  height: 28px;
  font-size: 14px;
  margin: 0;
}
.account-label-name {
  overflow-wrap: anywhere;
}
</style>
