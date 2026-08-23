# Workspaces and teams

Workspaces belong to exactly one organization and can be created, updated, archived,
and restored. Typed settings cover branding, working hours, calendar preferences,
meeting defaults, and chat defaults without implementing those future features.

Teams belong to a workspace and repeat the organization identifier as an indexed tenant
guard. Team visibility is public or private. Membership is explicit and carries one of
three roles: owner, manager, or member.

Creating a team assigns the creator as owner. Owners cannot leave or be removed until
ownership is transferred. Transfer demotes the previous owner to manager and promotes an
existing member atomically.

REST endpoints are documented interactively at `/api/docs`. All workspace and team
management operations declare centralized `workspaces.*` or `teams.*` permissions.

