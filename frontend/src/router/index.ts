import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('../views/Login.vue'),
      meta: { noAuth: true }
    },
    {
      path: '/',
      redirect: '/data'
    },
    {
      path: '/',
      component: () => import('../layouts/MainLayout.vue'),
      children: [
        {
          path: 'data',
          name: 'Data',
          component: () => import('../views/DataView.vue')
        },
        {
          path: 'bi',
          name: 'BI',
          component: () => import('../views/BIView.vue')
        },
        {
          path: 'chat',
          name: 'Chat',
          component: () => import('../views/ChatView.vue')
        },
        {
          path: 'data/relations',
          name: 'Relations',
          component: () => import('../views/RelationsView.vue')
        },
        {
          path: 'admin',
          name: 'Admin',
          component: () => import('../views/AdminView.vue')
        },
        {
          path: 'admin/logs',
          name: 'AdminLogs',
          component: () => import('../views/AdminLogsView.vue')
        },
        {
          path: 'admin/llm-config',
          name: 'AdminLLMConfig',
          component: () => import('../views/AdminLLMConfigView.vue')
        },
        {
          path: 'admin/spaces',
          name: 'AdminSpaces',
          component: () => import('../views/AdminSpacesView.vue')
        }
      ]
    }
  ]
})

// 路由守卫 - 登录状态检查
router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('xlsx-bi-token')

  if (to.meta.noAuth) {
    if (token) {
      next('/data')
      return
    }
    next()
    return
  }

  if (!token) {
    next('/login')
    return
  }

  next()
})

export default router
