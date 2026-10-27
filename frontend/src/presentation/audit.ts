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
  automatic_approval: "自动批准",
  approve: "批准转移",
  reject: "拒绝货物转移",
  cancel: "取消货物转移",
  completion_requested: "提交完成报告",
  completed: "完成并记库存",
  approve_completion: "核实并确认完成",
  reject_completion: "退回完成报告",
  fund_reference_added: "关联资金记录",
};
