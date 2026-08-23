import {
  Building2,
  CalendarDays,
  Clock3,
  DoorOpen,
  MailPlus,
  Sparkles,
  SunMedium,
  Users,
  Workflow,
} from 'lucide-react'
import type { ComponentType } from 'react'

const registry: Record<string, ComponentType<{ className?: string }>> = {
  workspaces: Building2,
  teams: Workflow,
  members: Users,
  invitations: MailPlus,
  today_schedule: CalendarDays,
  upcoming_events: Clock3,
  availability: Clock3,
  resource_status: DoorOpen,
  holiday_summary: SunMedium,
  quick_schedule: Sparkles,
}

export function WidgetIcon({ id }: { id: string }) {
  const Icon = registry[id] ?? Building2
  return <Icon aria-hidden="true" className="size-4.5" />
}
