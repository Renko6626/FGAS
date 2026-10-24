export interface AgentSource {
  submitted_credential_id?: string | null;
  submitted_credential_name?: string | null;
}
export interface AgentAudit {
  actor_id: string;
  action: string;
  agent_credential_id?: string | null;
  agent_credential_name?: string | null;
  created_at: string;
}

export function approvalLabel(mode: string | null | undefined) {
  const labels: Record<string, string> = {
    automatic: "自动批准",
    manual: "人工批准",
    agent_direct: "Agent 直接执行",
    agent_approval: "Agent 批准",
  };
  return labels[mode || ""] || "待处理";
}
