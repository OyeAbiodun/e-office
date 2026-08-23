import {
  SiAnthropic,
  SiApple,
  SiBox,
  SiCloudflare,
  SiDocker,
  SiDropbox,
  SiGithub,
  SiGitlab,
  SiGmail,
  SiGoogle,
  SiGooglecalendar,
  SiGoogledrive,
  SiGooglegemini,
  SiGooglemeet,
  SiKubernetes,
  SiStripe,
  SiZoom,
} from '@icons-pack/react-simple-icons'
import { BiLogoMicrosoftTeams } from 'react-icons/bi'
import { FaAws, FaMicrosoft, FaSlack, FaYahoo } from 'react-icons/fa6'
import { PiMicrosoftOutlookLogoFill } from 'react-icons/pi'
import { SiOpenai } from 'react-icons/si'
import { TbBrandAzure, TbBrandOnedrive } from 'react-icons/tb'
import type { IconType } from 'react-icons'
import { Braces, Cloud, Mail, Webhook } from 'lucide-react'
import type { ComponentType, SVGProps } from 'react'

const simpleIcons: Record<string, ComponentType<SVGProps<SVGSVGElement>>> = {
  anthropic: SiAnthropic,
  'apple-calendar': SiApple,
  box: SiBox,
  cloudflare: SiCloudflare,
  docker: SiDocker,
  dropbox: SiDropbox,
  github: SiGithub,
  gitlab: SiGitlab,
  gmail: SiGmail,
  'google-workspace': SiGoogle,
  'google-calendar': SiGooglecalendar,
  'google-drive': SiGoogledrive,
  gemini: SiGooglegemini,
  'google-meet': SiGooglemeet,
  kubernetes: SiKubernetes,
  stripe: SiStripe,
  zoom: SiZoom,
}

const recognizedIcons: Record<string, IconType> = {
  'microsoft-365': FaMicrosoft,
  outlook: PiMicrosoftOutlookLogoFill,
  yahoo: FaYahoo,
  'microsoft-calendar': PiMicrosoftOutlookLogoFill,
  onedrive: TbBrandOnedrive,
  'amazon-s3': FaAws,
  'azure-blob': TbBrandAzure,
  openai: SiOpenai,
  'azure-openai': TbBrandAzure,
  'microsoft-teams': BiLogoMicrosoftTeams,
  slack: FaSlack,
}

const colors: Record<string, string> = {
  anthropic: '#191919',
  'apple-calendar': '#555555',
  box: '#0061D5',
  cloudflare: '#F38020',
  docker: '#2496ED',
  dropbox: '#0061FF',
  github: '#181717',
  gitlab: '#FC6D26',
  gmail: '#EA4335',
  'google-workspace': '#4285F4',
  'google-calendar': '#4285F4',
  'google-drive': '#0F9D58',
  gemini: '#8E75B2',
  'google-meet': '#00897B',
  kubernetes: '#326CE5',
  stripe: '#635BFF',
  zoom: '#0B5CFF',
  'microsoft-365': '#F25022',
  outlook: '#0078D4',
  yahoo: '#6001D2',
  'microsoft-calendar': '#0078D4',
  onedrive: '#0078D4',
  'amazon-s3': '#FF9900',
  'azure-blob': '#0078D4',
  openai: '#10A37F',
  'azure-openai': '#0078D4',
  'microsoft-teams': '#6264A7',
  slack: '#4A154B',
}

export function ProviderLogo({
  provider,
  className = 'size-7',
}: {
  provider: string
  className?: string
}) {
  const Icon = simpleIcons[provider]
  if (Icon)
    return (
      <Icon
        aria-label={`${provider.replaceAll('-', ' ')} logo`}
        className={className}
        color={colors[provider]}
        role="img"
      />
    )
  const RecognizedIcon = recognizedIcons[provider]
  if (RecognizedIcon)
    return (
      <RecognizedIcon
        aria-label={`${provider.replaceAll('-', ' ')} logo`}
        className={className}
        color={colors[provider]}
        role="img"
      />
    )
  if (provider === 'webhooks')
    return <Webhook aria-label="Webhooks" className={className} role="img" />
  if (provider === 'rest-api')
    return <Braces aria-label="REST API" className={className} role="img" />
  if (provider === 'smtp' || provider === 'imap')
    return (
      <Mail
        aria-label={provider.toUpperCase()}
        className={className}
        role="img"
      />
    )
  return (
    <Cloud
      aria-label={`${provider} provider`}
      className={className}
      role="img"
    />
  )
}
