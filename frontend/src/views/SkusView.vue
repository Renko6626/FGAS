<script setup lang="ts">
import { computed, ref } from "vue";
import { NButton, NInput, NModal, NCheckbox, NSelect } from "naive-ui";
import { warehouse } from "../api/warehouse";
import type { Sku } from "../api/warehouse";
import AccountLabel from "../components/AccountLabel.vue";
import TagInput from "../components/TagInput.vue";
const props = defineProps<{ items: Sku[]; editable: boolean }>(),
  emit = defineEmits<{ changed: [] }>();
const show = ref(false),
  busy = ref(false),
  error = ref(""),
  originalCode = ref(""),
  code = ref(""),
  name = ref(""),
  tags = ref<string[]>([]),
  unit = ref(""),
  avatar = ref(""),
  active = ref(true),
  search = ref(""),
  tag = ref<string | null>(null),
  status = ref<string | null>(null);
const tagSuggestions = computed(() => [...new Set([
  "类别:徽章", "类别:立牌", "类别:同人本", ...props.items.flatMap(s => s.tags),
])]);
const tagOptions = computed(() => tagSuggestions.value.map(value => ({ label: value, value })));
const filteredItems = computed(() => {
  const q = search.value.trim().toLocaleLowerCase();
  return props.items.filter(s =>
    (!q || [s.code, s.name].some(value => value.toLocaleLowerCase().includes(q))) &&
    (!tag.value || s.tags.includes(tag.value)) &&
    (status.value === null || s.active === (status.value === "active")),
  );
});
function edit(s?: Sku) {
  originalCode.value = s?.code || "";
  code.value = s?.code || "";
  name.value = s?.name || "";
  tags.value = [...(s?.tags || [])];
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
      code: code.value, name: name.value, tags: tags.value, unit: unit.value,
      avatar_url: avatar.value.trim() || null, active: active.value,
    };
    if (originalCode.value) await warehouse.updateSku(originalCode.value, body);
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
  <p>名称包含款式与规格；数量按整数记录，单位用于说明计数方式。</p>
  <div class="filters">
    <NInput v-model:value="search" clearable placeholder="搜索代号或完整名称" />
    <NSelect v-model:value="tag" clearable filterable :options="tagOptions" placeholder="所有类别与角色标签" />
    <NSelect v-model:value="status" clearable :options="[{ label: '启用', value: 'active' }, { label: '停用', value: 'inactive' }]" placeholder="所有状态" />
  </div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>代号</th>
          <th>完整名称</th>
          <th>标签</th>
          <th>单位</th>
          <th>状态</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="s in filteredItems" :key="s.id">
          <td>{{ s.code }}</td>
          <td>
            <AccountLabel :name="s.name" :url="s.avatar_url" />
          </td>
          <td>{{ s.tags.join("，") || "—" }}</td>
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
        <tr v-if="!filteredItems.length"><td colspan="6">暂无符合条件的商品</td></tr>
      </tbody>
    </table>
  </div>
  <NModal v-model:show="show" preset="card" title="SKU 资料" class="dialog"
    ><label>代号<NInput v-model:value="code" placeholder="字母、数字或连字符，如 ARC-01-A" /></label
    ><p>代号会去除首尾空格并转为大写，不能与其他商品重复。</p
    ><label>完整名称<NInput v-model:value="name" placeholder="如：博丽灵梦立牌 10cm 春服A款" /></label
    ><label>标签<TagInput v-model="tags" :suggestions="tagSuggestions" /></label
    ><p>例如类别:立牌、角色:博丽灵梦，多角色商品可添加多个角色标签。</p
    ><label>单位<NInput v-model:value="unit" /></label
    ><label
      >缩略图 URL<NInput
        v-model:value="avatar"
        placeholder="留空显示名称首字" /></label
    ><NCheckbox v-model:checked="active">启用</NCheckbox>
    <p class="error">{{ error }}</p>
    <NButton :loading="busy" :disabled="!code.trim() || !name.trim() || !unit.trim()" @click="save">保存</NButton></NModal
  >
</template>
