import { request } from "./client";

export type AuthMode = "development" | "casdoor";
export interface AuthConfig {
  mode: AuthMode;
  web_agent_prototype?: boolean;
}
export interface User {
  id: string;
  display_name: string;
  role: "admin" | "trusted" | "untrusted";
  active: boolean;
}

export const authApi = {
  authConfig: () => request<AuthConfig>("/auth/config"),
  users: () => request<User[]>("/auth/users"),
  me: () => request<User>("/auth/me"),
  login: (id: string) => request<User>("/auth/login", "POST", { user_id: id }),
  logout: () => request("/auth/logout", "POST"),
};
