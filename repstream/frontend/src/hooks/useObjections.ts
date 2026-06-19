import { useMutation, useQuery } from '@tanstack/react-query'
import { addToCallPrep, fetchObjectionResponse, fetchObjections } from '../api/objectionHandler'

export function useObjections(period?: string) {
  return useQuery({
    queryKey: ['objections', 'list', period],
    queryFn: () => fetchObjections(period),
  })
}

export function useObjectionResponse(objectionId: string) {
  return useQuery({
    queryKey: ['objections', 'response', objectionId],
    queryFn: () => fetchObjectionResponse(objectionId),
    enabled: !!objectionId,
  })
}

export function useAddToCallPrep() {
  return useMutation({
    mutationFn: ({ objectionId, repId }: { objectionId: string; repId: string }) =>
      addToCallPrep(objectionId, repId),
  })
}
