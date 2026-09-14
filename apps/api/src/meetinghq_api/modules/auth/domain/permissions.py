"""Central permission catalog and default role policies."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PermissionDefinition:
    """Declarative permission metadata."""

    name: str
    resource: str
    action: str
    description: str


class Permissions:
    """Stable permission names consumed by endpoint declarations."""

    USERS_READ = "users.read"
    USERS_WRITE = "users.write"
    MEETINGS_CREATE = "meetings.create"
    MEETINGS_UPDATE = "meetings.update"
    MEETINGS_DELETE = "meetings.delete"
    MEETINGS_READ = "meetings.read"
    MEETINGS_CANCEL = "meetings.cancel"
    MEETINGS_MANAGE = "meetings.manage"
    AGENDA_MANAGE = "agenda.manage"
    ACTION_MANAGE = "action.manage"
    CALENDAR_READ = "calendar.read"
    CALENDAR_WRITE = "calendar.write"
    CALENDAR_MANAGE = "calendar.manage"
    RESOURCE_MANAGE = "resource.manage"
    HOLIDAY_MANAGE = "holiday.manage"
    AVAILABILITY_MANAGE = "availability.manage"
    CHAT_SEND = "chat.send"
    CHAT_READ = "chat.read"
    CHAT_CREATE = "chat.create"
    CHAT_EDIT = "chat.edit"
    CHAT_DELETE = "chat.delete"
    CHAT_MANAGE = "chat.manage"
    CHANNEL_MANAGE = "channel.manage"
    CONVERSATION_MANAGE = "conversation.manage"
    BILLING_MANAGE = "billing.manage"
    REPORTS_VIEW = "reports.view"
    ADMIN_MANAGE = "admin.manage"
    ORGANIZATIONS_READ = "organizations.read"
    ORGANIZATIONS_WRITE = "organizations.write"
    WORKSPACES_READ = "workspaces.read"
    WORKSPACES_WRITE = "workspaces.write"
    TEAMS_READ = "teams.read"
    TEAMS_WRITE = "teams.write"
    INVITATIONS_READ = "invitations.read"
    INVITATIONS_WRITE = "invitations.write"
    INTEGRATIONS_READ = "integrations.view"
    INTEGRATIONS_MANAGE = "integrations.manage"
    INTEGRATIONS_TEST = "integrations.test"
    TASKS_VIEW_OWN = "tasks.view_own"
    TASKS_CREATE_OWN = "tasks.create_own"
    TASKS_EDIT_OWN = "tasks.edit_own"
    TASKS_ASSIGN = "tasks.assign"
    TASKS_VIEW_TEAM = "tasks.view_team"
    TASKS_VIEW_DEPARTMENT = "tasks.view_department"
    TASKS_MANAGE = "tasks.manage"
    TASKS_COMMENT = "tasks.comment"
    TASKS_COMPLETE = "tasks.complete"
    TASKS_REOPEN = "tasks.reopen"
    TASKS_EXPORT = "tasks.export"
    ACTIVITY_CREATE_OWN = "activity.create_own"
    ACTIVITY_VIEW_OWN = "activity.view_own"
    ACTIVITY_EDIT_OWN = "activity.edit_own"
    ACTIVITY_VIEW_TEAM = "activity.view_team"
    ACTIVITY_VIEW_DEPARTMENT = "activity.view_department"
    ACTIVITY_MANAGE = "activity.manage"
    VOUCHERS_VIEW_OWN = "vouchers.view_own"
    VOUCHERS_CREATE = "vouchers.create"
    VOUCHERS_EDIT_DRAFT = "vouchers.edit_draft"
    VOUCHERS_SUBMIT = "vouchers.submit"
    VOUCHERS_APPROVE = "vouchers.approve"
    VOUCHERS_REJECT = "vouchers.reject"
    VOUCHERS_RETURN = "vouchers.return"
    VOUCHERS_DISBURSE = "vouchers.disburse"
    VOUCHERS_AUDIT = "vouchers.audit"
    FINANCE_ACCOUNTS_VIEW = "finance.accounts.view"
    FINANCE_ACCOUNTS_MANAGE = "finance.accounts.manage"
    FINANCE_TRANSACTIONS_VIEW = "finance.transactions.view"
    FINANCE_TRANSACTIONS_MANAGE = "finance.transactions.manage"
    FINANCE_REVERSE = "finance.reverse"
    FINANCE_RECONCILE = "finance.reconcile"
    LEAVE_VIEW_OWN = "leave.view_own"
    LEAVE_REQUEST = "leave.request"
    LEAVE_WITHDRAW_OWN = "leave.withdraw_own"
    LEAVE_VIEW_TEAM = "leave.view_team"
    LEAVE_REVIEW = "leave.review"
    LEAVE_APPROVE = "leave.approve"
    LEAVE_REJECT = "leave.reject"
    LEAVE_TYPES_VIEW = "leave.types.view"
    LEAVE_TYPES_MANAGE = "leave.types.manage"
    LEAVE_BALANCES_VIEW = "leave.balances.view"
    LEAVE_BALANCES_ADJUST = "leave.balances.adjust"
    LEAVE_HOLIDAYS_MANAGE = "leave.holidays.manage"
    LEAVE_REPORTS_VIEW = "leave.reports.view"
    LEAVE_EXPORT = "leave.export"
    PAYROLL_VIEW_OWN = "payroll.view_own"
    PAYROLL_PAYSLIP_DOWNLOAD_OWN = "payroll.payslip.download_own"
    PAYROLL_PERIODS_VIEW = "payroll.periods.view"
    PAYROLL_PERIODS_MANAGE = "payroll.periods.manage"
    PAYROLL_PREPARE = "payroll.prepare"
    PAYROLL_REVIEW = "payroll.review"
    PAYROLL_APPROVE = "payroll.approve"
    PAYROLL_PAY = "payroll.pay"
    PAYROLL_VIEW_EMPLOYEE = "payroll.view_employee"
    PAYROLL_SALARY_STRUCTURE_VIEW = "payroll.salary_structure.view"
    PAYROLL_SALARY_STRUCTURE_MANAGE = "payroll.salary_structure.manage"
    PAYROLL_COMPONENTS_MANAGE = "payroll.components.manage"
    PAYROLL_STATUTORY_MANAGE = "payroll.statutory.manage"
    PAYROLL_LOANS_MANAGE = "payroll.loans.manage"
    PAYROLL_REPORTS_VIEW = "payroll.reports.view"
    PAYROLL_EXPORT = "payroll.export"
    PROJECTS_VIEW = "projects.view"
    PROJECTS_CREATE = "projects.create"
    PROJECTS_EDIT = "projects.edit"
    PROJECTS_ARCHIVE = "projects.archive"
    PROJECTS_MANAGE_MEMBERS = "projects.manage_members"
    PROJECTS_MANAGE_MILESTONES = "projects.manage_milestones"
    PROJECTS_MANAGE_RISKS = "projects.manage_risks"
    PROJECTS_MANAGE_ISSUES = "projects.manage_issues"
    PROJECTS_MANAGE_FILES = "projects.manage_files"
    PROJECTS_GENERATE_REPORTS = "projects.generate_reports"
    PROJECTS_VIEW_REPORTS = "projects.view_reports"
    REPORTS_VIEW_OWN = "reports.view_own"
    REPORTS_CREATE_OWN = "reports.create_own"
    REPORTS_SUBMIT_OWN = "reports.submit_own"
    REPORTS_VIEW_TEAM = "reports.view_team"
    REPORTS_REVIEW_TEAM = "reports.review_team"
    REPORTS_VIEW_DEPARTMENT = "reports.view_department"
    REPORTS_VIEW_MANAGEMENT = "reports.view_management"
    REPORTS_GENERATE = "reports.generate"
    REPORTS_EXPORT = "reports.export"
    REPORTS_MANAGE_POLICY = "reports.manage_policy"


_LEGACY_PERMISSION_CATALOG = tuple(
    PermissionDefinition(name, resource, action, description)
    for name, resource, action, description in (
        (Permissions.USERS_READ, "users", "read", "View organization users"),
        (Permissions.USERS_WRITE, "users", "write", "Manage organization users"),
        (Permissions.MEETINGS_CREATE, "meetings", "create", "Create meetings"),
        (Permissions.MEETINGS_UPDATE, "meetings", "update", "Update meetings"),
        (Permissions.MEETINGS_DELETE, "meetings", "delete", "Delete meetings"),
        (Permissions.MEETINGS_READ, "meetings", "read", "View meetings"),
        (Permissions.MEETINGS_CANCEL, "meetings", "cancel", "Cancel meetings"),
        (Permissions.MEETINGS_MANAGE, "meetings", "manage", "Manage meeting lifecycle"),
        (Permissions.AGENDA_MANAGE, "agenda", "manage", "Manage meeting agendas"),
        (Permissions.ACTION_MANAGE, "action", "manage", "Manage meeting action items"),
        (Permissions.CALENDAR_READ, "calendar", "read", "View calendars"),
        (Permissions.CALENDAR_WRITE, "calendar", "write", "Create and update calendars"),
        (Permissions.CALENDAR_MANAGE, "calendar", "manage", "Manage calendar lifecycle"),
        (Permissions.RESOURCE_MANAGE, "resource", "manage", "Manage scheduling resources"),
        (Permissions.HOLIDAY_MANAGE, "holiday", "manage", "Manage organization holidays"),
        (Permissions.AVAILABILITY_MANAGE, "availability", "manage", "Manage availability"),
        (Permissions.CHAT_SEND, "chat", "send", "Send chat messages"),
        (Permissions.CHAT_READ, "chat", "read", "Read conversations and messages"),
        (Permissions.CHAT_CREATE, "chat", "create", "Create conversations and messages"),
        (Permissions.CHAT_EDIT, "chat", "edit", "Edit own messages"),
        (Permissions.CHAT_DELETE, "chat", "delete", "Delete own messages"),
        (Permissions.CHAT_MANAGE, "chat", "manage", "Moderate enterprise chat"),
        (Permissions.CHANNEL_MANAGE, "channel", "manage", "Manage channels"),
        (Permissions.CONVERSATION_MANAGE, "conversation", "manage", "Manage conversations"),
        (Permissions.BILLING_MANAGE, "billing", "manage", "Manage billing"),
        (Permissions.REPORTS_VIEW, "reports", "view", "View reports"),
        (Permissions.ADMIN_MANAGE, "admin", "manage", "Manage platform settings"),
        (Permissions.ORGANIZATIONS_READ, "organizations", "read", "View organization"),
        (Permissions.ORGANIZATIONS_WRITE, "organizations", "write", "Manage organization"),
        (Permissions.WORKSPACES_READ, "workspaces", "read", "View workspaces"),
        (Permissions.WORKSPACES_WRITE, "workspaces", "write", "Manage workspaces"),
        (Permissions.TEAMS_READ, "teams", "read", "View teams"),
        (Permissions.TEAMS_WRITE, "teams", "write", "Manage teams"),
        (Permissions.INVITATIONS_READ, "invitations", "read", "View invitations"),
        (Permissions.INVITATIONS_WRITE, "invitations", "write", "Manage invitations"),
        (Permissions.INTEGRATIONS_READ, "integrations", "view", "View integration settings"),
        (
            Permissions.INTEGRATIONS_MANAGE,
            "integrations",
            "manage",
            "Manage integration settings",
        ),
        (Permissions.INTEGRATIONS_TEST, "integrations", "test", "Test integration delivery"),
        (Permissions.TASKS_VIEW_OWN, "tasks", "view_own", "View own tasks"),
        (Permissions.TASKS_CREATE_OWN, "tasks", "create_own", "Create own tasks"),
        (Permissions.TASKS_EDIT_OWN, "tasks", "edit_own", "Edit own tasks"),
        (Permissions.TASKS_ASSIGN, "tasks", "assign", "Assign tasks to authorized employees"),
        (Permissions.TASKS_VIEW_TEAM, "tasks", "view_team", "View direct-report tasks"),
        (Permissions.TASKS_VIEW_DEPARTMENT, "tasks", "view_department", "View department tasks"),
        (Permissions.TASKS_MANAGE, "tasks", "manage", "Manage all organization tasks"),
        (Permissions.TASKS_COMMENT, "tasks", "comment", "Comment on visible tasks"),
        (Permissions.TASKS_COMPLETE, "tasks", "complete", "Complete tasks"),
        (Permissions.TASKS_REOPEN, "tasks", "reopen", "Reopen tasks"),
        (Permissions.TASKS_EXPORT, "tasks", "export", "Export authorized task lists"),
        (Permissions.ACTIVITY_CREATE_OWN, "activity", "create_own", "Record own daily activity"),
        (Permissions.ACTIVITY_VIEW_OWN, "activity", "view_own", "View own daily activity"),
        (Permissions.ACTIVITY_EDIT_OWN, "activity", "edit_own", "Edit own daily activity"),
        (Permissions.ACTIVITY_VIEW_TEAM, "activity", "view_team", "View direct-report activity"),
        (
            Permissions.ACTIVITY_VIEW_DEPARTMENT,
            "activity",
            "view_department",
            "View department activity",
        ),
        (Permissions.ACTIVITY_MANAGE, "activity", "manage", "Manage organization activity records"),
    )
)

_FINANCE_PERMISSION_CATALOG = tuple(
    PermissionDefinition(name, resource, action, description)
    for name, resource, action, description in (
        (Permissions.VOUCHERS_VIEW_OWN, "vouchers", "view_own", "View own vouchers"),
        (Permissions.VOUCHERS_CREATE, "vouchers", "create", "Create vouchers"),
        (Permissions.VOUCHERS_EDIT_DRAFT, "vouchers", "edit_draft", "Edit own draft vouchers"),
        (Permissions.VOUCHERS_SUBMIT, "vouchers", "submit", "Submit vouchers"),
        (Permissions.VOUCHERS_APPROVE, "vouchers", "approve", "Approve vouchers"),
        (Permissions.VOUCHERS_REJECT, "vouchers", "reject", "Reject vouchers"),
        (Permissions.VOUCHERS_RETURN, "vouchers", "return", "Return vouchers for correction"),
        (Permissions.VOUCHERS_DISBURSE, "vouchers", "disburse", "Disburse approved vouchers"),
        (Permissions.VOUCHERS_AUDIT, "vouchers", "audit", "Audit organization vouchers"),
        ("vouchers.view_all", "vouchers", "view_all", "Review vouchers across the organization"),
        ("vouchers.comment", "vouchers", "comment", "Comment on accessible vouchers"),
        ("vouchers.export", "vouchers", "export", "Export accessible vouchers and PDFs"),
        ("finance.export", "finance", "export", "Export statements and transaction lists"),
        (Permissions.FINANCE_ACCOUNTS_VIEW, "finance", "accounts_view", "View finance accounts"),
        (
            Permissions.FINANCE_ACCOUNTS_MANAGE,
            "finance",
            "accounts_manage",
            "Manage finance accounts",
        ),
        (
            Permissions.FINANCE_TRANSACTIONS_VIEW,
            "finance",
            "transactions_view",
            "View finance transactions",
        ),
        (
            Permissions.FINANCE_TRANSACTIONS_MANAGE,
            "finance",
            "transactions_manage",
            "Create controlled finance adjustments and account transfers",
        ),
        (Permissions.FINANCE_REVERSE, "finance", "reverse", "Reverse finance transactions"),
        (Permissions.FINANCE_RECONCILE, "finance", "reconcile", "Reconcile finance transactions"),
    )
)

_LEAVE_PERMISSION_CATALOG = tuple(
    PermissionDefinition(name, "leave", action, description)
    for name, action, description in (
        (Permissions.LEAVE_VIEW_OWN, "view_own", "View own leave records"),
        (Permissions.LEAVE_REQUEST, "request", "Create leave requests"),
        (Permissions.LEAVE_WITHDRAW_OWN, "withdraw_own", "Withdraw own leave requests"),
        (Permissions.LEAVE_VIEW_TEAM, "view_team", "View direct-report leave"),
        (Permissions.LEAVE_REVIEW, "review", "Review authorized leave requests"),
        (Permissions.LEAVE_APPROVE, "approve", "Approve authorized leave requests"),
        (Permissions.LEAVE_REJECT, "reject", "Reject authorized leave requests"),
        (Permissions.LEAVE_TYPES_VIEW, "types_view", "View leave policy types"),
        (Permissions.LEAVE_TYPES_MANAGE, "types_manage", "Manage leave policy types"),
        (Permissions.LEAVE_BALANCES_VIEW, "balances_view", "View authorized leave balances"),
        (Permissions.LEAVE_BALANCES_ADJUST, "balances_adjust", "Adjust leave balances"),
        (Permissions.LEAVE_HOLIDAYS_MANAGE, "holidays_manage", "Manage leave holidays"),
        (Permissions.LEAVE_REPORTS_VIEW, "reports_view", "View leave reports"),
        (Permissions.LEAVE_EXPORT, "export", "Export leave data"),
    )
)

_PAYROLL_PERMISSION_CATALOG = tuple(
    PermissionDefinition(name, "payroll", action, description)
    for name, action, description in (
        (Permissions.PAYROLL_VIEW_OWN, "view_own", "View own Payroll and payslips"),
        (
            Permissions.PAYROLL_PAYSLIP_DOWNLOAD_OWN,
            "payslip_download_own",
            "Download own secure payslips",
        ),
        (Permissions.PAYROLL_PERIODS_VIEW, "periods_view", "View Payroll periods"),
        (Permissions.PAYROLL_PERIODS_MANAGE, "periods_manage", "Manage Payroll periods"),
        (Permissions.PAYROLL_PREPARE, "prepare", "Prepare and submit Payroll"),
        (Permissions.PAYROLL_REVIEW, "review", "Review and return Payroll"),
        (Permissions.PAYROLL_APPROVE, "approve", "Approve Payroll"),
        (Permissions.PAYROLL_PAY, "pay", "Pay, post, close, and reverse Payroll"),
        (Permissions.PAYROLL_VIEW_EMPLOYEE, "view_employee", "View employee Payroll details"),
        (
            Permissions.PAYROLL_SALARY_STRUCTURE_VIEW,
            "salary_structure_view",
            "View salary structures and statutory configuration",
        ),
        (
            Permissions.PAYROLL_SALARY_STRUCTURE_MANAGE,
            "salary_structure_manage",
            "Manage employee salary structures",
        ),
        (Permissions.PAYROLL_COMPONENTS_MANAGE, "components_manage", "Manage salary components"),
        (
            Permissions.PAYROLL_STATUTORY_MANAGE,
            "statutory_manage",
            "Manage effective-dated statutory rules",
        ),
        (Permissions.PAYROLL_LOANS_MANAGE, "loans_manage", "Manage Payroll loans and advances"),
        (Permissions.PAYROLL_REPORTS_VIEW, "reports_view", "View Payroll reports"),
        (Permissions.PAYROLL_EXPORT, "export", "Export tenant-scoped Payroll data"),
    )
)

_PROJECT_PERMISSION_CATALOG = tuple(
    PermissionDefinition(name, "projects", action, description)
    for name, action, description in (
        (Permissions.PROJECTS_VIEW, "view", "View authorized projects"),
        (Permissions.PROJECTS_CREATE, "create", "Create projects"),
        (Permissions.PROJECTS_EDIT, "edit", "Manage organization projects"),
        (Permissions.PROJECTS_ARCHIVE, "archive", "Archive completed projects"),
        (Permissions.PROJECTS_MANAGE_MEMBERS, "manage_members", "Manage project members"),
        (Permissions.PROJECTS_MANAGE_MILESTONES, "manage_milestones", "Manage project milestones"),
        (Permissions.PROJECTS_MANAGE_RISKS, "manage_risks", "Manage project risks"),
        (Permissions.PROJECTS_MANAGE_ISSUES, "manage_issues", "Manage project issues"),
        (Permissions.PROJECTS_MANAGE_FILES, "manage_files", "Manage project files"),
        (Permissions.PROJECTS_GENERATE_REPORTS, "generate_reports", "Generate project reports"),
        (Permissions.PROJECTS_VIEW_REPORTS, "view_reports", "View project reports"),
    )
)

_REPORT_PERMISSION_CATALOG = tuple(
    PermissionDefinition(name, "reports", action, description)
    for name, action, description in (
        (Permissions.REPORTS_VIEW_OWN, "view_own", "View own generated reports"),
        (Permissions.REPORTS_CREATE_OWN, "create_own", "Generate own reports"),
        (Permissions.REPORTS_SUBMIT_OWN, "submit_own", "Submit own reports for review"),
        (Permissions.REPORTS_VIEW_TEAM, "view_team", "View direct-report and team reports"),
        (Permissions.REPORTS_REVIEW_TEAM, "review_team", "Review authorized staff reports"),
        (
            Permissions.REPORTS_VIEW_DEPARTMENT,
            "view_department",
            "View authorized department reports",
        ),
        (
            Permissions.REPORTS_VIEW_MANAGEMENT,
            "view_management",
            "View organization management intelligence",
        ),
        (Permissions.REPORTS_GENERATE, "generate", "Generate authorized management reports"),
        (Permissions.REPORTS_EXPORT, "export", "Export authorized reporting data"),
        (
            Permissions.REPORTS_MANAGE_POLICY,
            "manage_policy",
            "Manage organization reporting policy",
        ),
    )
)

MVP_PERMISSION_RESOURCES = (
    "dashboard",
    "calendar",
    "meetings",
    "chat",
    "mail",
    "members",
    "users",
    "roles",
    "reports",
    "settings",
    "notifications",
)
MVP_PERMISSION_ACTIONS = ("view", "create", "edit", "delete", "manage", "export")
MVP_PERMISSION_CATALOG = tuple(
    PermissionDefinition(
        f"{resource}.{action}",
        resource,
        action,
        f"{action.title()} {resource}",
    )
    for resource in MVP_PERMISSION_RESOURCES
    for action in MVP_PERMISSION_ACTIONS
)
PERMISSION_CATALOG = tuple(
    {
        item.name: item
        for item in (
            *_LEGACY_PERMISSION_CATALOG,
            *_FINANCE_PERMISSION_CATALOG,
            *_LEAVE_PERMISSION_CATALOG,
            *_PAYROLL_PERMISSION_CATALOG,
            *_PROJECT_PERMISSION_CATALOG,
            *_REPORT_PERMISSION_CATALOG,
            *MVP_PERMISSION_CATALOG,
        )
    }.values()
)


def _matrix(resources: set[str], actions: set[str] | None = None) -> frozenset[str]:
    allowed_actions = actions or set(MVP_PERMISSION_ACTIONS)
    return frozenset(f"{resource}.{action}" for resource in resources for action in allowed_actions)


_legacy_admin = frozenset(item.name for item in _LEGACY_PERMISSION_CATALOG)
_finance_admin = frozenset(item.name for item in _FINANCE_PERMISSION_CATALOG)
_leave_admin = frozenset(item.name for item in _LEAVE_PERMISSION_CATALOG)
_payroll_admin = frozenset(item.name for item in _PAYROLL_PERMISSION_CATALOG)
_project_admin = frozenset(item.name for item in _PROJECT_PERMISSION_CATALOG)
_report_admin = frozenset(item.name for item in _REPORT_PERMISSION_CATALOG)
_task_employee = frozenset(
    {
        Permissions.TASKS_VIEW_OWN,
        Permissions.TASKS_CREATE_OWN,
        Permissions.TASKS_EDIT_OWN,
        Permissions.TASKS_COMMENT,
        Permissions.TASKS_COMPLETE,
        Permissions.TASKS_REOPEN,
        Permissions.ACTIVITY_CREATE_OWN,
        Permissions.ACTIVITY_VIEW_OWN,
        Permissions.ACTIVITY_EDIT_OWN,
    }
)
_task_manager = _task_employee | frozenset(
    {
        Permissions.TASKS_ASSIGN,
        Permissions.TASKS_VIEW_TEAM,
        Permissions.TASKS_VIEW_DEPARTMENT,
        Permissions.ACTIVITY_VIEW_TEAM,
        Permissions.ACTIVITY_VIEW_DEPARTMENT,
    }
)
_meeting_operator = frozenset(
    {
        Permissions.MEETINGS_CREATE,
        Permissions.MEETINGS_UPDATE,
        Permissions.MEETINGS_DELETE,
        Permissions.MEETINGS_READ,
        Permissions.MEETINGS_CANCEL,
        Permissions.MEETINGS_MANAGE,
        Permissions.AGENDA_MANAGE,
        Permissions.ACTION_MANAGE,
        Permissions.CALENDAR_READ,
        Permissions.CALENDAR_WRITE,
        Permissions.CHAT_READ,
        Permissions.CHAT_SEND,
        Permissions.ORGANIZATIONS_READ,
        Permissions.USERS_READ,
        Permissions.WORKSPACES_READ,
    }
)

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "Super Admin": frozenset(item.name for item in PERMISSION_CATALOG),
    "Admin": _legacy_admin
    | _finance_admin
    | _leave_admin
    | _payroll_admin
    | _project_admin
    | _report_admin
    | _matrix(set(MVP_PERMISSION_RESOURCES)),
    "Meeting Organizer": _meeting_operator
    | _matrix({"dashboard"}, {"view"})
    | _matrix({"calendar", "meetings"})
    | _matrix({"chat", "mail"}, {"view", "create", "edit"})
    | _matrix({"members", "users", "settings"}, {"view"}),
    "Team Manager": _meeting_operator
    | frozenset(
        {
            Permissions.CALENDAR_MANAGE,
            Permissions.CHAT_CREATE,
            Permissions.CHAT_EDIT,
            Permissions.CHAT_DELETE,
            Permissions.CHANNEL_MANAGE,
            Permissions.TEAMS_READ,
            Permissions.TEAMS_WRITE,
        }
    ),
    "Employee": frozenset(
        {
            Permissions.ORGANIZATIONS_READ,
            Permissions.WORKSPACES_READ,
            Permissions.TEAMS_READ,
            Permissions.USERS_READ,
            Permissions.MEETINGS_CREATE,
            Permissions.MEETINGS_UPDATE,
            Permissions.MEETINGS_READ,
            Permissions.AGENDA_MANAGE,
            Permissions.ACTION_MANAGE,
            Permissions.CALENDAR_READ,
            Permissions.CALENDAR_WRITE,
            Permissions.CHAT_SEND,
            Permissions.CHAT_READ,
            Permissions.CHAT_CREATE,
            Permissions.CHAT_EDIT,
        }
    )
    | _task_employee
    | frozenset(
        {
            Permissions.LEAVE_VIEW_OWN,
            Permissions.LEAVE_REQUEST,
            Permissions.LEAVE_WITHDRAW_OWN,
            Permissions.LEAVE_TYPES_VIEW,
            Permissions.LEAVE_BALANCES_VIEW,
        }
    )
    | frozenset(
        {
            Permissions.VOUCHERS_VIEW_OWN,
            Permissions.VOUCHERS_CREATE,
            Permissions.VOUCHERS_EDIT_DRAFT,
            Permissions.VOUCHERS_SUBMIT,
        }
    )
    | _matrix({"dashboard", "calendar", "meetings", "chat", "members"}, {"view"})
    | _matrix({"calendar", "meetings", "chat", "mail"}, {"create", "edit"})
    | _matrix({"mail"}, {"view"}),
    "Guest": frozenset(
        {
            Permissions.ORGANIZATIONS_READ,
            Permissions.WORKSPACES_READ,
            Permissions.CALENDAR_READ,
            Permissions.MEETINGS_READ,
        }
    )
    | _matrix({"dashboard", "calendar", "meetings"}, {"view"}),
}

ROLE_PERMISSIONS["Team Manager"] |= (
    _matrix({"dashboard"}, {"view"})
    | _matrix({"calendar", "meetings", "chat", "mail", "members"})
    | _matrix({"users", "reports", "settings"}, {"view"})
)
ROLE_PERMISSIONS["Team Manager"] |= _task_manager
ROLE_PERMISSIONS["Team Manager"] |= frozenset(
    {
        Permissions.PROJECTS_VIEW,
        Permissions.PROJECTS_CREATE,
        Permissions.PROJECTS_EDIT,
        Permissions.PROJECTS_MANAGE_MEMBERS,
        Permissions.PROJECTS_MANAGE_MILESTONES,
        Permissions.PROJECTS_MANAGE_RISKS,
        Permissions.PROJECTS_MANAGE_ISSUES,
        Permissions.PROJECTS_MANAGE_FILES,
        Permissions.PROJECTS_GENERATE_REPORTS,
        Permissions.PROJECTS_VIEW_REPORTS,
    }
)
ROLE_PERMISSIONS["Team Manager"] |= frozenset(
    {
        Permissions.REPORTS_VIEW_OWN,
        Permissions.REPORTS_CREATE_OWN,
        Permissions.REPORTS_SUBMIT_OWN,
        Permissions.REPORTS_VIEW_TEAM,
        Permissions.REPORTS_REVIEW_TEAM,
        Permissions.REPORTS_VIEW_DEPARTMENT,
        Permissions.REPORTS_EXPORT,
    }
)
ROLE_PERMISSIONS["Meeting Organizer"] |= _task_manager
ROLE_PERMISSIONS["Meeting Organizer"] |= frozenset(
    {
        Permissions.PROJECTS_VIEW,
        Permissions.PROJECTS_CREATE,
        Permissions.PROJECTS_VIEW_REPORTS,
    }
)
ROLE_PERMISSIONS["Team Manager"] |= frozenset(
    {
        Permissions.LEAVE_VIEW_OWN,
        Permissions.LEAVE_REQUEST,
        Permissions.LEAVE_WITHDRAW_OWN,
        Permissions.LEAVE_TYPES_VIEW,
        Permissions.LEAVE_BALANCES_VIEW,
        Permissions.LEAVE_VIEW_TEAM,
        Permissions.LEAVE_REVIEW,
        Permissions.LEAVE_APPROVE,
        Permissions.LEAVE_REJECT,
    }
)

_voucher_employee = frozenset(
    {
        "vouchers.view_own",
        "vouchers.create",
        "vouchers.edit_draft",
        "vouchers.submit",
        "vouchers.comment",
        "vouchers.export",
    }
)
ROLE_PERMISSIONS["Employee"] |= _voucher_employee
ROLE_PERMISSIONS["Employee"] |= frozenset(
    {Permissions.PROJECTS_VIEW, Permissions.PROJECTS_VIEW_REPORTS}
)
ROLE_PERMISSIONS["Employee"] |= frozenset(
    {
        Permissions.REPORTS_VIEW_OWN,
        Permissions.REPORTS_CREATE_OWN,
        Permissions.REPORTS_SUBMIT_OWN,
        Permissions.REPORTS_EXPORT,
    }
)
ROLE_PERMISSIONS["Employee"] |= frozenset(
    {Permissions.PAYROLL_VIEW_OWN, Permissions.PAYROLL_PAYSLIP_DOWNLOAD_OWN}
)
ROLE_PERMISSIONS["Team Manager"] |= _voucher_employee | frozenset(
    {"vouchers.approve", "vouchers.return", "vouchers.reject"}
)
ROLE_PERMISSIONS["Accountant"] = _matrix({"dashboard", "notifications"}, {"view"}) | frozenset(
    {
        "vouchers.view_own",
        "vouchers.disburse",
        "vouchers.comment",
        "vouchers.export",
        "finance.accounts.view",
        "finance.transactions.view",
        "finance.export",
        "finance.reconcile",
        "finance.reverse",
        Permissions.PAYROLL_VIEW_OWN,
        Permissions.PAYROLL_PAYSLIP_DOWNLOAD_OWN,
        Permissions.PAYROLL_PERIODS_VIEW,
        Permissions.PAYROLL_PAY,
        Permissions.PAYROLL_VIEW_EMPLOYEE,
        Permissions.PAYROLL_REPORTS_VIEW,
        Permissions.PAYROLL_EXPORT,
    }
)
ROLE_PERMISSIONS["Auditor"] = _matrix({"dashboard", "notifications"}, {"view"}) | frozenset(
    {
        "vouchers.view_own",
        "vouchers.audit",
        "vouchers.export",
        "finance.accounts.view",
        "finance.transactions.view",
        "finance.export",
        Permissions.PAYROLL_VIEW_OWN,
        Permissions.PAYROLL_PAYSLIP_DOWNLOAD_OWN,
        Permissions.PAYROLL_PERIODS_VIEW,
        Permissions.PAYROLL_VIEW_EMPLOYEE,
        Permissions.PAYROLL_REPORTS_VIEW,
        Permissions.PAYROLL_EXPORT,
        Permissions.PROJECTS_VIEW,
        Permissions.PROJECTS_VIEW_REPORTS,
    }
)

ROLE_PERMISSIONS["Payroll Officer"] = _matrix({"dashboard", "notifications"}, {"view"}) | frozenset(
    {
        Permissions.PAYROLL_VIEW_OWN,
        Permissions.PAYROLL_PAYSLIP_DOWNLOAD_OWN,
        Permissions.PAYROLL_PERIODS_VIEW,
        Permissions.PAYROLL_PERIODS_MANAGE,
        Permissions.PAYROLL_PREPARE,
        Permissions.PAYROLL_VIEW_EMPLOYEE,
        Permissions.PAYROLL_SALARY_STRUCTURE_VIEW,
        Permissions.PAYROLL_SALARY_STRUCTURE_MANAGE,
        Permissions.PAYROLL_COMPONENTS_MANAGE,
        Permissions.PAYROLL_STATUTORY_MANAGE,
        Permissions.PAYROLL_LOANS_MANAGE,
        Permissions.PAYROLL_REPORTS_VIEW,
        Permissions.PAYROLL_EXPORT,
        Permissions.FINANCE_ACCOUNTS_VIEW,
    }
)
ROLE_PERMISSIONS["Payroll Approver"] = _matrix(
    {"dashboard", "notifications"}, {"view"}
) | frozenset(
    {
        Permissions.PAYROLL_VIEW_OWN,
        Permissions.PAYROLL_PAYSLIP_DOWNLOAD_OWN,
        Permissions.PAYROLL_PERIODS_VIEW,
        Permissions.PAYROLL_REVIEW,
        Permissions.PAYROLL_APPROVE,
        Permissions.PAYROLL_VIEW_EMPLOYEE,
        Permissions.PAYROLL_REPORTS_VIEW,
        Permissions.PAYROLL_EXPORT,
    }
)
