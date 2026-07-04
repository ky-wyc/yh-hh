import { createRouter, createWebHistory } from 'vue-router'
import LoginView from './views/LoginView.vue'
import DashboardView from './views/DashboardView.vue'
import GroupsView from './views/GroupsView.vue'
import LlmSettingsView from './views/LlmSettingsView.vue'
import LogsView from './views/LogsView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginView },
    { path: '/', component: DashboardView },
    { path: '/groups', component: GroupsView },
    { path: '/llm', component: LlmSettingsView },
    { path: '/logs', component: LogsView }
  ]
})

