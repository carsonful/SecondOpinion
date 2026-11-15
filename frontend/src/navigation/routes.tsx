import { AnchorHTMLAttributes, MouseEvent } from 'react'

export const ROUTES = {
  home: { path: '/', title: 'Second Opinion | Research health claims' },
  'how-it-works': { path: '/how-it-works', title: 'How it works | Second Opinion' },
  about: { path: '/about', title: 'About | Second Opinion' },
} as const

export type Page = keyof typeof ROUTES
export type CurrentPage = Page | 'not-found'

export function pageAt(pathname: string): CurrentPage {
  const path = pathname.replace(/\/+$/, '') || '/'
  return (Object.keys(ROUTES) as Page[]).find(page => ROUTES[page].path === path) ?? 'not-found'
}

interface PageLinkProps extends Omit<AnchorHTMLAttributes<HTMLAnchorElement>, 'href' | 'onClick'> {
  page: Page
  onNavigate: (page: Page) => void
}

/** Ordinary clicks use the SPA; browser gestures retain normal link behavior. */
export function PageLink({ page, onNavigate, children, ...props }: PageLinkProps) {
  function follow(event: MouseEvent<HTMLAnchorElement>) {
    if (
      event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey
      || event.shiftKey || event.altKey || event.currentTarget.hasAttribute('download')
      || (event.currentTarget.target && event.currentTarget.target !== '_self')
    ) return
    event.preventDefault()
    onNavigate(page)
  }

  return <a {...props} href={ROUTES[page].path} onClick={follow}>{children}</a>
}
