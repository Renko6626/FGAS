import { request } from "./client";

export interface Member {
  code: string;
  name: string;
  note: string;
}

export const membersApi = {
  list: () => request<Member[]>("/members"),
  create: (data: { name: string; note: string }) =>
    request<Member>("/members", "POST", data),
  update: (id: string, data: { name: string; note: string }) =>
    request<Member>("/members/" + id, "PATCH", data),
};
