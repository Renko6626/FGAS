import { request } from './client';

export interface Handbook {
  title: string;
  content: string;
  updated_by_id: string | null;
  updated_by_name: string | null;
  updated_at: string | null;
}

export const handbookApi = {
  read: () => request<Handbook>('/handbook'),
  save: (data: Pick<Handbook, 'title' | 'content'>) => request<Handbook>('/handbook', 'PUT', data),
};
