type StatusPillProps = {
  tone: 'neutral' | 'success' | 'warning' | 'danger'
  label: string
}

const toneClasses: Record<StatusPillProps['tone'], string> = {
  neutral: 'bg-ivory-deep text-navy-muted',
  success: 'bg-sage-soft text-success',
  warning: 'bg-ivory-deep text-navy-muted',
  danger: 'bg-red-50 text-danger',
}

export function StatusPill({ tone, label }: StatusPillProps) {
  return (
    <span
      className={`inline-flex items-center rounded-md px-2.5 py-1 text-xs font-semibold tracking-wide ${toneClasses[tone]}`}
    >
      {label}
    </span>
  )
}
