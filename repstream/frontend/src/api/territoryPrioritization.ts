import api from './client'
import type { HCPInsightResponse, HCPRankedItem, TerritorySummary } from '../types/hcp'

export async function fetchTerritorySummary(): Promise<TerritorySummary> {
  const { data } = await api.get<TerritorySummary>('/territory/summary')
  return data
}

export async function fetchHCPList(): Promise<HCPRankedItem[]> {
  const { data } = await api.get<HCPRankedItem[]>('/territory/hcp-list')
  return data
}

export async function regenerateHCPInsight(hcpId: string): Promise<HCPInsightResponse> {
  const { data } = await api.get<HCPInsightResponse>(`/territory/hcp/${hcpId}/insight`)
  return data
}
