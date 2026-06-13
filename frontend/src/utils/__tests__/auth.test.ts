import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
  getAuthToken,
  setAuthToken,
  clearAuthToken,
  getAuthHeaders,
  handleUnauthorized,
} from '../auth'

const TOKEN_KEY = 'xlsx-bi-token'

describe('auth utils', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('getAuthToken returns null when token is missing', () => {
    expect(getAuthToken()).toBeNull()
  })

  it('setAuthToken stores token in localStorage', () => {
    setAuthToken('test-token')
    expect(localStorage.getItem(TOKEN_KEY)).toBe('test-token')
  })

  it('clearAuthToken removes token from localStorage', () => {
    setAuthToken('test-token')
    clearAuthToken()
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
  })

  it('getAuthHeaders returns empty object when token is missing', () => {
    expect(getAuthHeaders()).toEqual({})
  })

  it('getAuthHeaders returns Bearer header when token exists', () => {
    setAuthToken('test-token')
    expect(getAuthHeaders()).toEqual({ Authorization: 'Bearer test-token' })
  })

  it('handleUnauthorized clears token and redirects to login', () => {
    const locationAssign = vi.fn()
    const mockLocation = { ...window.location }
    Object.defineProperty(mockLocation, 'href', {
      get: () => '',
      set: (value: string) => locationAssign(value),
      configurable: true,
    })
    vi.stubGlobal('location', mockLocation)
    setAuthToken('test-token')
    handleUnauthorized()
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
    expect(locationAssign).toHaveBeenCalledWith('/login')
    vi.unstubAllGlobals()
  })
})
