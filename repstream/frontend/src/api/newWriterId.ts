import api from './client'
import type { ApproachBriefResponse, NewWriterCandidate } from '../types/newwriter'

export async function fetchNewWriterCandidates(): Promise<NewWriterCandidate[]> {
  const { data } = await api.get<NewWriterCandidate[]>('/new-writers/candidates')
  return data
}

export async function generateApproachBrief(hcpId: string): Promise<ApproachBriefResponse> {
  const { data } = await api.post<ApproachBriefResponse>(`/new-writers/${hcpId}/approach-brief`)
  return data
}
