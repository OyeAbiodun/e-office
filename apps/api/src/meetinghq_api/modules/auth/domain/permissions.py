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
    {item.name: item for item in (*_LEGACY_PERMISSION_CATALOG, *MVP_PERMISSION_CATALOG)}.values()
)


def _matrix(resources: set[str], actions: set[str] | None = None) -> frozenset[str]:
    allowed_actions = actions or set(MVP_PERMISSION_ACTIONS)
    return frozenset(f"{resource}.{action}" for resource in resources for action in allowed_actions)


_legacy_admin = frozenset(item.name for item in _LEGACY_PERMISSION_CATALOG)
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
        Permissions.USERS_READ,
    }
)

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "Super Admin": frozenset(item.name for item in PERMISSION_CATALOG),
    "Admin": _legacy_admin | _matrix(set(MVP_PERMISSION_RESOURCES)),
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
ROLE_PERMISSIONS["Meeting Organizer"] |= _task_manager
