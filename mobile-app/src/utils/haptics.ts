import { Haptics, ImpactStyle } from '@capacitor/haptics'

export function tapHaptic(style: ImpactStyle = ImpactStyle.Light): void {
  void Haptics.impact({ style }).catch(() => undefined)
}
