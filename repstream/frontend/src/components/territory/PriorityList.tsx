import type { HCPRankedItem } from '../../types/hcp'
import HCPCard from './HCPCard'

interface Props {
  hcps: HCPRankedItem[]
  filter?: 'HIGH' | 'MEDIUM' | 'LOW' | 'ALL'
}

export default function PriorityList({ hcps, filter = 'ALL' }: Props) {
  const filtered = filter === 'ALL' ? hcps : hcps.filter((h) => h.priority_tier === filter)

  if (filtered.length === 0) {
    return (
      <div className="text-center py-16 text-slate-400">
        <p className="text-sm">No HCPs found for this filter.</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {filtered.map((hcp) => (
        <HCPCard key={hcp.hcp_id} hcp={hcp} />
      ))}
    </div>
  )
}
