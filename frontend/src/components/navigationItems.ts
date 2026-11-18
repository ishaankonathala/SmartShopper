import {
  Bookmark,
  Clock3,
  Compass,
  SlidersHorizontal,
  Sparkles,
  type LucideIcon,
} from 'lucide-react'

export type AppNavigationItem = {
  label: string
  to: string
  icon: LucideIcon
}

export const APP_NAV_ITEMS: AppNavigationItem[] = [
  { label: 'Shop with AI', to: '/', icon: Sparkles },
  { label: 'Discover', to: '/discover', icon: Compass },
  { label: 'My Preferences', to: '/preferences', icon: SlidersHorizontal },
  { label: 'Shopping History', to: '/history', icon: Clock3 },
  { label: 'Saved Products', to: '/saved', icon: Bookmark },
]
