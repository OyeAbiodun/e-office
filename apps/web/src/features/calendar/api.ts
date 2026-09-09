import { apiRawRequest, apiRequest } from '@/features/auth/api'

export interface Calendar {
  id: string
  name: string
  color: string
  type: 'personal' | 'team' | 'workspace' | 'organization' | 'resource'
  timezone: string
  is_default: boolean
}

export interface CalendarEvent {
  id: string
  calendar_id: string
  meeting_id: string | null
  title: string
  start_datetime: string
  end_datetime: string
  status: string
  description: string | null
  timezone: string
  all_day: boolean
  recurrence_rule_id: string | null
  recurrence_parent_id: string | null
  original_start_datetime: string | null
  category_id: string | null
}

export interface Resource {
  id: string
  name: string
  category: string
  capacity: number
  location: string | null
  status: string
}

export interface Holiday {
  id: string
  name: string
  date: string
  recurring: boolean
}

export interface EventCategory {
  id: string
  name: string
  color: string
}

export interface Reservation {
  id: string
  resource_id: string
  calendar_event_id: string
  start_datetime: string
  end_datetime: string
  cancelled_at: string | null
}

export interface AvailabilityRule {
  id: string
  calendar_id: string
  weekday: number
  start_time: string
  end_time: string
  availability_type: string
  priority: number
}

export interface CalendarShare {
  id: string
  calendar_id: string
  user_id: string
  permission: 'read' | 'write' | 'manage'
}

export interface TimeSlot {
  start_datetime: string
  end_datetime: string
}

export const calendarApi = {
  calendars: () => apiRequest<Calendar[]>('/calendars', {}, true),
  events: (calendarId: string) =>
    apiRequest<CalendarEvent[]>(`/calendars/${calendarId}/events`, {}, true),
  createEvent: (calendarId: string, body: object) =>
    apiRequest<CalendarEvent>(
      `/calendars/${calendarId}/events`,
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  updateEvent: (eventId: string, body: object) =>
    apiRequest<CalendarEvent>(
      `/events/${eventId}`,
      { method: 'PATCH', body: JSON.stringify(body) },
      true,
    ),
  deleteEvent: (eventId: string) =>
    apiRequest(`/events/${eventId}`, { method: 'DELETE' }, true),
  setRecurrence: (eventId: string, body: object) =>
    apiRequest(
      `/events/${eventId}/recurrence`,
      { method: 'PUT', body: JSON.stringify(body) },
      true,
    ),
  createException: (eventId: string, body: object) =>
    apiRequest<CalendarEvent>(
      `/events/${eventId}/exceptions`,
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  categories: () => apiRequest<EventCategory[]>('/event-categories', {}, true),
  createCategory: (body: object) =>
    apiRequest<EventCategory>(
      '/event-categories',
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  availability: (calendarId: string) =>
    apiRequest<AvailabilityRule[]>(
      `/calendars/${calendarId}/availability`,
      {},
      true,
    ),
  createAvailability: (calendarId: string, body: object) =>
    apiRequest<AvailabilityRule>(
      `/calendars/${calendarId}/availability`,
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  deleteAvailability: (ruleId: string) =>
    apiRequest(`/availability/${ruleId}`, { method: 'DELETE' }, true),
  suggestions: (body: object) =>
    apiRequest<TimeSlot[]>(
      '/scheduling/suggestions',
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  shares: (calendarId: string) =>
    apiRequest<CalendarShare[]>(`/calendars/${calendarId}/shares`, {}, true),
  share: (calendarId: string, body: object) =>
    apiRequest<CalendarShare>(
      `/calendars/${calendarId}/shares`,
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  revokeShare: (calendarId: string, shareId: string) =>
    apiRequest(
      `/calendars/${calendarId}/shares/${shareId}`,
      { method: 'DELETE' },
      true,
    ),
  resources: () => apiRequest<Resource[]>('/resources', {}, true),
  createResource: (body: object) =>
    apiRequest<Resource>(
      '/resources',
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  reserve: (body: object) =>
    apiRequest<Reservation>(
      '/reservations',
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  holidays: () => apiRequest<Holiday[]>('/holidays', {}, true),
  createHoliday: (body: { name: string; date: string; recurring: boolean }) =>
    apiRequest<Holiday>(
      '/holidays',
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  updateHoliday: (
    id: string,
    body: { name: string; date: string; recurring: boolean },
  ) =>
    apiRequest<Holiday>(
      `/holidays/${id}`,
      { method: 'PUT', body: JSON.stringify(body) },
      true,
    ),
  deleteHoliday: (id: string) =>
    apiRequest(`/holidays/${id}`, { method: 'DELETE' }, true),
  importIcs: async (calendarId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    const response = await apiRawRequest(
      `/calendars/${calendarId}/import.ics`,
      { method: 'POST', body: form },
    )
    const payload = (await response.json()) as {
      data: CalendarEvent[]
    }
    return payload.data
  },
  exportIcs: async (calendarId: string) => {
    const response = await apiRawRequest(`/calendars/${calendarId}/export.ics`)
    return response.blob()
  },
}
