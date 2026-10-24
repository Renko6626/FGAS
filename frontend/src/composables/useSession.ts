import { onBeforeUnmount, onMounted, ref, type Ref } from "vue";
import { authApi, type AuthMode, type User } from "../api/auth";

const ssoErrors: Record<string, string> = {
  invalid_state: "登录状态已失效，请重新登录",
  access_denied: "登录已取消或未获授权",
  idp_unavailable: "身份服务暂时不可用，请稍后重试",
  user_disabled: "账号已停用，请联系管理员",
  login_failed: "登录失败，请重试",
};

interface SessionOptions {
  busy: Ref<boolean>;
  error: Ref<string>;
  notice: Ref<string>;
  clearWorkspace: () => void;
  refresh: () => Promise<void>;
  closeTransfer: () => void;
  onLogin: () => void;
  onExpired: () => void;
  onPermissionsResolved: () => void;
}

export function useSession(options: SessionOptions) {
  const { busy, error, notice } = options;
  const user = ref<User | null>(null);
  const mode = ref<AuthMode | null>(null);
  const users = ref<User[]>([]);
  const selected = ref<string | null>(null);
  const switching = ref(false);
  const identityEpoch = ref(0);

  function clearUser() {
    user.value = null;
    options.clearWorkspace();
  }

  function readSsoError() {
    const url = new URL(window.location.href);
    const code = url.searchParams.get("sso_error");
    if (!code) return;
    error.value = ssoErrors[code] || ssoErrors.login_failed!;
    url.searchParams.delete("sso_error");
    window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
  }

  function sessionExpired() {
    if (!user.value) return;
    identityEpoch.value++;
    selected.value = null;
    options.closeTransfer();
    options.onExpired();
    clearUser();
    error.value = "登录状态已失效，请重新登录";
  }

  async function identities() {
    if (mode.value === "development") users.value = await authApi.users();
  }

  async function initialize() {
    readSsoError();
    mode.value = (await authApi.authConfig()).mode;
    if (mode.value === "development") await identities();
    try {
      user.value = await authApi.me();
      selected.value = user.value.id;
    } catch {
      user.value = null;
    }
  }

  async function login() {
    if (mode.value === "casdoor") {
      window.location.assign("/api/auth/casdoor/login");
      return;
    }
    if (!selected.value || switching.value) return;
    switching.value = true;
    busy.value = true;
    error.value = "";
    try {
      options.closeTransfer();
      identityEpoch.value++;
      await authApi.login(selected.value);
      user.value = await authApi.me();
      identityEpoch.value++;
      options.onLogin();
      notice.value = "开发账号已切换";
      await options.refresh();
    } catch (e) {
      clearUser();
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
      options.closeTransfer();
      identityEpoch.value++;
      await authApi.logout();
      clearUser();
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
      user.value = await authApi.me();
      options.onPermissionsResolved();
      await options.refresh();
    } catch (e) {
      user.value = null;
      error.value = (e as Error).message;
    }
  }

  onMounted(() => window.addEventListener("fgas-session-expired", sessionExpired));
  onBeforeUnmount(() => window.removeEventListener("fgas-session-expired", sessionExpired));

  return { user, mode, users, selected, switching, identityEpoch, initialize, login, logout, permissionChanged };
}
