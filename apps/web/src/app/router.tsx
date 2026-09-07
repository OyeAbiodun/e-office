import {
  createRootRoute,
  createRoute,
  createRouter,
} from '@tanstack/react-router'
import { lazy } from 'react'

import { AppShell } from '@/components/app-shell'
import { RouteOutlet } from '@/components/route-outlet'
import { ProtectedRoute, PublicRoute } from '@/features/auth/route-guards'

const AuthLayout = lazy(() =>
  import('@/features/auth/auth-layout').then((module) => ({
    default: module.AuthLayout,
  })),
)
const ForgotPasswordPage = lazy(() =>
  import('@/features/auth/forgot-password-page').then((module) => ({
    default: module.ForgotPasswordPage,
  })),
)
const LoginPage = lazy(() =>
  import('@/features/auth/login-page').then((module) => ({
    default: module.LoginPage,
  })),
)
const ChangePasswordPage = lazy(() =>
  import('@/features/auth/change-password-page').then((module) => ({
    default: module.ChangePasswordPage,
  })),
)
const RegisterPage = lazy(() =>
  import('@/features/auth/register-page').then((module) => ({
    default: module.RegisterPage,
  })),
)
const ResetPasswordPage = lazy(() =>
  import('@/features/auth/reset-password-page').then((module) => ({
    default: module.ResetPasswordPage,
  })),
)
const SessionsPage = lazy(() =>
  import('@/features/auth/sessions-page').then((module) => ({
    default: module.SessionsPage,
  })),
)
const StatusPages = lazy(() =>
  import('@/features/auth/status-pages').then((module) => ({
    default: module.UnauthorizedPage,
  })),
)
const ForbiddenPage = lazy(() =>
  import('@/features/auth/status-pages').then((module) => ({
    default: module.ForbiddenPage,
  })),
)
const VerifyEmailPage = lazy(() =>
  import('@/features/auth/verify-email-page').then((module) => ({
    default: module.VerifyEmailPage,
  })),
)
const CalendarPage = lazy(() =>
  import('@/features/calendar/calendar-page').then((module) => ({
    default: module.CalendarPage,
  })),
)
const ChatHomePage = lazy(() =>
  import('@/features/chat/chat-home-page').then((module) => ({
    default: module.ChatHomePage,
  })),
)
const ConversationPage = lazy(() =>
  import('@/features/chat/conversation-page').then((module) => ({
    default: module.ConversationPage,
  })),
)
const DashboardPage = lazy(() =>
  import('@/features/dashboard/dashboard-page').then((module) => ({
    default: module.DashboardPage,
  })),
)
const HelpCenterPage = lazy(() =>
  import('@/features/help/help-center-page').then((module) => ({
    default: module.HelpCenterPage,
  })),
)
const NotificationCenterPage = lazy(() =>
  import('@/features/notifications/notification-center-page').then(
    (module) => ({
      default: module.NotificationCenterPage,
    }),
  ),
)
const MailPage = lazy(() =>
  import('@/features/mail/mail-page').then((module) => ({
    default: module.MailPage,
  })),
)
const AcceptInvitationPage = lazy(() =>
  import('@/features/invitations/accept-invitation-page').then((module) => ({
    default: module.AcceptInvitationPage,
  })),
)
const InvitationsPage = lazy(() =>
  import('@/features/invitations/invitations-page').then((module) => ({
    default: module.InvitationsPage,
  })),
)
const CreateMeetingPage = lazy(() =>
  import('@/features/meetings/create-meeting-page').then((module) => ({
    default: module.CreateMeetingPage,
  })),
)
const EditMeetingPage = lazy(() =>
  import('@/features/meetings/edit-meeting-page').then((module) => ({
    default: module.EditMeetingPage,
  })),
)
const MeetingDetailPage = lazy(() =>
  import('@/features/meetings/meeting-detail-page').then((module) => ({
    default: module.MeetingDetailPage,
  })),
)
const MeetingTemplatesPage = lazy(() =>
  import('@/features/meetings/meeting-templates-page').then((module) => ({
    default: module.MeetingTemplatesPage,
  })),
)
const MeetingsPage = lazy(() =>
  import('@/features/meetings/meetings-page').then((module) => ({
    default: module.MeetingsPage,
  })),
)
const OrganizationPage = lazy(() =>
  import('@/features/organizations/organization-page').then((module) => ({
    default: module.OrganizationPage,
  })),
)
const OrganizationSettingsPage = lazy(() =>
  import('@/features/organizations/settings-page').then((module) => ({
    default: module.OrganizationSettingsPage,
  })),
)
const PlatformPage = lazy(() =>
  import('@/features/platform/platform-page').then((module) => ({
    default: module.PlatformPage,
  })),
)
const AdministrationPage = lazy(() =>
  import('@/features/platform/administration-page').then((module) => ({
    default: module.AdministrationPage,
  })),
)
const TeamsPage = lazy(() =>
  import('@/features/teams/teams-page').then((module) => ({
    default: module.TeamsPage,
  })),
)
const TeamDetailPage = lazy(() =>
  import('@/features/teams/team-detail-page').then((module) => ({
    default: module.TeamDetailPage,
  })),
)
const MembersPage = lazy(() =>
  import('@/features/users/members-page').then((module) => ({
    default: module.MembersPage,
  })),
)
const UserManagementPage = lazy(() =>
  import('@/features/users/user-management-page').then((module) => ({
    default: module.UserManagementPage,
  })),
)
const RolesPage = lazy(() =>
  import('@/features/users/roles-page').then((module) => ({
    default: module.RolesPage,
  })),
)
const MyAccountPage = lazy(() =>
  import('@/features/users/my-account-page').then((module) => ({
    default: module.MyAccountPage,
  })),
)
const ProfilePage = lazy(() =>
  import('@/features/users/profile-page').then((module) => ({
    default: module.ProfilePage,
  })),
)
const WorkspaceListPage = lazy(() =>
  import('@/features/workspaces/workspace-list-page').then((module) => ({
    default: module.WorkspaceListPage,
  })),
)
const WorkspaceDetailPage = lazy(() =>
  import('@/features/workspaces/workspace-detail-page').then((module) => ({
    default: module.WorkspaceDetailPage,
  })),
)
const SystemHealthPage = lazy(() =>
  import('@/features/system-health/system-health-page').then((module) => ({
    default: module.SystemHealthPage,
  })),
)
const AuditCenterPage = lazy(() =>
  import('@/features/audit/audit-center-page').then((module) => ({
    default: module.AuditCenterPage,
  })),
)
const IntegrationCenterPage = lazy(() =>
  import('@/features/integrations/integration-center-page').then((module) => ({
    default: module.IntegrationCenterPage,
  })),
)
const TasksPage = lazy(() =>
  import('@/features/tasks/tasks-page').then((module) => ({
    default: module.TasksPage,
  })),
)

const rootRoute = createRootRoute({ component: RouteOutlet })
const VouchersPage = lazy(() =>
  import('@/features/finance/vouchers-page').then((m) => ({
    default: m.VouchersPage,
  })),
)
const VoucherEditorPage = lazy(() =>
  import('@/features/finance/voucher-editor').then((m) => ({
    default: m.VoucherEditorPage,
  })),
)
const VoucherDetailPage = lazy(() =>
  import('@/features/finance/voucher-detail').then((m) => ({
    default: m.VoucherDetailPage,
  })),
)
const FinancePage = lazy(() =>
  import('@/features/finance/finance-page').then((m) => ({
    default: m.FinancePage,
  })),
)
const AccountDetailPage = lazy(() =>
  import('@/features/finance/finance-page').then((m) => ({
    default: m.AccountDetailPage,
  })),
)
const protectedRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: '_protected',
  component: ProtectedRoute,
})
const appShellRoute = createRoute({
  getParentRoute: () => protectedRoute,
  id: '_app',
  component: AppShell,
})

const protectedPages = [
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/vouchers',
    component: VouchersPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/vouchers/new',
    component: VoucherEditorPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/vouchers/$voucherId',
    component: VoucherDetailPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/vouchers/$voucherId/edit',
    component: VoucherEditorPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/finance',
    component: FinancePage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/finance/accounts/$accountId',
    component: AccountDetailPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/',
    component: DashboardPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/tasks',
    component: TasksPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/organization',
    component: OrganizationPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/organization/settings',
    component: OrganizationSettingsPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/workspaces',
    component: WorkspaceListPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/workspaces/$workspaceId',
    component: WorkspaceDetailPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/teams',
    component: TeamsPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/teams/$teamId',
    component: TeamDetailPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/members',
    component: MembersPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/users',
    component: UserManagementPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/roles',
    component: RolesPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/platform',
    component: PlatformPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/administration',
    component: AdministrationPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/help',
    component: HelpCenterPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/notifications',
    component: NotificationCenterPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/mail',
    component: MailPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/mail/compose',
    component: () => <MailPage compose />,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/mail/$messageId',
    component: MailPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/system-health',
    component: SystemHealthPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/audit',
    component: AuditCenterPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/integrations',
    component: IntegrationCenterPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/invitations',
    component: InvitationsPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/profile',
    component: ProfilePage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/profile/security',
    component: ProfilePage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/profile/security/mfa',
    component: ProfilePage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/profile/notifications',
    component: ProfilePage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/profile/preferences',
    component: ProfilePage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/profile/sessions',
    component: ProfilePage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/profile/connections',
    component: ProfilePage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/profile/organization',
    component: ProfilePage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/account',
    component: MyAccountPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/settings/sessions',
    component: SessionsPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/calendar',
    component: () => <CalendarPage />,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/calendar/day',
    component: () => <CalendarPage view="day" />,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/calendar/week',
    component: () => <CalendarPage view="week" />,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/calendar/month',
    component: () => <CalendarPage view="month" />,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/calendar/agenda',
    component: () => <CalendarPage view="agenda" />,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/calendar/settings',
    component: () => <CalendarPage view="settings" />,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/calendar/availability',
    component: () => <CalendarPage view="availability" />,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/calendar/resources',
    component: () => <CalendarPage view="resources" />,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/calendar/holidays',
    component: () => <CalendarPage view="holidays" />,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/meetings',
    component: MeetingsPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/meetings/upcoming',
    component: () => <MeetingsPage view="upcoming" />,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/meetings/past',
    component: () => <MeetingsPage view="past" />,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/meetings/actions',
    component: () => <MeetingsPage view="actions" />,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/change-password',
    component: ChangePasswordPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/meetings/templates',
    component: MeetingTemplatesPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/meetings/new',
    component: CreateMeetingPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/meetings/$meetingId',
    component: MeetingDetailPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/meetings/$meetingId/edit',
    component: EditMeetingPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/chat',
    component: ChatHomePage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/chat/new',
    component: () => <ChatHomePage view="new" />,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/chat/channels',
    component: () => <ChatHomePage view="channels" />,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/chat/archived',
    component: () => <ChatHomePage view="archived" />,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/chat/$conversationId',
    component: ConversationPage,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/chat/$conversationId/thread/$messageId',
    component: () => <ConversationPage thread />,
  }),
  createRoute({
    getParentRoute: () => appShellRoute,
    path: '/calendar/$calendarId',
    component: () => <CalendarPage view="detail" />,
  }),
]

const publicRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: '_public',
  component: PublicRoute,
})
const authLayoutRoute = createRoute({
  getParentRoute: () => publicRoute,
  id: '_auth',
  component: AuthLayout,
})
const publicPages = [
  createRoute({
    getParentRoute: () => authLayoutRoute,
    path: '/login',
    component: LoginPage,
  }),
  createRoute({
    getParentRoute: () => authLayoutRoute,
    path: '/register',
    component: RegisterPage,
  }),
  createRoute({
    getParentRoute: () => authLayoutRoute,
    path: '/forgot-password',
    component: ForgotPasswordPage,
  }),
  createRoute({
    getParentRoute: () => authLayoutRoute,
    path: '/reset-password',
    component: ResetPasswordPage,
  }),
  createRoute({
    getParentRoute: () => authLayoutRoute,
    path: '/verify-email',
    component: VerifyEmailPage,
  }),
  createRoute({
    getParentRoute: () => authLayoutRoute,
    path: '/accept-invitation',
    component: AcceptInvitationPage,
  }),
]

const routeTree = rootRoute.addChildren([
  protectedRoute.addChildren([appShellRoute.addChildren(protectedPages)]),
  publicRoute.addChildren([authLayoutRoute.addChildren(publicPages)]),
  createRoute({
    getParentRoute: () => rootRoute,
    path: '/unauthorized',
    component: StatusPages,
  }),
  createRoute({
    getParentRoute: () => rootRoute,
    path: '/forbidden',
    component: ForbiddenPage,
  }),
])

export const router = createRouter({
  routeTree,
  defaultPreload: 'intent',
  defaultPreloadStaleTime: 0,
})

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
