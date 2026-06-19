import { CheckCircle, PlusCircle } from 'lucide-react'
import { useAddToCallPrep } from '../../hooks/useObjections'

interface Props {
  objectionId: string
}

export default function AddToCallPrepButton({ objectionId }: Props) {
  const { mutate, isPending, isSuccess } = useAddToCallPrep()

  const handleClick = () => {
    const repId = localStorage.getItem('repstream_rep_id') ?? 'REP001'
    mutate({ objectionId, repId })
  }

  if (isSuccess) {
    return (
      <button disabled className="btn-ghost w-full justify-center text-green-600 cursor-default">
        <CheckCircle className="w-4 h-4" />
        Added to Call Prep
      </button>
    )
  }

  return (
    <button onClick={handleClick} disabled={isPending} className="btn-primary w-full justify-center">
      <PlusCircle className="w-4 h-4" />
      {isPending ? 'Adding…' : 'Add to Call Prep'}
    </button>
  )
}
