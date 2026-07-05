import { createApp } from 'vue'
import {
  ElAlert,
  ElAside,
  ElButton,
  ElCard,
  ElCol,
  ElContainer,
  ElDescriptions,
  ElDescriptionsItem,
  ElForm,
  ElFormItem,
  ElHeader,
  ElInput,
  ElInputNumber,
  ElMain,
  ElMenu,
  ElMenuItem,
  ElOption,
  ElRow,
  ElSelect,
  ElSwitch,
  ElTabPane,
  ElTable,
  ElTableColumn,
  ElTabs
} from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import { router } from './router'
import './style.css'

const app = createApp(App)

for (const component of [
  ElAlert,
  ElAside,
  ElButton,
  ElCard,
  ElCol,
  ElContainer,
  ElDescriptions,
  ElDescriptionsItem,
  ElForm,
  ElFormItem,
  ElHeader,
  ElInput,
  ElInputNumber,
  ElMain,
  ElMenu,
  ElMenuItem,
  ElOption,
  ElRow,
  ElSelect,
  ElSwitch,
  ElTabPane,
  ElTable,
  ElTableColumn,
  ElTabs
]) {
  app.use(component)
}

app.use(router).mount('#app')
