import { apiClient } from "@/services/api";

export interface MCPSettings {
  enabled: boolean;
  public_base_url: string;
  mcp_url: string;
}

export interface IntegrationToken {
  id: number;
  name: string;
  scopes: string[];
  created_at: string;
  expires_at: string;
  revoked_at: string | null;
}

export interface TokenInput {
  name: string;
  scopes: string[];
  expires_in_days: number;
}

export async function loadMCPSettings(): Promise<MCPSettings> {
  return (await apiClient.get<MCPSettings>("/console/mcp")).data;
}

export async function saveMCPSettings(
  settings: Pick<MCPSettings, "enabled" | "public_base_url">,
): Promise<MCPSettings> {
  return (await apiClient.put<MCPSettings>("/console/mcp", settings)).data;
}

export async function listIntegrationTokens(): Promise<IntegrationToken[]> {
  return (await apiClient.get<IntegrationToken[]>("/integration-tokens")).data;
}

export async function createIntegrationToken(input: TokenInput): Promise<IntegrationToken & { token: string }> {
  return (await apiClient.post<IntegrationToken & { token: string }>("/integration-tokens", input)).data;
}

export async function revokeIntegrationToken(id: number): Promise<void> {
  await apiClient.delete(`/integration-tokens/${id}`);
}
