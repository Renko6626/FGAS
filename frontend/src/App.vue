<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from "vue";
import { NButton, NSelect, NModal, NConfigProvider, zhCN } from "naive-ui";
import { workspaceTheme } from "./theme";
import DashboardView from "./views/DashboardView.vue";
import { money } from "./presentation/funds";
import { useSession } from "./composables/useSession";
import { useWorkspace } from "./composables/useWorkspace";
import StocktakesView from "./views/StocktakesView.vue";
import CatalogView from "./views/CatalogView.vue";
import TransfersView from "./views/TransfersView.vue";
import SettlementsView from "./views/SettlementsView.vue";
import MembersView from "./views/MembersView.vue";
import UsersView from "./views/UsersView.vue";
import AgentConnectionsView from "./views/AgentConnectionsView.vue";
import SkusView from "./views/SkusView.vue";
import InventoryView from "./views/InventoryView.vue";
import StockTransfersView from "./views/StockTransfersView.vue";
import StockTransferEditor from "./components/StockTransferEditor.vue";
import TransferEditor from "./components/TransferEditor.vue";
import AccountAvatar from "./components/AccountAvatar.vue";
import { stocktakesEnabled } from "./features";
const tab = ref("home");
const targetCode = ref("");
const targetAccountCode = ref("");
const error = ref("");
const notice = ref("");
const busy = ref(false);
const showTransfer = ref(false);
const opening = ref(false);
const mobileNav = ref(false);
const showIdentity = ref(false);
const approvalType = ref("funds");
const {
  user, mode, users, selected, switching, identityEpoch,
  initialize, login, logout, permissionChanged,
} = useSession({
  busy,
  error,
  notice,
  clearWorkspace: () => workspace.clear(),
  refresh: () => workspace.refresh(),
  closeTransfer: () => { showTransfer.value = false; },
  onLogin: () => {
    readPageHash();
    showIdentity.value = false;
    mobileNav.value = false;
  },
  onExpired: () => { showIdentity.value = false; },
  onPermissionsResolved: () => {
    if (!nav.value.some((n) => n.value === tab.value)) navigate("home");
  },
});
const workspace = useWorkspace(user, identityEpoch, busy, error);
const { accounts, locations, dashboard, counts, total, skus, members, revision, refresh } = workspace;
const trusted = computed(
  () => user.value?.role === "trusted" || user.value?.role === "admin",
);
const roles = { admin: "管理员", trusted: "受信任用户", untrusted: "普通用户" };
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
  agentConnections: { title: "Agent 连接" },
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
  ...(stocktakesEnabled ? [{
    label: "盘点",
    items: [{ value: "stocktakes", label: "阶段盘点" }],
  }] : []),
  {
    label: "基础资料",
    items: [
      { value: "members", label: "成员与联系人" },
      { value: "agentConnections", label: "Agent 连接" },
      ...(user.value?.role === "admin"
        ? [{ value: "users", label: "用户权限" }]
        : []),
    ],
  },
]);
const nav = computed(() => groups.value.flatMap((group) => group.items));
const currentPage = computed(() => pages[tab.value] || pages.home!);
const approvalCount = computed(
  () => counts.value.pendingFunds + counts.value.pendingStock,
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
  const [value = "home", search = ""] = window.location.hash.slice(1).split("?");
  const params = new URLSearchParams(search);
  targetCode.value = params.get("code") || "";
  targetAccountCode.value = params.get("account_code") || "";
  tab.value = nav.value.some((item) => item.value === value) ? value : "home";
  mobileNav.value = false;
}
onBeforeUnmount(() => {
  window.removeEventListener("hashchange", readPageHash);
});
function createStock() {
  stockEditor.value?.open();
}
function create(isOpening = false) {
  opening.value = isOpening;
  showTransfer.value = true;
}
onMounted(async () => {
  try {
    await initialize();
    readPageHash();
    window.addEventListener("hashchange", readPageHash);
    if (user.value) await refresh();
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
        <div class="sidebar-foot">
          {{ mode === "casdoor" ? "正式环境" : "开发环境" }}<span>人民币</span>
        </div>
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
            <div v-if="tab === 'home'" class="page-actions">
              <NButton @click="createStock">登记货物</NButton>
              <NButton type="primary" @click="create()">登记资金</NButton>
            </div>
            <div
              v-else-if="tab === 'accounts' || tab === 'transfers'"
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
            :data="dashboard"
            :accounts="accounts"
            :loading="busy"
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
              :target-code="targetCode"
              :key="`${user.id}:${identityEpoch}`"
              :accounts="accounts"
              :approvals="false"
              :trusted="trusted"
              :revision="revision"
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
                <span>{{ counts.pendingFunds }}</span></button
              ><button
                :class="{ active: approvalType === 'stock' }"
                @click="approvalType = 'stock'"
              >
                货物申请
                <span>{{ counts.pendingStock }}</span>
              </button>
            </div>
            <TransfersView
              v-if="approvalType === 'funds'"
              :key="`${user.id}:${identityEpoch}:fund-approvals`"
              :accounts="accounts"
              approvals
              :trusted="trusted"
              :revision="revision"
              @changed="refresh"
              @notice="notice = $event"
            />
            <StockTransfersView
              v-else
              :key="`${user.id}:${identityEpoch}:stock-approvals`"
              :locations="locations"
              :trusted="trusted"
              :skus="skus"
              :accounts="accounts"
              :revision="revision"
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
              :target-account-code="targetAccountCode"
              v-else-if="tab === 'settlements'"
              :key="`${user.id}:${identityEpoch}`"
              :accounts="accounts"
              :trusted="trusted"
              @changed="refresh"
            />
            <StockTransfersView
              :target-code="targetCode"
              v-else-if="tab === 'stock'"
              :key="`${user.id}:${identityEpoch}:stock`"
              :locations="locations"
              :trusted="trusted"
              :skus="skus"
              :accounts="accounts"
              :revision="revision"
              @changed="refresh"
            />
            <StocktakesView
              v-else-if="stocktakesEnabled && tab === 'stocktakes'"
              :key="`${user.id}:${identityEpoch}`"
              :accounts="accounts"
              :locations="locations"
              :skus="skus"
              :members="members"
              :trusted="trusted"
              @changed="refresh"
              @notice="notice = $event"
            />
            <InventoryView
              v-else-if="tab === 'inventory'"
              :key="`${user.id}:${identityEpoch}`"
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
            <AgentConnectionsView
              v-else-if="tab === 'agentConnections'"
              :key="`${user.id}:${identityEpoch}`"
              :user="user"
            />
            <UsersView
              v-else-if="tab === 'users' && user.role === 'admin'"
              :current-user-id="user.id"
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
        @saved="
          notice = '货物转移已保存';
          refresh();
        "
      />
      <NModal
        v-model:show="showIdentity"
        preset="card"
        :title="mode === 'casdoor' ? '当前账号' : '开发账号'"
        class="dialog compact-dialog"
      >
        <template v-if="mode === 'development'">
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
        </template>
        <p v-else>
          <strong>{{ user.display_name }}</strong>
          <small>{{ roles[user.role] }}</small>
        </p>
        <p v-if="mode === 'casdoor'" class="muted">
          通过 Casdoor 登录。退出 FGAS 不会退出 Casdoor。
        </p>
        <div class="actions">
          <NButton @click="logout">退出登录</NButton
          ><NButton
            v-if="mode === 'development'"
            type="primary"
            :loading="switching"
            @click="login"
            >切换账号</NButton
          >
        </div>
      </NModal>
    </div>
    <main v-else class="login-page">
      <div class="login-card fantasy_guide_div_1">
        <h1>FGAS</h1>
        <h2>资金与库存工作台</h2>
        <template v-if="mode === 'development'">
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
        </template>
        <template v-else-if="mode === 'casdoor'">
          <NButton
            tag="a"
            href="/api/auth/casdoor/login"
            type="primary"
            size="large"
            block
            >使用 Casdoor 登录</NButton
          >
          <p class="muted">首次登录会自动创建普通用户，角色由管理员授予。</p>
        </template>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
      </div>
    </main>
  </NConfigProvider>
</template>
