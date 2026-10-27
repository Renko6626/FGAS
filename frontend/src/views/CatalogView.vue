<script setup lang="ts">
import { computed, ref } from "vue";
import { NButton, NInput, NModal, NSelect, NCheckbox } from "naive-ui";
import { accountsApi } from "../api/accounts";
import { type Account, type StockAccount, type AccountBase, type AccountKind, type StockAccountKind, type ResponsibilityHistory } from "../api/accounts";
import { kinds, stockKinds } from "../presentation/accounts";
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
  kind = ref<AccountKind | StockAccountKind>("public"),
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
const kindLabels = computed(() => props.mode === "accounts" ? kinds : stockKinds);
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
      (!filterMember.value || a.member_code === filterMember.value),
  ).sort((a, b) => {
    if (props.mode !== "accounts") return 0;
    const left = (a as Account).last_posted_at;
    const right = (b as Account).last_posted_at;
    if (!left || !right) return left ? -1 : right ? 1 : a.name.localeCompare(b.name, "zh-CN");
    return Date.parse(right) - Date.parse(left) || a.name.localeCompare(b.name, "zh-CN");
  }),
);
const tagOptions = computed(() =>
  [...new Set(all.value.flatMap((a) => a.tags))].map((value) => ({
    label: value,
    value,
  })),
);
const memberOptions = computed(() =>
  props.members.map((m) => ({ label: `${m.name}（${m.code}）`, value: m.code })),
);
function edit(a?: AccountBase) {
  id.value = a?.code || "";
  name.value = a?.name || "";
  kind.value = a?.kind || (props.mode === "accounts" ? "public" : "internal");
  member.value = a?.member_code || null;
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
      name: name.value, member_code: member.value,
      avatar_url: avatar.value || null, tags: tags.value, active: active.value,
    };
    if (props.mode === "accounts") {
      if (id.value) await accountsApi.update(id.value, body);
      else await accountsApi.create({ ...body, kind: kind.value as AccountKind });
    } else {
      if (id.value) await accountsApi.updateStock(id.value, body);
      else await accountsApi.createStock({ ...body, kind: kind.value as StockAccountKind });
    }
    show.value = false;
    emit("changed");
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
const historyShow = ref(false), historyName = ref(""), historyBusy = ref(false);
const historyRows = ref<ResponsibilityHistory[]>([]);
async function history(a: AccountBase) {
  historyName.value = a.name;
  historyRows.value = [];
  historyShow.value = true;
  historyBusy.value = true;
  error.value = "";
  try {
    historyRows.value = (await accountsApi.stockDetail(a.code)).responsibility_history;
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    historyBusy.value = false;
  }
}
function dateText(value: string) { return new Date(value).toLocaleString("zh-CN", { hour12: false }); }
</script>
<template>
  <div class="toolbar">
    <div>
      <h2>{{ mode === "accounts" ? "账户一览" : "货物账户" }}</h2>
    </div>
    <NButton v-if="editable" @click="edit()">新建账户</NButton>
  </div>
  <div
    class="catalog-categories"
    aria-label="账户类型"
  >
    <button :class="{ active: filterKind === null }" :aria-pressed="filterKind === null" @click="filterKind = null">
      全部 <span>{{ all.length }}</span>
    </button>
    <button
      v-for="(label, value) in kindLabels"
      :key="value"
      :class="{ active: filterKind === value }"
      :aria-pressed="filterKind === value"
      @click="filterKind = value"
    >
      {{ label }} <span>{{ all.filter((a) => a.kind === value).length }}</span>
    </button>
  </div>
  <div class="catalog-filters">
    <NInput
      v-model:value="search"
      clearable
      :placeholder="mode === 'accounts' ? '搜索账户、联系人或标签' : '搜索账户、负责人或标签'"
      :input-props="{ 'aria-label': '搜索账户' }"
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
      :placeholder="mode === 'accounts' ? '所有联系人' : '所有负责人'"
      :options="memberOptions"
    />
  </div>

  <div v-if="!rows.length" class="empty-state">
    <h3>{{ all.length ? "没有符合条件的账户" : "还没有账户" }}</h3>
    <p>
      {{
        all.length ? "试试其他分类或清空筛选。" : mode === "accounts" ? "可新建公账、私账或外部账户。" : "可新建实际保管或外部账户，成员长期代管也属于实际保管。"
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
  <div v-else class="account-grid">
    <article v-for="a in rows" :key="a.code" class="account-card" :class="{ inactive: !a.active }">
      <div class="card-heading">
        <AccountAvatar :name="a.name" :url="a.avatar_url" />
        <div class="card-name"><strong>{{ a.name }}</strong><small>{{ a.code }}</small></div>
        <span v-if="!a.active" class="status-pill status-inactive">已停用</span>
      </div>
      <div v-if="mode === 'accounts'" class="card-balance"><span>账户余额</span><strong>¥ {{ money((a as Account).balance_minor) }}</strong></div>
      <div v-else class="card-custodian" :class="{ unassigned: a.kind === 'internal' && !a.member_name }">
        <span>{{ a.kind === 'internal' ? '负责人' : '账户类型' }}</span>
        <strong>{{ a.kind === 'internal' ? a.member_name || '未指定负责人' : '外部账户' }}</strong>
      </div>
      <div class="card-meta"><span>{{ kindLabels[a.kind] }}</span><span v-if="mode === 'accounts' && a.member_name">联系人：{{ a.member_name }}</span><span v-else-if="a.kind === 'external' && a.member_name">负责人：{{ a.member_name }}</span></div>
      <div v-if="a.tags.length" class="card-tags"><span v-for="tag in a.tags" :key="tag" class="tag">{{ tag }}</span></div>
      <div v-if="editable || mode === 'stock-accounts'" class="card-actions"><NButton v-if="editable" text @click="edit(a)">编辑账户</NButton><NButton v-if="mode === 'stock-accounts'" text :disabled="historyBusy" @click="history(a)">负责人历史</NButton></div>
    </article>
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
          Object.entries(kindLabels).map(([value, label]) => ({ value, label }))
        "
    /></label>
    <p v-if="id" class="muted">类型创建后固定，需要其他类型时请新建账户。</p>
    <label
      >{{ mode === 'accounts' ? '联系人' : '负责人' }} <span class="field-optional">可选</span
      ><NSelect
        v-model:value="member"
        clearable
        :options="memberOptions"
        :placeholder="mode === 'accounts' ? '选择成员或联系人' : '选择负责人，清空表示暂未指定'"
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
    v-model:show="historyShow"
    preset="card"
    title="负责人历史"
    class="dialog"
    :style="{ width: '900px', maxWidth: 'calc(100vw - 32px)' }"
  >
    <p>{{ historyName }}</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="historyBusy">正在读取历史</p>
    <div v-else class="table-wrap">
      <table>
        <thead><tr><th>负责人</th><th>开始时间</th><th>结束时间</th><th>设置人</th><th>结束人</th></tr></thead>
        <tbody>
          <tr v-for="row in historyRows" :key="row.member_code + row.valid_from">
            <td>{{ row.member_name }}</td><td>{{ dateText(row.valid_from) }}</td>
            <td>{{ row.valid_to ? dateText(row.valid_to) : '至今' }}</td>
            <td>{{ row.actor_name }}</td><td>{{ row.ended_by_name || '—' }}</td>
          </tr>
          <tr v-if="!historyRows.length"><td colspan="5">尚无负责人记录</td></tr>
        </tbody>
      </table>
    </div>
  </NModal>
</template>

<style scoped>
.catalog-categories { display:flex; flex-wrap:wrap; gap:4px; border-bottom:1px solid #e3e8ec; margin-bottom:16px; }
.catalog-categories button { border:0 !important; border-bottom:2px solid transparent !important; border-image:none !important; background:none; padding:9px 14px; color:#66707c; font-size:14px; min-width:0 !important; }
.catalog-categories button.active { color:#244a66; border-bottom-color:#345d78 !important; font-weight:650; }
.catalog-categories span { font-size:12px; margin-left:5px; color:#66707c !important; }
.account-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(230px,1fr)); gap:10px 14px; }
.account-card { min-width:0; display:flex; flex-direction:column; padding:12px 14px; border:1px solid #e3e8ec; border-radius:8px; background:#fff; }
.account-card.inactive { background:#f5f6f5; border-color:#d8ddd8; }
.account-card.inactive .card-name,.account-card.inactive .card-balance,.account-card.inactive .card-custodian { opacity:.65; }
.card-heading { display:flex; align-items:center; gap:8px; min-width:0; }
.card-heading :deep(.account-avatar) { width:36px; height:36px; margin:0; border-radius:50%; font-size:16px; }
.card-name { flex:1; min-width:0; }
.card-name strong,.card-name small { display:block; overflow-wrap:anywhere; }
.card-name strong { font-size:15px; line-height:1.4; }
.card-name small { font-size:12px; line-height:1.4; margin-top:1px; }
.card-balance,.card-custodian { display:flex; flex-wrap:wrap; align-items:baseline; justify-content:space-between; gap:2px 8px; margin-top:10px; }
.card-balance span,.card-custodian span,.card-meta { color:#66707c; font-size:12px; }
.card-balance strong { font-size:22px; font-variant-numeric:tabular-nums; overflow-wrap:anywhere; }
.card-custodian strong { font-size:22px; overflow-wrap:anywhere; }
.card-custodian.unassigned strong { color:#976a26; font-size:18px; }
.card-meta { display:flex; flex-wrap:wrap; gap:3px 14px; margin-top:6px; }
.card-tags { margin-top:4px; }
.card-actions { display:flex; flex-wrap:wrap; gap:4px 10px; margin-top:auto; padding-top:6px; }
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
@media(max-width:360px) { .account-grid { grid-template-columns:minmax(0,1fr); } }
</style>
