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

export interface FundAuditEvent extends AgentAudit {
  detail: string;
}
