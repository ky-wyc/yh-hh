import { createRouter, createWebHistory } from 'vue-router'
import LoginView from './views/LoginView.vue'
import DashboardView from './views/DashboardView.vue'
import GroupsView from './views/GroupsView.vue'
import KeywordRulesView from './views/KeywordRulesView.vue'
import LlmSettingsView from './views/LlmSettingsView.vue'
import LogsView from './views/LogsView.vue'
import { hasToken } from './auth'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginView },
    { path: '/', component: DashboardView, meta: { requiresAuth: true } },
    { path: '/groups', component: GroupsView, meta: { requiresAuth: true } },
    { path: '/keywords', component: KeywordRulesView, meta: { requiresAuth: true } },
    { path: '/llm', component: LlmSettingsView, meta: { requiresAuth: true } },
    { path: '/logs', component: LogsView, meta: { requiresAuth: true } }
  ]
})

router.beforeEach((to) => {
  if (to.meta.requiresAuth && !hasToken()) {
    return '/login'
  }
  if (to.path === '/login' && hasToken()) {
    return '/'
  }
  return true
})
