<script setup lang="ts">
import { ref } from "vue";
import { NButton, NInput, NModal, NCheckbox } from "naive-ui";
import { warehouse } from "../api/warehouse";
import type { Sku } from "../api/warehouse";
import AccountLabel from "../components/AccountLabel.vue";
const props = defineProps<{ items: Sku[]; editable: boolean }>(),
  emit = defineEmits<{ changed: [] }>();
const show = ref(false),
  busy = ref(false),
  error = ref(""),
  id = ref(""),
  name = ref(""),
  specification = ref(""),
  unit = ref(""),
  avatar = ref(""),
  active = ref(true);
function edit(s?: Sku) {
  id.value = s?.id || "";
  name.value = s?.name || "";
  specification.value = s?.specification || "";
  unit.value = s?.unit || "";
  avatar.value = s?.avatar_url || "";
  active.value = s?.active ?? true;
  error.value = "";
  show.value = true;
}
async function save() {
  busy.value = true;
  try {
    const body = {
      name: name.value, specification: specification.value, unit: unit.value,
      avatar_url: avatar.value.trim() || null, active: active.value,
    };
    if (id.value) await warehouse.updateSku(id.value, body);
    else await warehouse.createSku(body);
    show.value = false;
    emit("changed");
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <div class="toolbar">
    <h2>SKU 目录</h2>
    <NButton v-if="editable" @click="edit()">新建 SKU</NButton>
  </div>
  <p>数量按整数记录，单位用于说明计数方式。</p>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>名称</th>
          <th>规格</th>
          <th>单位</th>
          <th>状态</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="s in props.items" :key="s.id">
          <td>
            <AccountLabel :name="s.name" :url="s.avatar_url" />
          </td>
          <td>{{ s.specification }}</td>
          <td>{{ s.unit }}</td>
          <td>
            <span
              class="status-pill"
              :class="s.active ? 'status-active' : 'status-inactive'"
              >{{ s.active ? "启用" : "停用" }}</span
            >
          </td>
          <td><NButton v-if="editable" @click="edit(s)">编辑</NButton></td>
        </tr>
      </tbody>
    </table>
  </div>
  <NModal v-model:show="show" preset="card" title="SKU 资料" class="dialog"
    ><label>名称<NInput v-model:value="name" /></label
    ><label>规格<NInput v-model:value="specification" /></label
    ><label>单位<NInput v-model:value="unit" /></label
    ><label
      >缩略图 URL<NInput
        v-model:value="avatar"
        placeholder="留空显示名称首字" /></label
    ><NCheckbox v-model:checked="active">启用</NCheckbox>
    <p class="error">{{ error }}</p>
    <NButton :loading="busy" @click="save">保存</NButton></NModal
  >
</template>
