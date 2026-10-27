<script setup lang="ts">
import { ref, useId } from "vue";
import { NTooltip } from "naive-ui";

defineProps<{ label: string; text: string }>();
const hovered = ref(false), focused = ref(false);
const descriptionId = useId();
</script>

<template>
  <NTooltip trigger="manual" :show="hovered || focused" placement="bottom-start" :style="{ maxWidth: '300px' }">
    <template #trigger>
      <button type="button" class="status-hint" :aria-label="`${label}说明`" :aria-describedby="descriptionId" @mouseenter="hovered = true" @mouseleave="hovered = false" @focus="focused = true" @blur="focused = false">?</button>
    </template>
    <span :id="descriptionId" role="tooltip">{{ text }}</span>
  </NTooltip>
</template>

<style scoped>
.status-hint { display:inline-flex; align-items:center; justify-content:center; width:16px; min-width:16px !important; height:16px; padding:0; border:1px solid #9bada8; border-radius:50%; background:transparent; color:#71877e; font-size:11px; font-family:inherit; line-height:1; cursor:help; }
.status-hint:hover,.status-hint:focus-visible { color:#2c6c54; border-color:#3c8866; outline:2px solid #dcece2; outline-offset:2px; }
</style>
