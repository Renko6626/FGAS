<script setup lang="ts">
import {ref,watch,computed} from 'vue'
const props=defineProps<{name:string;url?:string|null}>()
const failed=ref(false)
watch(()=>props.url,()=>failed.value=false)
const initial=computed(()=>Array.from(props.name.trim())[0]||'?')
</script>
<template><span class="account-avatar"><img v-if="url&&!failed" :src="url" :alt="name" @error="failed=true"><span v-else>{{initial}}</span></span></template>
<style scoped>.account-avatar{display:inline-flex;width:36px;height:36px;flex-shrink:0;align-items:center;justify-content:center;vertical-align:middle;border-radius:50%;background:#e9eef3;color:#36546d;font-weight:600;overflow:hidden;margin-right:8px}.account-avatar img{width:100%;height:100%;object-fit:cover}</style>
