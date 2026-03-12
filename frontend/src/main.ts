import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Aura from '@primevue/themes/aura'
import { definePreset } from '@primevue/themes'
import ToastService from 'primevue/toastservice'
import ConfirmationService from 'primevue/confirmationservice'
import Tooltip from 'primevue/tooltip'
import 'primeicons/primeicons.css'
import 'highlight.js/styles/github-dark.css'

import App from './App.vue'
import router from './router'
import './style.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)

const CapeCodPreset = definePreset(Aura, {
    semantic: {
        primary: {
            50: '#fafafa',
            100: '#f4f5f5',
            200: '#e4e6e7',
            300: '#d4d7d8',
            400: '#a0a8ab',
            500: '#70787b',
            600: '#51595c',
            700: '#393f41',
            800: '#27292a',
            900: '#181a1b',
            950: '#090b0b',
        },
        colorScheme: {
            light: {
                surface: {
                    0: '#ffffff',
                    50: '#fafafa',
                    100: '#f4f5f5',
                    200: '#e4e6e7',
                    300: '#d4d7d8',
                    400: '#a0a8ab',
                    500: '#70787b',
                    600: '#51595c',
                    700: '#393f41',
                    800: '#27292a',
                    900: '#181a1b',
                    950: '#090b0b',
                }
            },
            dark: {
                surface: {
                    0: '#ffffff',
                    50: '#fafafa',
                    100: '#f4f5f5',
                    200: '#e4e6e7',
                    300: '#d4d7d8',
                    400: '#a0a8ab',
                    500: '#70787b',
                    600: '#51595c',
                    700: '#393f41',
                    800: '#27292a',
                    900: '#181a1b',
                    950: '#090b0b',
                }
            }
        }
    }
});

app.use(PrimeVue, {
  theme: {
    preset: CapeCodPreset,
    options: {
      darkModeSelector: '.dark-mode',
      cssLayer: false,
    },
  },
})

app.use(ToastService)
app.use(ConfirmationService)
app.directive('tooltip', Tooltip)

app.mount('#app')
