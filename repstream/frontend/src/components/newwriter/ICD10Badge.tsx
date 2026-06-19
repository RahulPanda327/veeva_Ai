interface Props {
  codes: string[]
}

export default function ICD10Badge({ codes }: Props) {
  if (codes.length === 0) return null

  return (
    <div className="flex flex-wrap gap-1">
      {codes.map((code) => (
        <span key={code} className="badge-ai-matched">
          <span className="sr-only">ICD-10: </span>
          {code}
        </span>
      ))}
    </div>
  )
}
