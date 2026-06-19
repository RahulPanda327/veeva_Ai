import { useMutation, useQuery } from '@tanstack/react-query'
import { fetchNewWriterCandidates, generateApproachBrief } from '../api/newWriterId'
import type { ApproachBriefResponse } from '../types/newwriter'

export function useNewWriterCandidates() {
  return useQuery({
    queryKey: ['new-writers', 'candidates'],
    queryFn: fetchNewWriterCandidates,
  })
}

export function useApproachBrief() {
  return useMutation<ApproachBriefResponse, Error, string>({
    mutationFn: (hcpId: string) => generateApproachBrief(hcpId),
  })
}
