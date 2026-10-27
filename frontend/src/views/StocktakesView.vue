<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch, onMounted } from "vue";
import { NButton, NInput, NModal } from "naive-ui";
import type { Account, StockAccount } from "../api/accounts";
import type { Sku } from "../api/warehouse";
import type { TransferInput } from "../api/funds";
import type { Member } from "../api/members";
import {
  stocktakesApi,
  type StocktakeKind,
  type Stocktake,
  type StocktakeDetail,
} from "../api/stocktakes";
import AccountLabel from "../components/AccountLabel.vue";
import PaginationBar from "../components/PaginationBar.vue";
import StocktakeFundRecords from "../components/StocktakeFundRecords.vue";
import StocktakeStockRecords from "../components/StocktakeStockRecords.vue";
import TransferEditor from "../components/TransferEditor.vue";
import StockTransferEditor from "../components/StockTransferEditor.vue";

const props = defineProps<{
  accounts: Account[];
  locations: StockAccount[];
  skus: Sku[];
  members: Member[];
  trusted: boolean;
}>();
const emit = defineEmits<{ changed: []; notice: [string] }>();
const kind = ref<StocktakeKind>("fund"),
  items = ref<Stocktake[]>([]),
  detail = shallowRef<StocktakeDetail | null>(null);
const busy = ref(false),
  error = ref(""),
  search = ref(""),
  page = ref(1),
  limit = ref(20),
  total = ref(0),
  statusFilter = ref("all");
let filterTimer: number | undefined;
const showCreate = ref(false),
  showDescription = ref(false),
  name = ref(""),
  description = ref(""),
  editDescription = ref("");
const showFund = ref(false),
  initial = ref<Partial<TransferInput>>({}),
  stockEditor = ref<InstanceType<typeof StockTransferEditor> | null>(null);
const endpointAccounts = computed(() =>
  kind.value === "fund" ? props.accounts : props.locations,
);
const hasFilters = computed(() => !!search.value.trim() || statusFilter.value !== "all");
function avatar(id: string) {
  return endpointAccounts.value.find((a) => a.code === id)?.avatar_url;
}
async function loadList() {
  const result = await stocktakesApi.list(kind.value, {
    q: search.value.trim() || undefined,
    status: statusFilter.value === "all" ? undefined : statusFilter.value,
    page: page.value,
    limit: limit.value,
  });
  items.value = result.items;
  total.value = result.total;
}
async function load() {
  busy.value = true;
  error.value = "";
  try {
    await loadList();
    if (detail.value) {
      detail.value = await stocktakesApi.detail(
        kind.value,
        detail.value.stocktake.id,
      );
      editDescription.value = detail.value.stocktake.description;
    }
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
async function open(item: Stocktake) {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    detail.value = await stocktakesApi.detail(kind.value, item.id);
    editDescription.value = detail.value.stocktake.description;
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
function create() {
  name.value = "";
  description.value = "";
  error.value = "";
  showCreate.value = true;
}
function edit() {
  if (!detail.value) return;
  editDescription.value = detail.value.stocktake.description;
  showDescription.value = true;
}
async function run(action: "create" | "description" | "end") {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    let identifier = detail.value?.stocktake.id;
    if (action === "create") {
      const item = await stocktakesApi.create(kind.value, {
        name: name.value,
        description: description.value,
      });
      identifier = item.id;
      showCreate.value = false;
    } else if (identifier) {
      if (action === "end") await stocktakesApi.end(kind.value, identifier);
      else {
        await stocktakesApi.update(
          kind.value,
          identifier,
          editDescription.value,
        );
        showDescription.value = false;
      }
    }
    if (identifier) {
      detail.value = await stocktakesApi.detail(kind.value, identifier);
      editDescription.value = detail.value.stocktake.description;
    }
    await loadList();
    emit("changed");
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
async function changed() {
  emit("changed");
  await load();
}
function createTransfer(gain: boolean) {
  const item = detail.value?.stocktake;
  if (!item) return;
  if (kind.value === "fund") {
    const fund =
      props.accounts.find((a) => a.kind === "public" && a.active)?.code || "";
    initial.value = {
      source_account_code: gain ? item.gain_account_code : fund,
      destination_account_code: gain ? fund : item.loss_account_code,
    };
    showFund.value = true;
  } else
    stockEditor.value?.open({
      source_account_code: gain ? item.gain_account_code : "",
      destination_account_code: gain ? "" : item.loss_account_code,
      tags: [gain ? "盘盈" : "盘亏"],
    });
}
watch(kind, () => {
  detail.value = null;
  showFund.value = false;
  showCreate.value = false;
  showDescription.value = false;
  search.value = "";
  statusFilter.value = "all";
  const wasFirst = page.value === 1;
  page.value = 1;
  if (wasFirst) load();
});
watch([search, statusFilter], () => {
  const wasFirst = page.value === 1;
  page.value = 1;
  if (wasFirst) {
    window.clearTimeout(filterTimer);
    filterTimer = window.setTimeout(load, 250);
  }
});
watch(page, () => {
  if (!detail.value) load();
});
watch(limit, () => {
  window.clearTimeout(filterTimer);
  if (page.value === 1) load();
  else page.value = 1;
});
onBeforeUnmount(() => window.clearTimeout(filterTimer));
onMounted(load);
</script>

<template>
  <template v-if="!detail">
    <div class="toolbar">
      <div class="segmented-tabs stocktake-kind">
        <button
          :disabled="busy"
          :class="{ active: kind === 'fund' }"
          @click="kind = 'fund'"
        >
          资金盘点</button
        ><button
          :disabled="busy"
          :class="{ active: kind === 'stock' }"
          @click="kind = 'stock'"
        >
          货物盘点
        </button>
      </div>
      <div class="inline-actions">
        <NButton :loading="busy" @click="load">刷新</NButton
        ><NButton v-if="trusted" :disabled="busy" @click="create"
          >新建盘点</NButton
        >
      </div>
    </div>
    <div class="stocktake-query">
      <NInput
        v-model:value="search"
        clearable
        placeholder="搜索盘点名称或说明"
        :input-props="{ 'aria-label': '搜索盘点' }"
      />
      <div class="stocktake-status-filter">
        <button
          v-for="option in [
            { value: 'all', label: '全部' },
            { value: 'in_progress', label: '进行中' },
            { value: 'ended', label: '已结束' },
          ]"
          :key="option.value"
          :class="{ active: statusFilter === option.value }"
          @click="statusFilter = option.value"
        >
          {{ option.label }}
        </button>
      </div>
    </div>
    <p v-if="error && !showCreate" class="error" role="alert">{{ error }}</p>
    <div v-if="items.length" class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>盘点名称</th>
            <th>状态</th>
            <th>说明</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.id">
            <td>{{ item.name }}</td>
            <td>
              <span class="status-pill" :class="`status-${item.status}`">{{
                item.status === "ended" ? "已结束" : "进行中"
              }}</span>
            </td>
            <td>{{ item.description || "—" }}</td>
            <td>
              <NButton
                class="plain-button"
                text
                :disabled="busy"
                @click="open(item)"
                >查看</NButton
              >
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-else class="empty-state">
      <p>
        {{
          busy
            ? "正在读取盘点"
            : hasFilters
              ? "没有符合条件的盘点"
              : "暂无盘点"
        }}
      </p>
      <NButton v-if="!busy && !items.length && trusted" @click="create"
        >新建盘点</NButton
      >
    </div>
    <PaginationBar
      v-if="total > limit"
      :page="page"
      :limit="limit"
      :total="total"
      @update:page="page = $event"
      @update:limit="limit = $event"
    />
  </template>
  <section v-else class="stocktake-detail">
    <div class="toolbar">
      <NButton class="plain-button" text :disabled="busy" @click="detail = null"
        >返回{{ kind === "fund" ? "资金" : "货物" }}盘点</NButton
      >
      <div class="inline-actions">
        <NButton :loading="busy" @click="load">刷新</NButton
        ><NButton v-if="trusted" :disabled="busy" @click="edit"
          >修改说明</NButton
        ><NButton
          v-if="trusted && detail.stocktake.status !== 'ended'"
          :disabled="busy"
          @click="run('end')"
          >结束盘点</NButton
        >
      </div>
    </div>
    <div class="stocktake-title">
      <h2>{{ detail.stocktake.name }}</h2>
      <span class="status-pill" :class="`status-${detail.stocktake.status}`">{{
        detail.stocktake.status === "ended" ? "已结束" : "进行中"
      }}</span>
    </div>
    <p v-if="detail.stocktake.description">
      {{ detail.stocktake.description }}
    </p>
    <p v-if="error && !showDescription" class="error" role="alert">
      {{ error }}
    </p>
    <div class="stocktake-record-heading">
      <h3>盘点流水</h3>
      <div class="inline-actions">
        <NButton :disabled="busy" @click="createTransfer(true)"
          >登记盘盈</NButton
        ><NButton :disabled="busy" @click="createTransfer(false)"
          >登记盘亏</NButton
        >
      </div>
    </div>
    <StocktakeFundRecords
      v-if="detail.kind === 'fund'"
      :key="detail.stocktake.id"
      :items="detail.transfers"
      :accounts="accounts"
      :trusted="trusted"
      @changed="changed"
      @notice="emit('notice', $event)"
    />
    <StocktakeStockRecords
      v-else
      :key="detail.stocktake.id"
      :items="detail.transfers"
      :locations="locations"
      :trusted="trusted"
      :skus="skus"
      :accounts="accounts"
      @changed="changed"
    />
    <details class="disclosure">
      <summary>盘点账户与创建信息</summary>
      <dl>
        <dt>盘盈账户</dt>
        <dd>
          <AccountLabel
            :name="detail.stocktake.gain_account_name"
            :url="avatar(detail.stocktake.gain_account_code)"
          />
        </dd>
        <dt>盘亏账户</dt>
        <dd>
          <AccountLabel
            :name="detail.stocktake.loss_account_name"
            :url="avatar(detail.stocktake.loss_account_code)"
          />
        </dd>
        <dt>创建时间</dt>
        <dd>
          {{ new Date(detail.stocktake.created_at).toLocaleString("zh-CN") }}
        </dd>
        <dt>创建人</dt>
        <dd>{{ detail.stocktake.created_by }}</dd>
        <dt>盘点编号</dt>
        <dd>{{ detail.stocktake.id }}</dd>
      </dl>
    </details>
  </section>
  <NModal
    v-model:show="showCreate"
    preset="card"
    :title="kind === 'fund' ? '新建资金盘点' : '新建货物盘点'"
    class="dialog compact-dialog"
    :closable="!busy"
    :mask-closable="!busy"
    :close-on-esc="!busy"
    ><label
      >名称<NInput
        v-model:value="name"
        :disabled="busy"
        maxlength="200" /></label
    ><label
      >说明<NInput
        v-model:value="description"
        :disabled="busy"
        type="textarea"
        :autosize="{ minRows: 2, maxRows: 5 }"
    /></label>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div class="actions">
      <NButton :disabled="busy" @click="showCreate = false">取消</NButton
      ><NButton
        type="primary"
        :loading="busy"
        :disabled="!name.trim()"
        @click="run('create')"
        >创建盘点</NButton
      >
    </div></NModal
  >
  <NModal
    v-model:show="showDescription"
    preset="card"
    title="修改盘点说明"
    class="dialog compact-dialog"
    :closable="!busy"
    :mask-closable="!busy"
    :close-on-esc="!busy"
    ><label
      >说明<NInput
        v-model:value="editDescription"
        :disabled="busy"
        type="textarea"
        :autosize="{ minRows: 3, maxRows: 6 }"
    /></label>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div class="actions">
      <NButton :disabled="busy" @click="showDescription = false">取消</NButton
      ><NButton type="primary" :loading="busy" @click="run('description')"
        >保存说明</NButton
      >
    </div></NModal
  >
  <TransferEditor
    :show="showFund"
    :accounts="accounts"
    :initial="initial"
    @close="showFund = false"
    @saved="changed"
  />
  <StockTransferEditor
    ref="stockEditor"
    hide-trigger
    :locations="locations"
    :skus="skus"
    :accounts="accounts"
    :trusted="trusted"
    @saved="changed"
  />
</template>

<style scoped>
.stocktake-kind {
  margin: 0;
  border-bottom: 0;
  padding: 0;
}
.stocktake-query {
  display: flex;
  gap: 20px;
  align-items: center;
  margin-bottom: 24px;
}
.stocktake-query > .n-input {
  max-width: 460px;
}
.stocktake-status-filter {
  display: flex;
  gap: 16px;
  flex-shrink: 0;
}
.stocktake-status-filter button {
  border: 0;
  border-image: none;
  background: none;
  padding: 4px 0;
  min-width: 0;
  color: #666;
}
.stocktake-status-filter button.active {
  color: black;
  text-decoration: underline;
  text-underline-offset: 5px;
}
.stocktake-title {
  display: flex;
  align-items: center;
  gap: 16px;
  margin: 28px 0 16px;
}
.stocktake-title h2 {
  margin: 0;
}
.stocktake-record-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 24px 0 20px;
  margin-top: 24px;
  border-top: 1px solid #ccc;
}
.stocktake-record-heading h3 {
  margin: 0;
  font-size: 20px;
}
@media (max-width: 760px) {
  .toolbar {
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .stocktake-query {
    flex-wrap: wrap;
    gap: 14px;
  }
  .stocktake-query > .n-input {
    max-width: none;
  }
  .stocktake-record-heading {
    flex-wrap: wrap;
  }
  .stocktake-title {
    flex-wrap: wrap;
  }
  .stocktake-title h2 {
    overflow-wrap: anywhere;
  }
}
</style>
