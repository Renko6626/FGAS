export function approvalLabel(mode: string | null | undefined) {
  const labels: Record<string, string> = {
    automatic: "自动批准",
    manual: "人工批准",
    agent_direct: "Agent 直接执行",
    agent_approval: "Agent 批准",
  };
  return labels[mode || ""] || "待处理";
}

export const actionNames: Record<string, string> = {
  submitted: "提交",
  posted: "批准并过账",
  rejected: "拒绝",
};
