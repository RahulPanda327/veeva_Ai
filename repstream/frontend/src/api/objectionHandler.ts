import api from './client'
import type { AddToCallPrepResponse, ObjectionItem, ObjectionResponse } from '../types/objection'

export async function fetchObjections(period?: string): Promise<ObjectionItem[]> {
  const { data } = await api.get<ObjectionItem[]>('/objections/list', {
    params: period ? { period } : undefined,
  })
  return data
}

export async function fetchObjectionResponse(objectionId: string): Promise<ObjectionResponse> {
  const { data } = await api.get<ObjectionResponse>(`/objections/${objectionId}/response`)
  return data
}

export async function addToCallPrep(
  objectionId: string,
  repId: string,
): Promise<AddToCallPrepResponse> {
  const { data } = await api.post<AddToCallPrepResponse>(
    `/objections/${objectionId}/add-to-call-prep`,
    { rep_id: repId },
  )
  return data
}
