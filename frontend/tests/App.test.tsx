import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import App from '../src/App'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

test('shows the backend status when the health check succeeds', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    json: async () => ({ status: 'ok' }),
  }))

  render(<App />)

  screen.getByRole('heading', { name: 'SecondOpinion' })
  await screen.findByText('Backend status: ok')
  expect(fetch).toHaveBeenCalledWith('/api/health')
})

test('shows an error when the backend cannot be reached', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))

  render(<App />)

  await screen.findByText('Backend status: backend unreachable')
})

test('mounts the app in the page root', async () => {
  document.body.innerHTML = '<div id="root"></div>'
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    json: async () => ({ status: 'ok' }),
  }))

  await import('../src/main')

  await screen.findByRole('heading', { name: 'SecondOpinion' })
  await screen.findByText('Backend status: ok')
})
