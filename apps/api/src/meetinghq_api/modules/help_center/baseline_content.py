"""Version-controlled OfficeFlow guidance for system-managed baseline articles."""

# ruff: noqa: E501

from dataclasses import dataclass


@dataclass(frozen=True)
class Guide:
    summary: str
    audience: str
    prerequisites: tuple[str, ...]
    location: str
    steps: tuple[str, ...]
    concepts: tuple[str, ...]
    outcome: str
    recovery: tuple[str, ...]
    related: tuple[str, ...]


def _body(title: str, guide: Guide) -> str:
    def bullets(values: tuple[str, ...]) -> str:
        return "\n".join(f"- {value}" for value in values)

    steps = "\n".join(f"{index}. {value}" for index, value in enumerate(guide.steps, 1))
    return (
        f"# {title}\n\n"
        f"{guide.summary}\n\n"
        "## Purpose\n\n"
        f"Use this guide to complete the workflow confidently and understand what OfficeFlow records.\n\n"
        "## Who can use it\n\n"
        f"{guide.audience}\n\n"
        "## Before you start\n\n"
        f"{bullets(guide.prerequisites)}\n\n"
        "## Where to find it\n\n"
        f"{guide.location}\n\n"
        "## Step by step\n\n"
        f"{steps}\n\n"
        "## Important fields and concepts\n\n"
        f"{bullets(guide.concepts)}\n\n"
        "## What happens next\n\n"
        f"{guide.outcome}\n\n"
        "## Common problems and recovery\n\n"
        f"{bullets(guide.recovery)}\n\n"
        "## Related guides\n\n"
        f"{bullets(guide.related)}\n\n"
        "> Menus and actions appear only when your role, record access, and enabled OfficeFlow features allow them. "
        "If the guidance does not resolve the issue, open **Help & Support → Get support** and choose "
        "Request Help or Report an Issue. Never include passwords, payroll values, medical documents, or bank details."
    )


GUIDES: dict[str, Guide] = {
    "quick-start": Guide(
        "Learn the OfficeFlow workspace, navigation, search, quick actions, notifications, and account controls.",
        "Every signed-in employee; available actions still follow assigned permissions.",
        (
            "Your account is active.",
            "Complete any temporary-password change shown after first login.",
        ),
        "Start on **Home**. Use the sidebar for modules, the top bar for search and notifications, and the account menu for Profile.",
        (
            "Review Home for meetings, work due today, recent notifications, and permitted decision widgets.",
            "Open My Space for your tasks, activity, and personal work summary.",
            "Press Ctrl+K to open Global Search / Command Centre and find a page or command.",
            "Use Quick Create only for actions offered by your role.",
            "Open Notifications to read or archive attention items.",
            "Open Profile to set language, timezone, working hours, accessibility, and Light, Dark, or System theme.",
        ),
        (
            "A missing menu normally means the feature is disabled or your role lacks its view permission.",
            "Access Denied means you are signed in but not authorized; it is not a login failure.",
            "The sidebar marks the active page separately from whichever accordion group you choose to expand.",
        ),
        "Preferences are saved to your profile; operational changes create activity, notifications, or audit records where appropriate.",
        (
            "Cannot log in: use Forgot password, then follow the single-use link promptly.",
            "Temporary password rejected: meet the displayed password rules and enter the confirmation exactly.",
            "Missing menu or Access Denied: ask an administrator to review your role rather than sharing another user's account.",
        ),
        ("First Login", "Profile & Security", "Notifications", "Troubleshooting"),
    ),
    "first-login": Guide(
        "Sign in safely, change password credentials issued temporarily, and verify your personal settings.",
        "New users and users whose password was reset by an administrator.",
        (
            "Use the email address in your account invitation.",
            "Have the temporary password or current reset link available.",
        ),
        "Open the OfficeFlow sign-in page. Organization codes are resolved automatically and are not entered by users.",
        (
            "Enter your work email and password, then select Sign in.",
            "If prompted, enter a new password and confirmation that meet every displayed rule.",
            "After the change succeeds, return to Sign in and use the new password.",
            "Open Profile and confirm your name, timezone, language, and notification preferences.",
        ),
        (
            "Reset links expire after 20 minutes and are single-use.",
            "A temporary password must be replaced before normal access continues.",
        ),
        "OfficeFlow invalidates the one-time credential and starts a normal session only after successful sign-in.",
        (
            "Expired link: request a new reset email.",
            "Link already used: sign in with the new password or request another reset.",
            "Access Denied after login: contact your administrator about permissions.",
        ),
        ("Quick Start Guide", "Profile & Security", "Troubleshooting"),
    ),
    "projects": Guide(
        "Create project records and plan delivery with members, milestones, tasks, risks, issues, documents, and reports.",
        "Project members can view assigned projects; project managers and authorized administrators manage project records.",
        (
            "The project feature is enabled.",
            "Members and managers already exist in the organization directory.",
        ),
        "Open **My work → Projects**. Select a project for Overview, Work, Updates, Risks, Issues, Documents, Reports, and Settings.",
        (
            "Select New project, enter the purpose, dates, status, visibility, and accountable manager, then save.",
            "Add authorized members and assign project managers from the organization directory.",
            "Create milestones and project tasks, or link an existing OfficeFlow task rather than duplicating it.",
            "Record concise updates and maintain risks and issues with owner, impact, status, and response.",
            "Upload documents through the project document area and verify access before sharing.",
            "Review progress and health from real milestones and task completion; generate the project report when the reporting action is available.",
            "Complete or archive the project only after open work and required records are resolved.",
        ),
        (
            "Progress comes from recorded work, not a decorative estimate.",
            "Risks are possible future events; issues are problems already affecting delivery.",
            "Archiving preserves history and links.",
        ),
        "Members see the project according to visibility and permissions; linked tasks remain in My Work and project reporting uses recorded data.",
        (
            "Cannot add a person: confirm organization membership and project-management permission.",
            "Progress looks wrong: review linked tasks and milestones.",
            "Upload failed: check file type, size, connection, and document permission.",
        ),
        ("Tasks & Activities", "Reports & Management Intelligence", "People & Directory"),
    ),
    "tasks-activities": Guide(
        "Create, assign, track, discuss, and complete work while recording lightweight daily activity.",
        "Employees manage their own work; managers assign only within authorized reporting or department scope.",
        (
            "The assignee is active.",
            "Manager assignment requires both permission and an allowed reporting relationship.",
        ),
        "Open **My work → Tasks & Activities** or **My Space** for personal work.",
        (
            "Select New Task and enter a title, due date, priority, and optional instructions.",
            "Choose yourself or an authorized assignee; add reminders, follow-up, project, meeting, attachments, or checklist items as needed.",
            "Use quick actions to start work, update status or priority, and mark completion.",
            "Open task detail for comments, mentions, secure attachments, checklist progress, and readable history.",
            "Record Daily Activity with outcome, blockers, next step, time spent, and optional task, project, or meeting link.",
            "Review Today, Upcoming, Overdue, daily summary, and weekly summary to keep records current.",
        ),
        (
            "Overdue does not automatically change task status.",
            "Follow-up is a reminder, not a duplicate task.",
            "Meeting action items link to tasks without creating repeated records.",
        ),
        "Assignments and material updates notify the relevant users according to preferences and quiet hours; managers see only authorized staff work.",
        (
            "Assignee missing: confirm the employee is active and within your scope.",
            "Reminder missing: review notification preferences and quiet hours.",
            "Attachment denied: request task access; storage links are never shared directly.",
        ),
        ("Projects", "Meetings", "Notifications", "Reports & Management Intelligence"),
    ),
    "chat": Guide(
        "Use direct, group, team, and channel conversations with threads, reactions, mentions, files, and presence.",
        "Users with Chat permission and access to the selected conversation or team channel.",
        (
            "The recipient or channel is visible to you.",
            "Use the API fallback if realtime status is temporarily offline.",
        ),
        "Open **Communication → Chat** and choose a conversation or authorized channel.",
        (
            "Start or select a direct, group, or team conversation.",
            "Compose a message, add mentions or an allowed attachment, then send.",
            "Use a thread to keep a reply tied to its original message and reactions for lightweight acknowledgement.",
            "Check delivery/read indicators where enabled and save or bookmark important messages.",
        ),
        (
            "Private channels restrict membership.",
            "Realtime offline does not prevent API-based message delivery.",
            "Presence is informational and may lag during reconnect.",
        ),
        "Messages appear in conversation history and notifications are routed according to mention and conversation preferences.",
        (
            "Realtime offline: keep working, then check connection and System Health if it persists.",
            "Message unavailable: verify channel membership.",
            "Upload failed: check file policy and size.",
        ),
        ("Notifications", "People & Directory", "Troubleshooting"),
    ),
    "email": Guide(
        "Use OfficeFlow Mail and understand organization-managed SMTP or mailbox integrations.",
        "Employees with Mail access can compose internal or permitted external messages; administrators configure providers.",
        (
            "For external delivery, an administrator must configure and test an email provider in Integration Centre.",
        ),
        "Open **Communication → Mail**. Administrators configure providers under **Administration → Integration Centre → Email**.",
        (
            "Select Compose, add recipients, subject, body, and permitted attachments.",
            "Send immediately or save a draft.",
            "Review Sent for application state; external receipt still depends on the configured provider and recipient mailbox.",
            "Administrators use connection test and health information without exposing saved secrets.",
        ),
        (
            "Sent means OfficeFlow handed the message to its configured delivery path.",
            "Spam placement is a deliverability issue, not proof of application failure.",
            "SMTP secrets are write-only.",
        ),
        "The message is retained in the appropriate folder and delivery/audit status is recorded safely.",
        (
            "Email not received: check Spam, recipient spelling, provider status, sender identity, SPF/DKIM/DMARC, and delivery audit.",
            "Provider error: ask an administrator to test and reconnect it.",
            "Never paste provider passwords into support requests.",
        ),
        ("Integration Center", "Notifications", "Troubleshooting"),
    ),
    "meetings": Guide(
        "Schedule meetings, invite participants, manage agendas, capture decisions, and turn action items into tracked work.",
        "Users with meeting-create permission organize meetings; invited participants can respond according to invitation access.",
        (
            "Confirm timezone, participants, and meeting type.",
            "External email delivery requires a configured provider.",
        ),
        "Open **Communication → Meetings**. Calendar also provides scheduling entry points.",
        (
            "Select Schedule Meeting and enter title, agenda, start/end time, timezone, type, location or link, visibility, host, co-hosts, and participants.",
            "Add recurrence and attachments only when needed, then create the meeting.",
            "Participants use Accept, Decline, or Tentative from OfficeFlow or the calendar invitation.",
            "During follow-up, record attendance, decisions, notes, and action items.",
            "Link or convert an action item to a task once; update or cancel the meeting from its detail page.",
        ),
        (
            "Rescheduling keeps the calendar identity and sends an updated sequence.",
            "Cancellation sends a cancellation update rather than deleting history.",
            "Private meeting access is restricted.",
        ),
        "Invitations, ICS calendar data, notifications, reminders, calendar entries, RSVP state, and audit history update through the lifecycle.",
        (
            "Invite missing: check notification and email delivery status.",
            "Wrong time: compare organizer and participant timezones.",
            "Duplicate calendar entry: use the updated invitation with the same UID.",
        ),
        ("Calendar", "Tasks & Activities", "Notifications", "Email Delivery"),
    ),
    "calendar": Guide(
        "Navigate day, week, month, and agenda views for meetings, events, leave, and optional task deadlines.",
        "Users with Calendar permission; editing depends on ownership and event permissions.",
        ("Set the correct profile timezone.",),
        "Open **My work → Calendar**.",
        (
            "Choose Day, Week, Month, or Agenda and move to the required date.",
            "Create an event with title, start/end, timezone, calendar, recurrence, participants, location, and reminders as applicable.",
            "Open an event to edit or delete it; drag or resize where the current view offers those controls.",
            "Use filters and calendar toggles to control overlays without deleting events.",
        ),
        (
            "Away/Leave events come from approved leave and are visually distinct from meetings.",
            "Recurring exceptions change one occurrence without silently rewriting unrelated dates.",
        ),
        "Changes persist to the shared calendar and invitation updates are generated when participants are affected.",
        (
            "Event missing: clear filters and confirm calendar access.",
            "Synchronization issue: refresh provider connection and verify timezone.",
            "Cannot edit: confirm organizer or calendar permission.",
        ),
        ("Meetings", "Leave Management", "Notifications"),
    ),
    "people-directory": Guide(
        "Understand employee profiles, departments, teams, managers, employment status, and reporting relationships.",
        "Employees view directory information allowed by policy; People administrators maintain employment records.",
        ("The employee must belong to your organization.",),
        "Open **People → People**. Administrative editing is under **Administration → Users** and organization management.",
        (
            "Search by name, email, employee number, department, team, role, or status.",
            "Open an employee profile to review contact, job, manager, department, team, roles, and permitted history.",
            "Authorized administrators update employment status, reporting line, and assignments without deleting history.",
        ),
        (
            "The identity account and employee profile serve different purposes.",
            "Inactive or terminated employees remain in historical records but cannot receive new work.",
        ),
        "Changes affect authorized pickers, reporting scope, task assignment, and approval routing.",
        (
            "Employee missing: check status and filters.",
            "Wrong manager or department: ask a People administrator to correct the canonical profile.",
            "Cross-organization records are never discoverable.",
        ),
        ("Users", "Roles & Permissions", "Leave Management", "Tasks & Activities"),
    ),
    "leave": Guide(
        "Understand balances and submit, review, withdraw, adjust, and report leave accurately.",
        "Employees request their own leave; managers and HR act only within assigned approval and administration scope.",
        (
            "An active leave period and applicable leave type must exist.",
            "Required supporting documents must be ready.",
        ),
        "Open **People → Leave**. Managers use Team Leave; authorized HR administrators use Leave administration.",
        (
            "Review entitlement, accrued, carryover, pending, used, expired, and available balance.",
            "Select Request Leave; choose type, dates, half-day option where supported, reason, handover, and required document.",
            "Review calculated working days and holidays, then submit.",
            "Track Pending, Approved, Returned, Rejected, Withdrawn, or Cancelled status.",
            "Managers approve, return, or reject with a reason; employees correct a returned request and resubmit where offered.",
            "HR manages periods, holidays, types, policies, balance adjustments, carryover, and reports with audit reasons.",
        ),
        (
            "Available balance is entitlement plus valid accrual/carryover/adjustments minus used and pending leave.",
            "Half-day leave consumes the configured fraction.",
            "Approved leave creates an Away event; history is preserved after withdrawal or cancellation.",
        ),
        "Approvers are notified, balances reserve or release correctly, and approved dates become visible through authorized calendar and absence views.",
        (
            "Balance discrepancy: compare period, adjustments, pending requests, carryover, and expiry before contacting HR.",
            "Date rejected: check overlap, working-day rules, notice, blackout, and balance.",
            "Document rejected: verify supported file type and size.",
        ),
        ("Calendar", "People & Directory", "Notifications", "Leave Reports"),
    ),
    "vouchers": Guide(
        "Create or approve voucher requests, disburse funds, and audit controlled organizational spending.",
        "Employees create permitted requests; managers approve; finance staff disburse; auditors view according to separation of duties.",
        (
            "Expense category, purpose, currency, amount, and required evidence are known.",
            "The requester and approver must satisfy configured separation-of-duties rules.",
        ),
        "Open **Finance & payroll → Vouchers**.",
        (
            "Select New voucher; enter purpose, line items, category, requested amount, related task/project/meeting where available, and attachments.",
            "Save the draft, review totals, then Submit.",
            "The assigned reviewer Approves, Returns for correction, or Rejects with a reason.",
            "After approval, authorized finance staff record partial or final disbursement against a Finance account and payment reference.",
            "Open voucher detail to review comments, attachments, decisions, disbursements, ledger links, and immutable history.",
        ),
        (
            "Draft → Submitted → Returned/Rejected/Approved → Partially disbursed → Completed is the controlled lifecycle.",
            "The requester cannot approve their own voucher when separation of duties applies.",
            "Returned is correctable; Rejected closes the request unless policy permits a new one.",
        ),
        "Notifications and branded email may be sent, disbursement posts ledger transactions, and every material decision is audited.",
        (
            "Approval unavailable: check status, role, assignment, and self-approval rule.",
            "Amount mismatch: review line totals and approved amount.",
            "External email missing: check Spam and delivery audit; workflow state in OfficeFlow remains authoritative.",
        ),
        ("Finance Center", "Notifications", "Audit Trail"),
    ),
    "finance": Guide(
        "Manage distinct account, ledger transaction, and statement workflows from one coherent Finance Center.",
        "Accountants and finance administrators with the specific Finance permissions; Payroll access alone does not grant Finance access.",
        (
            "At least one Finance account is required for posting and statements.",
            "Use only authorized, verified financial records.",
        ),
        "Open **Finance & payroll → Finance**, then choose the **Accounts**, **Transactions**, or **Statements** tab inside Finance.",
        (
            "Accounts: review account name/code, type, balance, status, and open an account for its detail and related entries.",
            "Transactions: filter by text, account, reconciliation state, and date; review credit/debit, source, reference, amount, and permitted actions.",
            "Statements: select an account and date range to calculate opening balance, period credits/debits, running entries, and closing balance.",
            "Export transactions or statements to available CSV or PDF formats when Export permission is present.",
            "Use Transfer funds for paired entries and use Reversal—not editing—to correct a posted transaction.",
        ),
        (
            "Accounts are controlled ledgers, not user bank credentials.",
            "Transactions are immutable financial entries.",
            "Statements reuse the ledger and do not create a second financial record.",
        ),
        "Authorized changes update balances, reconciliation state, voucher/payment links, reports, and audit history.",
        (
            "Tabs appear empty: confirm accounts and date filters.",
            "Export denied: request Finance export permission.",
            "Balance concern: inspect opening balance, period entries, reversals, and reconciliation before escalating.",
        ),
        ("Vouchers", "Payroll & Payslips", "Reports & Management Intelligence", "Audit Trail"),
    ),
    "payroll": Guide(
        "Configure salary rules, prepare and review payroll, post payment, and securely access payslips.",
        "Employees see their own payslips; Payroll officers and approvers see only the administration tabs granted to their roles.",
        (
            "Employees have active salary structures for the period.",
            "Components, statutory rules, and payment account are configured before preparation.",
        ),
        "Open **Finance & payroll → My Payroll**. Employees use Overview and My Payslips; authorized officers also see Payroll Runs, Salary Structures, Components, Statutory Rules, Loans, and Reports.",
        (
            "Create or confirm the payroll period and effective-dated salary structures.",
            "Configure earnings and deductions such as basic pay, allowances, PAYE, pension, NHF, loans, or adjustments according to policy.",
            "Prepare payroll, review employee count, gross pay, deductions, net pay, employer cost, validation issues, and results.",
            "Submit and approve through the permitted workflow; the preparer must not bypass required approval separation.",
            "Post payment to the selected Finance account and confirm the completed state.",
            "Employees open My Payslips and use Download Payslip through the authorized secure endpoint.",
        ),
        (
            "Gross pay is earnings before deductions; net pay is the amount payable after deductions.",
            "PAYE is income tax, pension and NHF follow configured statutory rules, and employer cost may exceed gross pay.",
            "Payslips are confidential and never visible through another employee's account.",
        ),
        "Approved payment creates controlled finance records, makes eligible payslips available, and records workflow and audit history.",
        (
            "Employee missing: verify active employment and effective salary structure.",
            "Download denied: sign in as the payslip owner or an explicitly authorized payroll role.",
            "Unexpected amount: review component effective dates, statutory configuration, and adjustments before approval.",
        ),
        (
            "Finance Center",
            "People & Directory",
            "Reports & Management Intelligence",
            "Security & Access",
        ),
    ),
    "reporting-intelligence": Guide(
        "Generate and submit weekly report, monthly, custom-date, project, team, and department reporting from recorded work.",
        "Employees create and submit their reports; managers review authorized staff reports; broader intelligence follows reporting permissions.",
        (
            "Record daily activities, task outcomes, meetings, blockers, and project updates before generation.",
        ),
        "Open **Intelligence → Reports & Intelligence**. Project reports are also available from an authorized project.",
        (
            "Choose weekly, monthly, or custom dates and generate a draft from actual OfficeFlow records.",
            "Review every section; edit narrative explanations without fabricating source metrics.",
            "Submit the report manually, or confirm automatic submission policy where configured.",
            "Managers review, return with guidance, or finalize according to permissions.",
            "Correct a returned report, regenerate only when source data must change, then resubmit.",
            "Use team, department, project, and management intelligence filters only within authorized scope; export PDF, CSV, or Excel where offered.",
        ),
        (
            "A draft is reviewable and not final.",
            "Automatic submission sends the generated report under configured policy; it does not invent missing activity.",
            "Returned reports remain editable; finalized records preserve review history.",
        ),
        "Status, reviewer feedback, timestamps, exports, and audit events remain attached to the report version.",
        (
            "Report not generated: confirm date range and source records.",
            "Missing figures: update the originating task/activity/meeting rather than typing false metrics.",
            "Manager cannot see report: verify reporting line, department, and review permission.",
        ),
        ("Tasks & Activities", "Projects", "People & Directory", "Troubleshooting"),
    ),
    "users": Guide(
        "Create and maintain user accounts and employee access without bypassing employment records or security controls.",
        "System and organization administrators with user-management permission.",
        ("Confirm the person's work email, department, manager, role, team, and workspace.",),
        "Open **Administration → Users**.",
        (
            "Search first to avoid duplicate accounts.",
            "Select Create User and enter identity, contact, employment, team/workspace, role, and status details.",
            "Deliver the generated account-ready email or temporary password through the configured secure process.",
            "Require first-login password rotation; edit profile or role assignments when responsibilities change.",
            "Disable rather than delete when access must stop but history must remain; reactivate only after authorization.",
        ),
        (
            "One OfficeFlow account belongs to one organization.",
            "Disabling blocks access without erasing historical ownership.",
            "Roles grant permissions; menu visibility follows those permissions dynamically.",
        ),
        "The user becomes available to authorized directory, assignment, approval, and collaboration workflows; changes are audited.",
        (
            "Invitation not received: check provider delivery and Spam.",
            "Duplicate email: edit the existing organization account.",
            "User still lacks a menu: verify role permission, feature flag, and menu publication.",
        ),
        ("People & Directory", "Roles & Permissions", "Email Delivery", "Audit Trail"),
    ),
    "roles-permissions": Guide(
        "Build least-privilege custom roles and understand how permissions control APIs, menus, and actions.",
        "Administrators with role-management permission.",
        ("Understand the user's job responsibilities and separation-of-duties requirements.",),
        "Open **Administration → Roles & Permissions**.",
        (
            "Review system roles before creating a custom role.",
            "Create or clone a role, give it a clear purpose, then search permissions by module.",
            "Use module select-all or clear-all carefully and review View, Create, Edit, Delete, Manage, and Export capabilities.",
            "Save, assign members, and verify the resulting menu and action access with an appropriate test user.",
            "Edit custom roles as duties change; protected system roles cannot be silently weakened or deleted.",
        ),
        (
            "Frontend visibility is not the authorization boundary; APIs enforce permissions too.",
            "A feature flag can hide a permitted module.",
            "Finance, payroll, HR, audit, and platform access should remain separated.",
        ),
        "Permission recalculation updates accessible navigation and actions; the change and actor are recorded in audit history.",
        (
            "Permission saved but menu missing: check feature and menu configuration.",
            "Access Denied: verify the exact action permission and record scope.",
            "Role cannot be edited: it may be a protected system role.",
        ),
        ("Users", "Platform Management", "Menu Management", "Security & Access"),
    ),
    "settings": Guide(
        "Configure organization branding, profile, timezone, working hours, defaults, security, retention, and operational limits.",
        "Organization administrators; platform-wide controls remain restricted to Platform Super Admin.",
        ("Document the intended policy and impact before changing production settings.",),
        "Open **Administration → Organization** and the relevant settings area.",
        (
            "Review company profile, branding, timezone, working hours, and calendar/meeting defaults.",
            "Configure password, upload, retention, compliance, and notification policies with affected owners.",
            "Preview high-impact changes, save, confirm feedback, and review the resulting audit event.",
        ),
        (
            "Organization settings apply only to the current tenant.",
            "Retention and security reductions may require compliance approval.",
        ),
        "New defaults affect future actions unless the setting explicitly migrates existing records.",
        (
            "Setting unavailable: verify administrator permission and feature status.",
            "Unexpected times: align organization and user timezones.",
            "Branding not visible: refresh after confirming the published configuration.",
        ),
        ("Platform Management", "Integration Center", "Security & Access", "Audit Trail"),
    ),
    "integrations": Guide(
        "Connect and monitor supported email, calendar, storage, identity, and collaboration providers without exposing secrets.",
        "Authorized administrators.",
        (
            "Obtain provider credentials and required scopes through the provider's approved process.",
        ),
        "Open **Administration → Integration Centre**, choose a provider, and open Setup.",
        (
            "Review overview, prerequisites, scopes, permissions, rate limits, and redirect/webhook requirements.",
            "Enter credentials in write-only fields and save.",
            "Run Connection Test, confirm health, and complete a controlled functional test.",
            "Monitor logs, sync, token expiry, usage, and audit; rotate secrets or reconnect when required.",
            "Disconnect only after assessing dependent workflows.",
        ),
        (
            "Configured does not always mean externally delivered.",
            "Saved secrets are never displayed again.",
            "Provider availability and feature enablement both affect navigation.",
        ),
        "The provider status and System Health reflect the tested connection; integrations emit redacted audit records.",
        (
            "Test fails: verify DNS, TLS, endpoint, scopes, sender identity, and provider policy.",
            "Token expired: reconnect or rotate according to provider guidance.",
            "Never include a secret in logs or support requests.",
        ),
        ("Email Delivery", "System Health", "Security & Access"),
    ),
    "security": Guide(
        "Protect accounts with strong passwords, MFA, session/device review, least privilege, and auditable administration.",
        "All users manage their own security; security administrators review organization controls and audit records.",
        ("Use a trusted device and current browser.",),
        "Open **Profile → Security** for personal controls and **Administration → Audit/System Health** for authorized oversight.",
        (
            "Change compromised passwords immediately and enable two-factor authentication when available.",
            "Review active sessions, devices, login history, connected accounts, and API tokens; revoke anything unfamiliar.",
            "Administrators review authentication, permission, configuration, finance, payroll, and support audit events using filters and export where authorized.",
        ),
        (
            "Audit logs are immutable compliance records; activity timelines are user-facing context.",
            "A 403 Access Denied is authorization working as designed.",
        ),
        "Revocation removes the affected session or credential while preserving security history.",
        (
            "MFA unavailable: confirm organization policy and authenticator compatibility.",
            "Suspicious session: revoke it, change password, and contact an administrator.",
            "Audit entry missing: confirm event type, tenant, date filters, and retention.",
        ),
        ("Profile & Security", "Roles & Permissions", "System Health", "Troubleshooting"),
    ),
    "troubleshooting": Guide(
        "Diagnose common OfficeFlow problems safely before escalating to Support.",
        "All users; administrative diagnostics require the corresponding permission.",
        ("Record the page, time, expected outcome, and safe error text without sensitive values.",),
        "Open **Help & Support → Troubleshooting**. Administrators may also inspect System Health and Audit.",
        (
            "Cannot log in or change password: confirm email, request a fresh reset link, meet password rules, and remember links are single-use and expire after 20 minutes.",
            "Access Denied or missing menu: verify role, feature flag, menu publication, record scope, and employment status.",
            "Notifications or email missing: review preferences, quiet hours, unread filters, provider health, Spam, and delivery audit.",
            "Attachment upload failure: verify authorization, file type, size, filename, and connection.",
            "Report not generated: confirm source records and period; leave discrepancy: inspect period, pending requests, carryover, expiry, and adjustments.",
            "Payslip or Finance export failure: confirm ownership/export permission, account/date selection, and browser download handling.",
            "Calendar synchronization: confirm timezone, provider connection, event filters, and latest invitation update.",
            "Retry in a current Chrome, Edge, Firefox, or Safari release; clear only site data if Support recommends it.",
        ),
        (
            "Do not repeatedly submit financial, payroll, leave, or meeting actions after an uncertain response.",
            "Do not send passwords, reset tokens, medical evidence, payslips, bank details, or provider secrets to Support.",
        ),
        "A successful retry completes the workflow once; unresolved issues should be raised with page context and a safe description.",
        (
            "If work remains blocked, choose Help & Support → Get support → Report an Issue.",
            "For access or policy questions, choose Request Help and identify the required business outcome.",
            "Administrators should include a relevant audit reference, not confidential record contents.",
        ),
        ("Quick Start Guide", "Security & Access", "System Health", "Integration Center"),
    ),
}


ROLE_PATHS: dict[str, tuple[str, tuple[str, ...]]] = {
    "employee-learning-path": (
        "Employee learning path",
        (
            "Quick Start Guide",
            "Tasks & Activities",
            "Meetings",
            "Calendar",
            "Leave Management",
            "Payroll & Payslips",
            "Reports & Management Intelligence",
        ),
    ),
    "manager-learning-path": (
        "Manager learning path",
        (
            "Quick Start Guide",
            "People & Directory",
            "Tasks & Activities",
            "Leave Management",
            "Reports & Management Intelligence",
            "Meetings",
        ),
    ),
    "project-manager-learning-path": (
        "Project Manager learning path",
        (
            "Quick Start Guide",
            "Projects",
            "Tasks & Activities",
            "Meetings",
            "Reports & Management Intelligence",
        ),
    ),
    "finance-learning-path": (
        "Finance and Accountant learning path",
        (
            "Quick Start Guide",
            "Vouchers",
            "Finance Center",
            "Reports & Management Intelligence",
            "Audit Trail",
        ),
    ),
    "payroll-learning-path": (
        "Payroll Officer learning path",
        (
            "Quick Start Guide",
            "People & Directory",
            "Payroll & Payslips",
            "Finance Center",
            "Audit Trail",
        ),
    ),
    "people-admin-learning-path": (
        "HR and People Administrator learning path",
        (
            "Quick Start Guide",
            "Users",
            "People & Directory",
            "Leave Management",
            "Roles & Permissions",
            "Audit Trail",
        ),
    ),
    "system-admin-learning-path": (
        "System Administrator learning path",
        (
            "Quick Start Guide",
            "Users",
            "Roles & Permissions",
            "Organization Settings",
            "Integration Center",
            "Security & Access",
            "System Health",
            "Help Centre content management",
        ),
    ),
}


def baseline_content(slug: str, title: str, category: str) -> tuple[str, str]:
    if slug in GUIDES:
        guide = GUIDES[slug]
        return guide.summary, _body(title, guide)
    if slug in ROLE_PATHS:
        path_title, guides = ROLE_PATHS[slug]
        sequence = "\n".join(f"{index}. **{guide}**" for index, guide in enumerate(guides, 1))
        summary = f"A permission-aware onboarding sequence for the {path_title.lower()}."
        return summary, (
            f"# {path_title}\n\n{summary}\n\n## How to use this path\n\n"
            "Open each guide in order and practise only the actions visible to your role. "
            "Examples never grant access to confidential records.\n\n## Recommended sequence\n\n"
            f"{sequence}\n\n## Completion check\n\n"
            "Confirm you can find your daily workspace, complete your core workflow, understand status and notifications, "
            "and know how to request help without sharing sensitive data.\n\n"
            "> If a listed module is not visible, skip it and ask your administrator whether it is required for your job."
        )
    summary = f"Learn how OfficeFlow {title.lower()} works."
    return summary, (
        f"# {title}\n\n{summary}\n\n## Purpose\n\n"
        f"This {category.lower()} guide explains the supported OfficeFlow workflow.\n\n"
        "## Access\n\nAvailability follows your role, record scope, and enabled features.\n\n"
        "## Get help\n\nOpen **Help & Support → Get support** if the page guidance and Troubleshooting guide do not resolve the issue."
    )
