import { apiRawRequest, apiRequest } from '@/features/auth/api'

export interface Meeting {
  id: string
  organization_id: string
  workspace_id: string
  calendar_event_id: string | null
  meeting_template_id: string | null
  title: string
  description: string | null
  agenda_text: string | null
  location: string | null
  recurrence: Record<string, unknown> | null
  meeting_type: string
  location_type: string
  meeting_url: string | null
  room_id: string | null
  organizer_id: string
  start_datetime: string
  end_datetime: string
  timezone: string
  status: string
  visibility: string
  created_at: string
  updated_at: string
}

export interface MeetingDetail extends Meeting {
  attendees: Array<Record<string, string | null>>
  agenda: Array<Record<string, string | number | null>>
  decisions: Array<Record<string, string | null>>
  action_items: Array<Record<string, string | null>>
  notes: Array<Record<string, string | null>>
  artifacts: Array<Record<string, string | number | null>>
  recordings: Array<Record<string, string | number | null>>
  attendance_events: Array<Record<string, string | null>>
  presenter_controls: Array<Record<string, string | null>>
  follow_ups: Array<Record<string, string | null>>
}

export interface MeetingDashboard {
  today: Meeting[]
  upcoming: Meeting[]
  recent: Meeting[]
  pending_rsvps: number
  my_action_items: Array<Record<string, string | null>>
}

export interface MeetingAnalytics {
  attendee_count: number
  joined_count: number
  attendance_rate: number
  average_minutes_attended: number
  agenda_items: number
  decisions: number
  action_items: number
  completed_actions: number
  follow_ups_pending: number
}

export const meetingApi = {
  list: (query = '') => apiRequest<Meeting[]>(`/meetings${query}`, {}, true),
  dashboard: () =>
    apiRequest<MeetingDashboard>('/meetings/dashboard', {}, true),
  get: (id: string) => apiRequest<MeetingDetail>(`/meetings/${id}`, {}, true),
  create: (body: object) =>
    apiRequest<Meeting>(
      '/meetings',
      {
        method: 'POST',
        body: JSON.stringify(body),
      },
      true,
    ),
  update: (id: string, body: object) =>
    apiRequest<Meeting>(
      `/meetings/${id}`,
      {
        method: 'PATCH',
        body: JSON.stringify(body),
      },
      true,
    ),
  transition: (id: string, status: string) =>
    apiRequest<Meeting>(
      `/meetings/${id}/transition`,
      {
        method: 'POST',
        body: JSON.stringify({ status }),
      },
      true,
    ),
  duplicate: (id: string) =>
    apiRequest<Meeting>(`/meetings/${id}/duplicate`, { method: 'POST' }, true),
  reschedule: (id: string, body: object) =>
    apiRequest<Meeting>(
      `/meetings/${id}/reschedule`,
      {
        method: 'POST',
        body: JSON.stringify(body),
      },
      true,
    ),
  rsvp: (id: string, status: string) =>
    apiRequest(
      `/meetings/${id}/rsvp`,
      {
        method: 'PUT',
        body: JSON.stringify({ status }),
      },
      true,
    ),
  add: (id: string, collection: string, body: object) =>
    apiRequest(
      `/meetings/${id}/${collection}`,
      {
        method: 'POST',
        body: JSON.stringify(body),
      },
      true,
    ),
  history: (id: string) =>
    apiRequest<Array<Record<string, unknown>>>(
      `/meetings/${id}/history`,
      {},
      true,
    ),
  analytics: (id: string) =>
    apiRequest<MeetingAnalytics>(`/meetings/${id}/analytics`, {}, true),
  addArtifact: (id: string, body: object) =>
    apiRequest(
      `/meetings/${id}/artifacts`,
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  uploadArtifact: async (id: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    const response = await apiRawRequest(`/meetings/${id}/artifacts/upload`, {
      method: 'POST',
      body: form,
    })
    return response.json()
  },
  addRecording: (id: string, body: object) =>
    apiRequest(
      `/meetings/${id}/recordings`,
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  attendance: (id: string, body: object) =>
    apiRequest(
      `/meetings/${id}/attendance`,
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  presenterControl: (id: string, body: object) =>
    apiRequest(
      `/meetings/${id}/presenter-controls`,
      { method: 'PUT', body: JSON.stringify(body) },
      true,
    ),
  followUp: (id: string, body: object) =>
    apiRequest(
      `/meetings/${id}/follow-ups`,
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  templates: () =>
    apiRequest<Array<Record<string, unknown>>>('/meeting-templates', {}, true),
  createTemplate: (body: object) =>
    apiRequest(
      '/meeting-templates',
      {
        method: 'POST',
        body: JSON.stringify(body),
      },
      true,
    ),
}
