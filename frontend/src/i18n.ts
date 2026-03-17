import { createI18n } from 'vue-i18n'
import { zhCN, en } from './locales'

function getDefaultLocale(): string {
  const saved = localStorage.getItem('locale')
  if (saved) return saved
  const browserLang = navigator.language
  return browserLang.startsWith('zh') ? 'zh-CN' : 'en'
}

const i18n = createI18n({
  legacy: false,
  locale: getDefaultLocale(),
  fallbackLocale: 'zh-CN',
  messages: {
    'zh-CN': zhCN,
    en,
  },
})

export default i18n
