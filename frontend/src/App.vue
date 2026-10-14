<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from "vue";
import { NButton, NSelect, NModal, NConfigProvider, zhCN } from "naive-ui";
import { workspaceTheme } from "./theme";
import DashboardView from "./views/DashboardView.vue";
import {
  api,
  money,
  type User,
  type Account,
  type StockAccount,
  type Transfer,
} from "./api/funds";
import StocktakesView from "./views/StocktakesView.vue";
import CatalogView from "./views/CatalogView.vue";
import TransfersView from "./views/TransfersView.vue";
import SettlementsView from "./views/SettlementsView.vue";
import MembersView from "./views/MembersView.vue";
import UsersView from "./views/UsersView.vue";
import { warehouse, type StockTransfer } from "./api/warehouse";
import { membersApi } from "./api/members";
import type { Sku, Member } from "./api/funds";
import SkusView from "./views/SkusView.vue";
import InventoryView from "./views/InventoryView.vue";
import StockTransfersView from "./views/StockTransfersView.vue";
import StockTransferEditor from "./components/StockTransferEditor.vue";
import TransferEditor from "./components/TransferEditor.vue";
import AccountAvatar from "./components/AccountAvatar.vue";
const user = ref<User | null>(null),
  users = ref<User[]>([]),
  selected = ref<string | null>(null),
  accounts = ref<Account[]>([]),
  locations = ref<StockAccount[]>([]),
  transfers = ref<Transfer[]>([]),
  total = ref(0),
  tab = ref("home"),
  error = ref(""),
  notice = ref(""),
  busy = ref(false),
  showTransfer = ref(false),
  opening = ref(false);
const switching = ref(false);
const skus = ref<Sku[]>([]),
  stock = ref<StockTransfer[]>([]),
  members = ref<Member[]>([]),
  revision = ref(0);
const identityEpoch = ref(0);

const trusted = computed(
  () => user.value?.role === "trusted" || user.value?.role === "admin",
);
const roles = { admin: "管理员", trusted: "受信任用户", untrusted: "普通用户" };
const mobileNav = ref(false),
  showIdentity = ref(false),
  approvalType = ref("funds");
const stockEditor = ref<InstanceType<typeof StockTransferEditor> | null>(null);
const pages: Record<string, { title: string }> = {
  home: { title: "工作首页" },
  accounts: { title: "资金账户" },
  transfers: { title: "资金流水" },
  settlements: { title: "私账结算" },
  approvals: { title: "待办审批" },
  stock: { title: "货物转移" },
  stocktakes: { title: "阶段盘点" },
  inventory: { title: "当前库存" },
  skus: { title: "货物目录" },
  locations: { title: "货物账户" },
  members: { title: "成员与联系人" },
  users: { title: "用户权限" },
};
const groups = computed(() => [
  {
    label: "日常工作",
    items: [
      { value: "home", label: "工作首页" },
      ...(trusted.value ? [{ value: "approvals", label: "待办审批" }] : []),
    ],
  },
  {
    label: "资金",
    items: [
      { value: "accounts", label: "资金账户" },
      { value: "transfers", label: "资金流水" },
      { value: "settlements", label: "私账结算" },
    ],
  },
  {
    label: "货物",
    items: [
      { value: "inventory", label: "当前库存" },
      { value: "stock", label: "货物转移" },
      { value: "locations", label: "货物账户" },
      { value: "skus", label: "货物目录" },
    ],
  },
  {
    label: "盘点",
    items: [{ value: "stocktakes", label: "阶段盘点" }],
  },
  {
    label: "基础资料",
    items: [
      { value: "members", label: "成员与联系人" },
      ...(user.value?.role === "admin"
        ? [{ value: "users", label: "用户权限" }]
        : []),
    ],
  },
]);
const nav = computed(() => groups.value.flatMap((group) => group.items));
const currentPage = computed(() => pages[tab.value] || pages.home!);
const approvalCount = computed(
  () =>
    transfers.value.filter((t) => t.status === "pending").length +
    stock.value.filter(
      (t) =>
        t.status === "pending" ||
        t.confirmations.some((c) => c.status === "pending"),
    ).length,
);
function navigate(value: string, approval?: "funds" | "stock") {
  if (approval) approvalType.value = approval;
  if (!nav.value.some((item) => item.value === value)) return;
  tab.value = value;
  mobileNav.value = false;
  window.location.hash = value;
}
function readPageHash() {
  if (!user.value) return;
  const value = window.location.hash.slice(1);
  tab.value = nav.value.some((item) => item.value === value) ? value : "home";
  mobileNav.value = false;
}
onBeforeUnmount(() => window.removeEventListener("hashchange", readPageHash));
function createStock() {
  stockEditor.value?.open();
}

async function refresh() {
  if (!user.value) return;
  const epoch = identityEpoch.value,
    actor = user.value.id;
  busy.value = true;
  error.value = "";
  try {
    const [a, l, t, s, k, w, m] = await Promise.all([
      api.accounts(),
      api.stockAccounts(),
      api.transfers(),
      api.summary(),
      warehouse.skus(),
      warehouse.transfers(),
      membersApi.list(),
    ]);
    if (epoch !== identityEpoch.value || actor !== user.value?.id) return;
    accounts.value = a;
    locations.value = l;
    transfers.value = t;
    total.value = s.total_minor;
    skus.value = k;
    stock.value = w;
    members.value = m;
    revision.value++;
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
async function identities() {
  users.value = await api.users();
}
async function login() {
  if (!selected.value || switching.value) return;
  switching.value = true;
  busy.value = true;
  error.value = "";
  try {
    showTransfer.value = false;
    identityEpoch.value++;
    await api.login(selected.value);
    user.value = await api.me();
    identityEpoch.value++;
    tab.value = "home";
    window.location.hash = "home";
    showIdentity.value = false;
    mobileNav.value = false;
    notice.value = "开发账号已切换";
    await refresh();
  } catch (e) {
    user.value = null;
    stock.value = [];
    skus.value = [];
    members.value = [];
    accounts.value = [];
    locations.value = [];
    transfers.value = [];
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
    switching.value = false;
  }
}
async function logout() {
  if (switching.value) return;
  switching.value = true;
  try {
    showTransfer.value = false;
    identityEpoch.value++;
    await api.logout();
    user.value = null;
    stock.value = [];
    skus.value = [];
    members.value = [];
    accounts.value = [];
    locations.value = [];
    transfers.value = [];
    notice.value = "已退出";
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    switching.value = false;
  }
}
async function permissionChanged() {
  identityEpoch.value++;
  await identities();
  try {
    user.value = await api.me();
    if (!nav.value.some((n) => n.value === tab.value)) navigate("home");
    await refresh();
  } catch (e) {
    user.value = null;
    error.value = (e as Error).message;
  }
}
function create(isOpening = false) {
  opening.value = isOpening;
  showTransfer.value = true;
}
onMounted(async () => {
  try {
    await identities();
    try {
      user.value = await api.me();
      selected.value = user.value.id;
    } catch {}
    readPageHash();
    window.addEventListener("hashchange", readPageHash);
    await refresh();
  } catch (e) {
    error.value = (e as Error).message;
  }
});
</script>

<template>
  <NConfigProvider :locale="zhCN" :theme-overrides="workspaceTheme">
    <div
      v-if="user && !switching"
      class="workspace"
      :class="{ 'nav-open': mobileNav }"
    >
      <button
        v-if="mobileNav"
        class="nav-scrim"
        aria-label="关闭导航"
        @click="mobileNav = false"
      ></button>
      <aside id="workspace-navigation" class="sidebar">
        <button
          class="brand"
          aria-label="FGAS 工作首页"
          @click="navigate('home')"
        >
          <span><strong>FGAS</strong></span>
        </button>
        <nav class="side-nav" aria-label="主导航">
          <div
            v-for="group in groups"
            :key="group.label"
            class="nav-group fantasy_guide_div_1"
          >
            <span class="nav-group-label">{{ group.label }}</span>
            <button
              v-for="item in group.items"
              :key="item.value"
              class="nav-item"
              :class="{ active: tab === item.value }"
              :aria-current="tab === item.value ? 'page' : undefined"
              @click="navigate(item.value)"
            >
              <span>{{ item.label }}</span
              ><span
                v-if="item.value === 'approvals' && approvalCount"
                class="nav-count"
                >{{ approvalCount }}</span
              >
            </button>
          </div>
        </nav>
        <div class="sidebar-foot">开发环境<span>人民币</span></div>
      </aside>
      <div class="workspace-body">
        <header class="workspace-header">
          <div class="header-title">
            <img src="/fantasyguide/touhouFantasyGuideLOGO.svg" alt="" />
            <div>
              <strong>FGAS</strong>
              <h2>资金与库存工作台</h2>
            </div>
          </div>
          <div class="header-left">
            <NButton
              class="mobile-menu"
              quaternary
              :aria-expanded="mobileNav"
              aria-controls="workspace-navigation"
              aria-label="展开导航"
              @click="mobileNav = !mobileNav"
              >☰</NButton
            ><span>{{ currentPage.title }}</span>
          </div>
          <div class="header-right">
            <NButton quaternary :loading="busy" @click="refresh">刷新</NButton
            ><button class="identity-button" @click="showIdentity = true">
              <AccountAvatar
                class="user-avatar"
                :name="user.display_name"
                :style="{ marginRight: '0' }"
              />
              <span class="identity-name"
                >{{ user.display_name
                }}<small v-if="user.display_name !== roles[user.role]">{{
                  roles[user.role]
                }}</small></span
              ><span aria-hidden="true">⌄</span>
            </button>
          </div>
        </header>
        <div class="main_background" aria-hidden="true"></div>
        <main class="workspace-main">
          <div class="page-heading">
            <div>
              <h1>{{ currentPage.title }}</h1>
            </div>
            <div
              v-if="tab === 'accounts' || tab === 'transfers'"
              class="page-actions"
            >
              <NButton v-if="tab === 'accounts'" @click="create(true)"
                >登记期初</NButton
              ><NButton type="primary" @click="create()">登记资金转移</NButton>
            </div>
            <NButton
              v-else-if="tab === 'stock'"
              type="primary"
              @click="createStock"
              >登记货物转移</NButton
            >
          </div>
          <p v-if="error" class="banner error" role="alert">{{ error }}</p>
          <div v-if="notice" class="banner success" role="status">
            <span>{{ notice }}</span
            ><button aria-label="关闭提示" @click="notice = ''">×</button>
          </div>
          <DashboardView
            v-if="tab === 'home'"
            :accounts="accounts"
            :transfers="transfers"
            :stock="stock"
            :total="total"
            :trusted="trusted"
            @navigate="navigate"
            @create="create()"
            @create-stock="createStock"
          />
          <template v-else-if="tab === 'accounts'">
            <section class="account-summary fantasy_guide_div_1">
              <div>
                <span class="metric-label">公账资金余额</span
                ><strong class="balance-value"
                  ><span>¥</span> {{ money(total) }}</strong
                >
              </div>
            </section>
            <section class="fantasy_guide_div_1 page-surface">
              <CatalogView
                mode="accounts"
                :accounts="accounts"
                :locations="locations"
                :editable="trusted"
                :members="members"
                @changed="refresh"
              />
            </section>
          </template>
          <section
            v-else-if="tab === 'transfers'"
            class="fantasy_guide_div_1 page-surface"
          >
            <TransfersView
              :key="`${user.id}:${identityEpoch}`"
              :items="transfers"
              :accounts="accounts"
              :approvals="false"
              :trusted="trusted"
              @changed="refresh"
              @notice="notice = $event"
              @create="create()"
            />
          </section>
          <section
            v-else-if="tab === 'approvals'"
            class="fantasy_guide_div_1 page-surface"
          >
            <div class="segmented-tabs" aria-label="审批类别">
              <button
                :class="{ active: approvalType === 'funds' }"
                @click="approvalType = 'funds'"
              >
                资金申请
                <span>{{
                  transfers.filter((t) => t.status === "pending").length
                }}</span></button
              ><button
                :class="{ active: approvalType === 'stock' }"
                @click="approvalType = 'stock'"
              >
                货物申请
                <span>{{
                  stock.filter(
                    (t) =>
                      t.status === "pending" ||
                      t.confirmations.some((c) => c.status === "pending"),
                  ).length
                }}</span>
              </button>
            </div>
            <TransfersView
              v-if="approvalType === 'funds'"
              :key="`${user.id}:${identityEpoch}:fund-approvals`"
              :items="transfers"
              :accounts="accounts"
              approvals
              :trusted="trusted"
              @changed="refresh"
              @notice="notice = $event"
            />
            <StockTransfersView
              v-else
              :key="`${user.id}:${identityEpoch}:stock-approvals`"
              :items="stock"
              :locations="locations"
              :funds="transfers"
              :trusted="trusted"
              :skus="skus"
              :accounts="accounts"
              approvals
              @changed="refresh"
            />
          </section>
          <section v-else class="fantasy_guide_div_1 page-surface">
            <MembersView
              v-if="tab === 'members'"
              :members="members"
              :accounts="accounts"
              :locations="locations"
              :trusted="trusted"
              @changed="refresh"
            />
            <SettlementsView
              v-else-if="tab === 'settlements'"
              :key="`${user.id}:${identityEpoch}`"
              :accounts="accounts"
              :trusted="trusted"
              @changed="refresh"
            />
            <StockTransfersView
              v-else-if="tab === 'stock'"
              :key="`${user.id}:${identityEpoch}:stock`"
              :items="stock"
              :locations="locations"
              :funds="transfers"
              :trusted="trusted"
              :skus="skus"
              :accounts="accounts"
              @changed="refresh"
            />
            <StocktakesView
              v-else-if="tab === 'stocktakes'"
              :key="`${user.id}:${identityEpoch}`"
              :accounts="accounts"
              :locations="locations"
              :skus="skus"
              :funds="transfers"
              :members="members"
              :trusted="trusted"
              @changed="refresh"
              @notice="notice = $event"
            />
            <InventoryView
              v-else-if="tab === 'inventory'"
              :key="`${user.id}:${identityEpoch}:${revision}`"
              :locations="locations"
              :skus="skus"
              :members="members"
              :revision="revision"
            />
            <SkusView
              v-else-if="tab === 'skus'"
              :key="`${user.id}:${identityEpoch}`"
              :items="skus"
              :editable="trusted"
              @changed="refresh"
            />
            <CatalogView
              v-else-if="tab === 'locations'"
              :key="`${user.id}:${identityEpoch}`"
              mode="stock-accounts"
              :accounts="accounts"
              :locations="locations"
              :editable="trusted"
              :members="members"
              @changed="refresh"
            />
            <UsersView
              v-else-if="tab === 'users' && user.role === 'admin'"
              @changed="permissionChanged"
            />
          </section>
        </main>
      </div>
      <TransferEditor
        :key="`${user.id}:${identityEpoch}`"
        :show="showTransfer"
        :accounts="accounts"
        :opening="opening"
        @close="showTransfer = false"
        @saved="
          notice = '资金转移' + $event;
          refresh();
        "
      />
      <StockTransferEditor
        ref="stockEditor"
        :key="`${user.id}:${identityEpoch}:editor`"
        hide-trigger
        :locations="locations"
        :skus="skus"
        :accounts="accounts"
        :funds="transfers"
        @saved="
          notice = '货物转移已保存';
          refresh();
        "
      />
      <NModal
        v-model:show="showIdentity"
        preset="card"
        title="开发账号"
        class="dialog compact-dialog"
      >
        <label
          >选择账号<NSelect
            v-model:value="selected"
            :options="
              users
                .filter((u) => u.active)
                .map((u) => ({
                  label: `${u.display_name}（${roles[u.role]}）`,
                  value: u.id,
                }))
            "
        /></label>
        <div class="actions">
          <NButton @click="logout">退出登录</NButton
          ><NButton type="primary" :loading="switching" @click="login"
            >切换账号</NButton
          >
        </div>
      </NModal>
    </div>
    <main v-else class="login-page">
      <div class="login-card fantasy_guide_div_1">
        <h1>FGAS</h1>
        <h2>资金与库存工作台</h2>
        <label
          >开发账号<NSelect
            v-model:value="selected"
            placeholder="选择账号"
            :options="
              users
                .filter((u) => u.active)
                .map((u) => ({
                  label: `${u.display_name}（${roles[u.role]}）`,
                  value: u.id,
                }))
            " /></label
        ><NButton
          type="primary"
          size="large"
          block
          :disabled="!selected"
          :loading="busy || switching"
          @click="login"
          >进入工作台</NButton
        >
        <p v-if="error" class="error" role="alert">{{ error }}</p>
      </div>
    </main>
  </NConfigProvider>
</template>
