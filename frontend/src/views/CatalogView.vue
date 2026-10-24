<script setup lang="ts">
import { computed, ref } from "vue";
import { NButton, NInput, NModal, NSelect, NCheckbox } from "naive-ui";
import { accountsApi } from "../api/accounts";
import { type Account, type StockAccount, type AccountBase, type AccountKind } from "../api/accounts";
import { kinds } from "../presentation/accounts";
import { money } from "../presentation/funds";
import type { Member } from "../api/members";
import AccountAvatar from "../components/AccountAvatar.vue";
import TagInput from "../components/TagInput.vue";
const props = defineProps<{
  mode: "accounts" | "stock-accounts";
  accounts: Account[];
  locations: StockAccount[];
  members: Member[];
  editable: boolean;
}>();
const emit = defineEmits<{ changed: [] }>();
const show = ref(false),
  id = ref(""),
  name = ref(""),
  kind = ref<AccountKind>("public"),
  member = ref<string | null>(null),
  avatar = ref(""),
  tags = ref<string[]>([]),
  active = ref(true),
  busy = ref(false),
  error = ref("");
const search = ref("");
const filterKind = ref<string | null>(null),
  filterTag = ref<string | null>(null),
  filterMember = ref<string | null>(null);
const all = computed<AccountBase[]>(() =>
  props.mode === "accounts" ? props.accounts : props.locations,
);
const rows = computed(() =>
  all.value.filter(
    (a) =>
      (!search.value.trim() ||
        [a.name, a.member_name || "", ...a.tags].some((v) =>
          v
            .toLocaleLowerCase()
            .includes(search.value.trim().toLocaleLowerCase()),
        )) &&
      (!filterKind.value || a.kind === filterKind.value) &&
      (!filterTag.value || a.tags.includes(filterTag.value)) &&
      (!filterMember.value || a.member_id === filterMember.value),
  ),
);
const tagOptions = computed(() =>
  [...new Set(all.value.flatMap((a) => a.tags))].map((value) => ({
    label: value,
    value,
  })),
);
const memberOptions = computed(() =>
  props.members.map((m) => ({ label: m.name, value: m.id })),
);
function edit(a?: AccountBase) {
  id.value = a?.id || "";
  name.value = a?.name || "";
  kind.value = a?.kind || "public";
  member.value = a?.member_id || null;
  avatar.value = a?.avatar_url || "";
  tags.value = [...(a?.tags || [])];
  active.value = a?.active ?? true;
  error.value = "";
  show.value = true;
}
async function save() {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    const body = {
      name: name.value, member_id: member.value,
      avatar_url: avatar.value || null, tags: tags.value, active: active.value,
    };
    if (props.mode === "accounts") {
      if (id.value) await accountsApi.update(id.value, body);
      else await accountsApi.create({ ...body, kind: kind.value });
    } else {
      if (id.value) await accountsApi.updateStock(id.value, body);
      else await accountsApi.createStock({ ...body, kind: kind.value });
    }
    show.value = false;
    emit("changed");
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
const custodyShow = ref(false),
  custodyId = ref(""),
  custodian = ref<string | null>(null);
function custody(a: AccountBase) {
  custodyId.value = a.id;
  custodian.value = (a as StockAccount).current_custody?.member_id || null;
  error.value = "";
  custodyShow.value = true;
}
async function saveCustody() {
  if (busy.value) return;
  busy.value = true;
  try {
    await accountsApi.setCustody(custodyId.value, custodian.value);
    custodyShow.value = false;
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
    <div>
      <h2>{{ mode === "accounts" ? "账户一览" : "货物账户" }}</h2>
    </div>
    <NButton v-if="editable" @click="edit()">新建账户</NButton>
  </div>
  <div
    v-if="mode === 'accounts'"
    class="catalog-categories"
    aria-label="账户类型"
  >
    <button :class="{ active: filterKind === null }" @click="filterKind = null">
      全部 <span>{{ all.length }}</span>
    </button>
    <button
      v-for="(label, value) in kinds"
      :key="value"
      :class="{ active: filterKind === value }"
      @click="filterKind = value"
    >
      {{ label }} <span>{{ all.filter((a) => a.kind === value).length }}</span>
    </button>
  </div>
  <div class="catalog-filters">
    <NInput
      v-model:value="search"
      clearable
      placeholder="搜索账户、联系人或标签"
      :input-props="{ 'aria-label': '搜索账户' }"
    />
    <NSelect
      v-if="mode !== 'accounts'"
      v-model:value="filterKind"
      clearable
      placeholder="所有类型"
      :options="
        Object.entries(kinds).map(([value, label]) => ({ value, label }))
      "
    />
    <NSelect
      v-model:value="filterTag"
      clearable
      placeholder="所有标签"
      :options="tagOptions"
    />
    <NSelect
      v-model:value="filterMember"
      clearable
      placeholder="所有联系人"
      :options="memberOptions"
    />
  </div>

  <div v-if="!rows.length" class="empty-state">
    <h3>{{ all.length ? "没有符合条件的账户" : "还没有账户" }}</h3>
    <p>
      {{
        all.length ? "试试其他分类或清空筛选。" : "可新建公账、私账或外部账户。"
      }}
    </p>
    <NButton
      v-if="all.length"
      @click="
        search = '';
        filterKind = null;
        filterTag = null;
        filterMember = null;
      "
      >清空筛选</NButton
    ><NButton v-else-if="editable" @click="edit()">新建账户</NButton>
  </div>
  <div v-else-if="mode === 'accounts'" class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>账户</th>
          <th>类型</th>
          <th>联系人</th>
          <th class="numeric">余额（元）</th>
          <th>标签</th>
          <th>状态</th>
          <th v-if="editable"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="a in rows" :key="a.id">
          <td class="account-name">
            <AccountAvatar :name="a.name" :url="a.avatar_url" />{{ a.name }}
          </td>
          <td>{{ kinds[a.kind] }}</td>
          <td>{{ a.member_name || "—" }}</td>
          <td class="numeric">{{ money((a as Account).balance_minor) }}</td>
          <td>
            <span v-for="tag in a.tags" :key="tag" class="tag">{{ tag }}</span
            ><span v-if="!a.tags.length">—</span>
          </td>
          <td>
            <span
              class="status-pill"
              :class="a.active ? 'status-active' : 'status-inactive'"
              >{{ a.active ? "启用" : "停用" }}</span
            >
          </td>
          <td v-if="editable">
            <NButton size="small" class="plain-button" text @click="edit(a)"
              >编辑</NButton
            >
          </td>
        </tr>
      </tbody>
    </table>
  </div>
  <div v-else class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>账户</th>
          <th>类型</th>
          <th>联系人</th>
          <th>标签</th>
          <th>当前保管人</th>
          <th>状态</th>
          <th v-if="editable">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="a in rows" :key="a.id">
          <td>
            <AccountAvatar :name="a.name" :url="a.avatar_url" />{{ a.name }}
          </td>
          <td>{{ kinds[a.kind] }}</td>
          <td>{{ a.member_name || "未绑定" }}</td>
          <td>{{ a.tags.join("，") || "—" }}</td>
          <td>
            {{ (a as StockAccount).current_custody?.member_name || "未指定" }}
          </td>
          <td>
            <span
              class="status-pill"
              :class="a.active ? 'status-active' : 'status-inactive'"
              >{{ a.active ? "启用" : "停用" }}</span
            >
          </td>
          <td v-if="editable">
            <NButton size="small" @click="edit(a)">编辑</NButton
            ><NButton
              v-if="a.kind !== 'external'"
              size="small"
              @click="custody(a)"
              >保管关系</NButton
            >
          </td>
        </tr>
      </tbody>
    </table>
  </div>
  <NModal
    v-model:show="show"
    preset="card"
    :title="id ? '编辑账户' : '新建账户'"
    class="dialog compact-dialog"
  >
    <label
      >账户名称<NInput
        v-model:value="name"
        placeholder="填写便于识别的名称" /></label
    ><label
      >账户类型<NSelect
        v-model:value="kind"
        :disabled="!!id"
        :options="
          Object.entries(kinds).map(([value, label]) => ({ value, label }))
        "
    /></label>
    <p v-if="id" class="muted">类型创建后固定，需要其他类型时请新建账户。</p>
    <label
      >联系人 <span class="field-optional">可选</span
      ><NSelect
        v-model:value="member"
        clearable
        :options="memberOptions"
        placeholder="选择成员或联系人"
    /></label>
    <label
      >标签 <span class="field-optional">可选</span><TagInput v-model="tags"
    /></label>
    <label
      >{{ mode === "stock-accounts" ? "缩略图 URL" : "头像 URL"
      }}<NInput v-model:value="avatar" placeholder="留空显示名称首字"
    /></label>
    <details class="disclosure">
      <summary>账户状态</summary>
      <NCheckbox v-model:checked="active">启用账户</NCheckbox>
      <p v-if="id" class="internal-id">账户编号：{{ id }}</p>
    </details>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div class="actions">
      <NButton @click="show = false">取消</NButton
      ><NButton type="primary" :loading="busy" @click="save">保存账户</NButton>
    </div>
  </NModal>
  <NModal
    v-model:show="custodyShow"
    preset="card"
    title="当前保管成员"
    class="dialog compact-dialog"
    ><p class="muted">保管关系独立于联系人，交接后保留历史。</p>
    <label
      >保管成员<NSelect
        v-model:value="custodian"
        clearable
        :options="memberOptions"
        placeholder="选择成员，清空可结束保管"
    /></label>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div class="actions">
      <NButton type="primary" :loading="busy" @click="saveCustody"
        >保存保管关系</NButton
      >
    </div></NModal
  >
</template>

<style scoped>
.catalog-categories {
  display: flex;
  gap: 24px;
  border-bottom: 1px solid black;
  margin-bottom: 20px;
}
.catalog-categories button {
  border: 0 !important;
  border-image: none !important;
  background: none;
  padding: 8px 0 12px;
  color: #666;
  font-size: 18px;
  min-width: 0 !important;
}
.catalog-categories button.active {
  color: black;
  text-decoration: underline;
  text-underline-offset: 14px;
}
.catalog-categories span {
  font-family: Arial, sans-serif !important;
  font-size: 12px;
  margin-left: 5px;
  color: #666 !important;
}
.catalog-filters {
  display: flex;
  gap: 12px;
  margin-bottom: 22px;
  flex-wrap: wrap;
}
.catalog-filters > .n-input {
  flex: 2 1 200px;
}
.catalog-filters > .n-select {
  flex: 1 1 140px;
}
.account-name {
  min-width: 160px;
}
</style>
