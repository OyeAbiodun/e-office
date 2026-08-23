import { Link } from '@tanstack/react-router'
import { CalendarClock, MapPin, Users } from 'lucide-react'
import { motion } from 'framer-motion'

import type { Meeting } from '@/features/meetings/api'

export function MeetingCard({
  meeting,
  index = 0,
}: {
  meeting: Meeting
  index?: number
}) {
  const start = new Date(meeting.start_datetime)
  return (
    <motion.article
      animate={{ opacity: 1, y: 0 }}
      className="group rounded-2xl border bg-card p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
      initial={{ opacity: 0, y: 8 }}
      transition={{ delay: index * 0.04 }}
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <span className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium capitalize text-primary">
            {meeting.status.replace('_', ' ')}
          </span>
          <Link
            className="mt-3 block text-lg font-semibold tracking-tight group-hover:text-primary"
            params={{ meetingId: meeting.id }}
            to="/meetings/$meetingId"
          >
            {meeting.title}
          </Link>
        </div>
        <div className="rounded-xl bg-muted px-3 py-2 text-center">
          <p className="text-xs font-medium uppercase text-muted-foreground">
            {start.toLocaleDateString([], { month: 'short' })}
          </p>
          <p className="text-xl font-semibold">{start.getDate()}</p>
        </div>
      </div>
      <p className="mt-3 line-clamp-2 text-sm leading-6 text-muted-foreground">
        {meeting.description || 'No description added.'}
      </p>
      <div className="mt-5 flex flex-wrap gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <CalendarClock className="size-4" />
          {start.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
        <span className="flex items-center gap-1.5 capitalize">
          <MapPin className="size-4" />
          {meeting.location_type}
        </span>
        <span className="flex items-center gap-1.5">
          <Users className="size-4" />
          Collaboration ready
        </span>
      </div>
    </motion.article>
  )
}
