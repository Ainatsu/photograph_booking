import type { CapacitorConfig } from '@capacitor/cli'

// 本地后端是 HTTP：同步 Android 工程前临时设 CAPACITOR_LOCAL_HTTP=true；
// 正式打包连 HTTPS API 时不要设，工程会恢复禁止明文与混合内容。
const allowLocalHttp = process.env.CAPACITOR_LOCAL_HTTP === 'true'

const config: CapacitorConfig = {
  /**
   * appId 与 ../mobile-app/capacitor.config.ts 的 com.photographerbooking.mobile 不同，
   * 否则两个应用装在同一台设备上会互相覆盖。
   *
   * 注意：如果本应用将来要**取代**原移动端（而不是并存），appId 必须改回
   * com.photographerbooking.mobile —— 应用商店的更新依赖 appId 稳定，换 ID 会被当成新应用。
   * 那种情况下也要先确认原应用已下线。
   */
  appId: 'com.photographerbooking.mobile.redesign',
  appName: '约拍',
  webDir: 'dist',
  backgroundColor: '#F2F2F7',
  android: {
    backgroundColor: '#F2F2F7',
    allowMixedContent: allowLocalHttp,
  },
  server: {
    cleartext: allowLocalHttp,
  },
  plugins: {
    StatusBar: {
      style: 'DARK',
      backgroundColor: '#F2F2F7',
    },
    Keyboard: {
      resize: 'body',
    },
  },
}

export default config
