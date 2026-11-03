import { query, request, requestForm } from "./client";

export type AttachmentTarget = "transfer" | "stock_transfer" | "sku" | "fund_account" | "stock_account";

export interface Attachment {
  id: string;
  target_kind: AttachmentTarget;
  target_code: string | null;
  target_name: string | null;
  caption: string;
  content_type: string;
  byte_size: number;
  width: number | null;
  height: number | null;
  original_filename: string;
  uploaded_by_id: string;
  uploaded_by_name: string | null;
  created_at: string;
  file_url: string;
}

export interface AdminAttachmentPage {
  items: Attachment[];
  total: number;
  total_bytes: number;
  page: number;
  limit: number;
}

export interface AttachmentUpload {
  blob: Blob;
  filename: string;
  caption?: string;
  width?: number;
  height?: number;
}

export const attachmentsApi = {
  list: (targetKind: AttachmentTarget, targetCode: string) =>
    request<Attachment[]>(`/attachments${query({ target_kind: targetKind, target_code: targetCode })}`),
  upload: (targetKind: AttachmentTarget, targetCode: string, input: AttachmentUpload) => {
    const form = new FormData();
    form.set("file", input.blob, input.filename);
    form.set("target_kind", targetKind);
    form.set("target_code", targetCode);
    if (input.caption) form.set("caption", input.caption);
    if (input.width) form.set("width", String(input.width));
    if (input.height) form.set("height", String(input.height));
    return requestForm<Attachment>("/attachments", form);
  },
  remove: (id: string) => request<{ ok: boolean }>(`/attachments/${id}`, "DELETE"),
  adminList: (params: { kind?: string; q?: string; page?: number; limit?: number }) =>
    request<AdminAttachmentPage>(`/admin/attachments${query(params)}`),
};
