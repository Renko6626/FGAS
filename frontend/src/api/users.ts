import { request } from "./client";
import type { User } from "./auth";

export interface AdminUser extends User {
  sso_subject: string | null;
  sso_username: string | null;
  email: string | null;
  last_login_at: string | null;
  created_at: string;
  source: "casdoor" | "development";
}
export interface ForceLogoutResult {
  ok: boolean;
  revoked: number;
  self: boolean;
}

export const usersApi = {
  adminUsers: () => request<AdminUser[]>("/users"),
  saveUser: (user: Pick<AdminUser, "id" | "role" | "active">) =>
    request<AdminUser>("/users/" + user.id, "PATCH", {
      role: user.role,
      active: user.active,
    }),
  forceLogout: (id: string) =>
    request<ForceLogoutResult>("/users/" + id + "/logout", "POST"),
};
