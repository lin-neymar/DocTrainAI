import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

import App from './App.vue'
import router from './router'
import './styles/theme.css'
import {
  applyThemePrimary,
  readStoredThemePrimary,
} from '@/utils/theme'

// 首屏先用本地缓存主题色，避免闪回默认蓝；登录后 /me 再校准
applyThemePrimary(readStoredThemePrimary())

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })
app.mount('#app')

