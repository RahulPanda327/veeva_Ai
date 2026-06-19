import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchHCPList, fetchTerritorySummary, regenerateHCPInsight } from '../api/territoryPrioritization'

export function useTerritorySummary() {
  return useQuery({
    queryKey: ['territory', 'summary'],
    queryFn: fetchTerritorySummary,
  })
}

export function useHCPList() {
  return useQuery({
    queryKey: ['territory', 'hcp-list'],
    queryFn: fetchHCPList,
  })
}

export function useRegenerateInsight() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (hcpId: string) => regenerateHCPInsight(hcpId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['territory', 'hcp-list'] })
    },
  })
}
