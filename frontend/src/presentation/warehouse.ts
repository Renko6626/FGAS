export const stockStatuses: Record<string, string> = {
  pending: "待审批",
  in_transit: "待完成",
  completed: "已完成",
  rejected: "已拒绝",
  cancelled: "已取消",
  invalidated: "已失效",
};
export const today = () => new Date().toLocaleDateString("sv-SE");
