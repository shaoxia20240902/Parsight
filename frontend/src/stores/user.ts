import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const TOKEN_KEY = 'xlsx-bi-token'
const ADMIN_KEY = 'xlsx-bi-is-admin'
const USERNAME_KEY = 'xlsx-bi-username'
const DISPLAY_NAME_KEY = 'xlsx-bi-display-name'

export const useUserStore = defineStore('user', () => {
  const token = ref<string>(localStorage.getItem(TOKEN_KEY) || '')
  const username = ref<string>(localStorage.getItem(USERNAME_KEY) || '')
  const displayName = ref<string>(localStorage.getItem(DISPLAY_NAME_KEY) || '')
  const isAdmin = ref<boolean>(localStorage.getItem(ADMIN_KEY) === 'true')

  const isLoggedIn = computed(() => !!token.value)

  const setToken = (t: string) => {
    token.value = t
    localStorage.setItem(TOKEN_KEY, t)
  }

  const setUser = (name: string, display: string, admin: boolean = false) => {
    username.value = name
    displayName.value = display
    isAdmin.value = admin
    localStorage.setItem(USERNAME_KEY, name)
    localStorage.setItem(DISPLAY_NAME_KEY, display)
    localStorage.setItem(ADMIN_KEY, String(admin))
  }

  const logout = () => {
    token.value = ''
    username.value = ''
    displayName.value = ''
    isAdmin.value = false
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(ADMIN_KEY)
    localStorage.removeItem(USERNAME_KEY)
    localStorage.removeItem(DISPLAY_NAME_KEY)
  }

  return {
    token,
    username,
    displayName,
    isAdmin,
    isLoggedIn,
    setToken,
    setUser,
    logout
  }
})
