import type { CapacitorConfig } from '@capacitor/cli'

const allowLocalHttp = process.env.CAPACITOR_LOCAL_HTTP === 'true'

const config: CapacitorConfig = {
  appId: 'com.photographerbooking.mobile',
  appName: '约拍',
  webDir: 'dist',
  backgroundColor: '#FAF7F2',
  android: {
    backgroundColor: '#FAF7F2',
    allowMixedContent: allowLocalHttp,
  },
  server: {
    cleartext: allowLocalHttp,
  },
  plugins: {
    StatusBar: {
      style: 'DARK',
      backgroundColor: '#FAF7F2',
    },
    Keyboard: {
      resize: 'body',
    },
  },
}

export default config
