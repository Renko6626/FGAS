<script setup lang="ts">
import type { HandbookHeading } from '../lib/handbookMarkdown';
defineProps<{ headings: HandbookHeading[]; active: string }>();
const emit = defineEmits<{ select: [string] }>();
</script>

<template>
  <ul class="handbook-contents">
    <li v-for="heading in headings" :key="heading.id">
      <button type="button" :class="{ active: active === heading.id }" :aria-current="active === heading.id ? 'location' : undefined"
        @click="emit('select', heading.id)">{{ heading.title }}</button>
      <HandbookContents v-if="heading.children.length" :headings="heading.children" :active="active" @select="emit('select', $event)" />
    </li>
  </ul>
</template>

<style scoped>
.handbook-contents { list-style:none; margin:0; padding:0; }
.handbook-contents .handbook-contents { margin-left:12px; padding-left:8px; border-left:1px solid var(--line); }
.handbook-contents button { display:block; width:100%; padding:6px 8px; border:0; border-radius:4px; background:none; color:#77859a; text-align:left; font:inherit; font-size:12px; line-height:1.5; overflow-wrap:anywhere; cursor:pointer; }
.handbook-contents button:hover { color:#344c69; background:#f1f4f7; }
.handbook-contents button.active { color:#244f77; background:#edf3f8; font-weight:600; }
</style>
