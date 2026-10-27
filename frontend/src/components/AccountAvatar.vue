<script setup lang="ts">
import { ref, watch, computed } from "vue";
const props = defineProps<{ name: string; url?: string | null }>();
const failed = ref(false);
watch(
  () => props.url,
  () => (failed.value = false),
);
const initial = computed(() => Array.from(props.name.trim()).find(character => !/[\p{P}\p{S}\s]/u.test(character)) || "?");
const colors = computed(() => {
  let hash = 0;
  for (const character of props.name.trim()) {
    hash = (Math.imul(hash, 31) + character.codePointAt(0)!) >>> 0;
  }
  const hue = (Math.imul(hash, 137) >>> 0) % 360;
  return {
    backgroundColor: `hsl(${hue}, 52%, 90%)`,
    color: `hsl(${hue}, 58%, 25%)`,
  };
});
</script>
<template>
  <span class="account-avatar" :style="colors"
    ><img
      v-if="url && !failed"
      :src="url"
      :alt="name"
      @error="failed = true"
    /><span v-else :style="{ color: colors.color }">{{ initial }}</span></span
  >
</template>
<style scoped>
.account-avatar {
  display: inline-flex;
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  vertical-align: middle;
  background: #eee;
  color: #333;
  font-weight: 600;
  overflow: hidden;
  margin-right: 8px;
}
.account-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>
