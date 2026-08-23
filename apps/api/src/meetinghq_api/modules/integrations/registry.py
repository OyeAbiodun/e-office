"""Provider metadata used by the Integration Center."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderDefinition:
    key: str
    name: str
    category: str
    description: str
    auth_type: str


PROVIDERS = (
    ProviderDefinition(
        "microsoft-365",
        "Microsoft 365",
        "Productivity",
        "Mail, calendar, files, and identity services.",
        "oauth",
    ),
    ProviderDefinition(
        "google-workspace",
        "Google Workspace",
        "Productivity",
        "Mail, calendar, storage, and directory services.",
        "oauth",
    ),
    ProviderDefinition(
        "gmail", "Gmail", "Email", "Google Workspace email delivery and synchronization.", "oauth"
    ),
    ProviderDefinition(
        "outlook", "Outlook", "Email", "Microsoft Outlook mail synchronization.", "oauth"
    ),
    ProviderDefinition("yahoo", "Yahoo Mail", "Email", "Yahoo mailbox synchronization.", "oauth"),
    ProviderDefinition("smtp", "SMTP", "Email", "Standards-based outbound email delivery.", "smtp"),
    ProviderDefinition("imap", "IMAP", "Email", "Standards-based mailbox synchronization.", "imap"),
    ProviderDefinition(
        "google-calendar",
        "Google Calendar",
        "Calendar",
        "Two-way Google Calendar synchronization.",
        "oauth",
    ),
    ProviderDefinition(
        "microsoft-calendar",
        "Microsoft Calendar",
        "Calendar",
        "Microsoft 365 calendar synchronization.",
        "oauth",
    ),
    ProviderDefinition(
        "apple-calendar",
        "Apple Calendar",
        "Calendar",
        "CalDAV-compatible Apple calendar access.",
        "caldav",
    ),
    ProviderDefinition(
        "google-drive",
        "Google Drive",
        "Storage",
        "Google Workspace document and file storage.",
        "oauth",
    ),
    ProviderDefinition("onedrive", "OneDrive", "Storage", "Microsoft cloud file storage.", "oauth"),
    ProviderDefinition("dropbox", "Dropbox", "Storage", "Dropbox team file storage.", "oauth"),
    ProviderDefinition("box", "Box", "Storage", "Enterprise content and file storage.", "oauth"),
    ProviderDefinition(
        "amazon-s3", "Amazon S3", "Storage", "S3-compatible durable object storage.", "storage"
    ),
    ProviderDefinition(
        "azure-blob", "Azure Blob", "Storage", "Microsoft Azure object storage.", "storage"
    ),
    ProviderDefinition(
        "openai", "OpenAI", "AI", "OpenAI models for MeetingHQ intelligence.", "api_key"
    ),
    ProviderDefinition(
        "azure-openai", "Azure OpenAI", "AI", "Enterprise OpenAI models hosted in Azure.", "api_key"
    ),
    ProviderDefinition("anthropic", "Anthropic", "AI", "Anthropic Claude model access.", "api_key"),
    ProviderDefinition("gemini", "Google Gemini", "AI", "Google Gemini model access.", "api_key"),
    ProviderDefinition(
        "microsoft-teams",
        "Microsoft Teams",
        "Meetings",
        "Teams meetings and collaboration.",
        "oauth",
    ),
    ProviderDefinition("zoom", "Zoom", "Meetings", "Zoom meeting creation and joining.", "oauth"),
    ProviderDefinition(
        "google-meet", "Google Meet", "Meetings", "Google Meet conference creation.", "oauth"
    ),
    ProviderDefinition(
        "slack", "Slack", "Collaboration", "Slack notifications and meeting workflows.", "oauth"
    ),
    ProviderDefinition(
        "rest-api", "REST APIs", "Developer", "External REST service connectivity.", "token"
    ),
    ProviderDefinition(
        "webhooks", "Webhooks", "Developer", "Signed outbound event delivery.", "webhook"
    ),
)

PROVIDER_MAP = {provider.key: provider for provider in PROVIDERS}
