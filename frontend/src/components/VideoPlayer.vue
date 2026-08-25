<template>
  <div class="video-player" :class="{ 'is-fullscreen': isFullscreen }" ref="playerRef">
    <!-- 视频元素 -->
    <video
      ref="videoRef"
      :src="src"
      class="video-element"
      :poster="poster"
      preload="metadata"
      playsinline
      @loadedmetadata="onLoadedMetadata"
      @timeupdate="onTimeUpdate"
      @waiting="loading = true"
      @canplay="loading = false"
      @ended="onEnded"
      @click="togglePlay"
      @dblclick="toggleFullscreen"
    />

    <!-- 加载指示器 -->
    <div v-if="loading" class="loading-indicator">
      <el-icon class="loading-icon"><Loading /></el-icon>
    </div>

    <!-- 中央播放按钮 -->
    <div
      v-if="!playing && !loading"
      class="center-play-btn"
      @click="togglePlay"
    >
      <el-icon :size="48"><VideoPlay /></el-icon>
    </div>

    <!-- 控制栏 -->
    <div class="controls-bar" :class="{ 'controls-visible': showControls }">
      <!-- 进度条 -->
      <div
        class="progress-track"
        ref="progressRef"
        @mousedown="startSeek"
        @touchstart="startSeek"
      >
        <div class="progress-buffered" :style="{ width: bufferedPercent + '%' }" />
        <div class="progress-filled" :style="{ width: progressPercent + '%' }" />
        <div class="progress-thumb" :style="{ left: progressPercent + '%' }" />
      </div>

      <div class="controls-row">
        <!-- 左侧控件 -->
        <div class="controls-left">
          <button class="ctrl-btn" @click="togglePlay" :title="playing ? '暂停' : '播放'" :aria-label="playing ? '暂停' : '播放'">
            <el-icon :size="20">
              <VideoPause v-if="playing" />
              <VideoPlay v-else />
            </el-icon>
          </button>

          <!-- 时间 -->
          <span class="time-display">{{ formatTime(currentTime) }} / {{ formatTime(duration) }}</span>

          <!-- 音量 -->
          <div class="volume-control">
            <button class="ctrl-btn" @click="toggleMute" :title="muted || volume === 0 ? '取消静音' : '静音'" :aria-label="muted || volume === 0 ? '取消静音' : '静音'">
              <VolumeX v-if="muted || volume === 0" :size="20" aria-hidden="true" />
              <Volume1 v-else-if="volume < 50" :size="20" aria-hidden="true" />
              <Volume2 v-else :size="20" aria-hidden="true" />
            </button>
            <el-slider
              v-model="volume"
              :min="0"
              :max="100"
              :step="1"
              class="volume-slider"
              @input="onVolumeChange"
            />
          </div>
        </div>

        <!-- 右侧控件 -->
        <div class="controls-right">
          <!-- 播放速度 -->
          <div class="speed-control">
            <button class="ctrl-btn speed-btn" @click="cycleSpeed" :title="'播放速度 ' + playbackRate + 'x'">
              {{ playbackRate }}x
            </button>
          </div>

          <!-- 全屏 -->
          <button class="ctrl-btn" @click="toggleFullscreen" :title="isFullscreen ? '退出全屏' : '全屏'" :aria-label="isFullscreen ? '退出全屏' : '全屏'">
            <el-icon :size="18">
              <FullScreen v-if="!isFullscreen" />
              <Close v-else />
            </el-icon>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import {
  LoaderCircle as Loading,
  Maximize as FullScreen,
  Minimize as Close,
  Pause as VideoPause,
  Play as VideoPlay,
  Volume1,
  Volume2,
  VolumeX,
} from 'lucide-vue-next'

defineOptions({ name: 'VideoPlayer' })

defineProps({
  src: { type: String, required: true },
  poster: { type: String, default: '' },
  autoplay: { type: Boolean, default: false },
})

const emit = defineEmits(['ended'])

const videoRef = ref(null)
const playerRef = ref(null)
const progressRef = ref(null)
const playing = ref(false)
const loading = ref(true)
const currentTime = ref(0)
const duration = ref(0)
const volume = ref(100)
const muted = ref(false)
const playbackRate = ref(1)
const isFullscreen = ref(false)
const showControls = ref(true)
let hideControlsTimer = null
let bufferedPercent = ref(0)

// 速度选项
const speeds = [0.5, 0.75, 1, 1.25, 1.5, 2]

// 进度百分比
const progressPercent = computed(() => {
  if (duration.value === 0) return 0
  return (currentTime.value / duration.value) * 100
})

// 格式化时间
const formatTime = (seconds) => {
  if (!seconds || isNaN(seconds)) return '0:00'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }
  return `${m}:${String(s).padStart(2, '0')}`
}

// 播放/暂停
const togglePlay = () => {
  const video = videoRef.value
  if (!video) return
  if (video.paused) {
    video.play().catch(() => {})
    playing.value = true
  } else {
    video.pause()
    playing.value = false
  }
}

// 元数据加载
const onLoadedMetadata = () => {
  const video = videoRef.value
  if (!video) return
  duration.value = video.duration
  volume.value = Math.round(video.volume * 100)
  muted.value = video.muted
  loading.value = false
}

// 时间更新
const onTimeUpdate = () => {
  const video = videoRef.value
  if (!video) return
  currentTime.value = video.currentTime
  // 计算缓冲进度
  if (video.buffered.length > 0) {
    bufferedPercent.value = (video.buffered.end(video.buffered.length - 1) / video.duration) * 100
  }
}

// 播放结束
const onEnded = () => {
  playing.value = false
  emit('ended')
}

// 进度条拖拽
let seeking = false

const startSeek = (e) => {
  seeking = true
  seek(e)
  document.addEventListener('mousemove', seek)
  document.addEventListener('mouseup', stopSeek)
  document.addEventListener('touchmove', seek, { passive: false })
  document.addEventListener('touchend', stopSeek)
}

const seek = (e) => {
  if (!seeking || !progressRef.value || !videoRef.value) return
  const rect = progressRef.value.getBoundingClientRect()
  const clientX = e.touches ? e.touches[0].clientX : e.clientX
  let percent = (clientX - rect.left) / rect.width
  percent = Math.max(0, Math.min(1, percent))
  currentTime.value = percent * duration.value
}

const stopSeek = () => {
  if (seeking && videoRef.value && duration.value) {
    videoRef.value.currentTime = currentTime.value
  }
  seeking = false
  document.removeEventListener('mousemove', seek)
  document.removeEventListener('mouseup', stopSeek)
  document.removeEventListener('touchmove', seek)
  document.removeEventListener('touchend', stopSeek)
}

// 音量
const onVolumeChange = (val) => {
  const video = videoRef.value
  if (!video) return
  video.volume = val / 100
  muted.value = val === 0
}

const toggleMute = () => {
  const video = videoRef.value
  if (!video) return
  video.muted = !video.muted
  muted.value = video.muted
}

// 播放速度
const cycleSpeed = () => {
  const idx = speeds.indexOf(playbackRate.value)
  const nextIdx = (idx + 1) % speeds.length
  playbackRate.value = speeds[nextIdx]
  if (videoRef.value) {
    videoRef.value.playbackRate = playbackRate.value
  }
}

// 全屏
const toggleFullscreen = () => {
  if (!playerRef.value) return

  if (!isFullscreen.value) {
    if (playerRef.value.requestFullscreen) {
      playerRef.value.requestFullscreen()
    } else if (playerRef.value.webkitRequestFullscreen) {
      playerRef.value.webkitRequestFullscreen()
    }
  } else {
    if (document.exitFullscreen) {
      document.exitFullscreen()
    } else if (document.webkitExitFullscreen) {
      document.webkitExitFullscreen()
    }
  }
}

const onFullscreenChange = () => {
  isFullscreen.value = !!(
    document.fullscreenElement ||
    document.webkitFullscreenElement
  )
}

// 控制栏显示/隐藏
// 键盘快捷键
const onKeyDown = (e) => {
  const video = videoRef.value
  if (!video) return

  switch (e.code) {
    case 'Space':
      e.preventDefault()
      togglePlay()
      break
    case 'ArrowLeft':
      e.preventDefault()
      video.currentTime = Math.max(0, video.currentTime - 5)
      break
    case 'ArrowRight':
      e.preventDefault()
      video.currentTime = Math.min(video.duration, video.currentTime + 5)
      break
    case 'ArrowUp':
      e.preventDefault()
      volume.value = Math.min(100, volume.value + 5)
      onVolumeChange(volume.value)
      break
    case 'ArrowDown':
      e.preventDefault()
      volume.value = Math.max(0, volume.value - 5)
      onVolumeChange(volume.value)
      break
    case 'KeyF':
      e.preventDefault()
      toggleFullscreen()
      break
    case 'KeyM':
      e.preventDefault()
      toggleMute()
      break
    case 'Digit0':
    case 'Digit1':
    case 'Digit2':
    case 'Digit3':
    case 'Digit4':
    case 'Digit5':
    case 'Digit6':
    case 'Digit7':
    case 'Digit8':
    case 'Digit9': {
      e.preventDefault()
      const num = parseInt(e.code.replace('Digit', ''))
      video.currentTime = (num / 10) * video.duration
      break
    }
  }
}

onMounted(() => {
  document.addEventListener('fullscreenchange', onFullscreenChange)
  document.addEventListener('webkitfullscreenchange', onFullscreenChange)
  document.addEventListener('keydown', onKeyDown)
})

onUnmounted(() => {
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  document.removeEventListener('webkitfullscreenchange', onFullscreenChange)
  document.removeEventListener('keydown', onKeyDown)
  document.removeEventListener('mousemove', seek)
  document.removeEventListener('mouseup', stopSeek)
  clearTimeout(hideControlsTimer)
})
</script>

<style scoped>
.video-player {
  position: relative;
  width: 100%;
  background: #000;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  user-select: none;
  -webkit-user-select: none;
}

.video-element {
  display: block;
  width: 100%;
  height: auto;
  max-height: 70vh;
  object-fit: contain;
}

.loading-indicator {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: #fff;
}

.loading-icon {
  animation: spin 1s linear infinite;
  font-size: 36px;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.center-play-btn {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  transition: background 0.2s, transform 0.2s;
}
.center-play-btn:hover {
  background: rgba(0, 0, 0, 0.75);
  transform: translate(-50%, -50%) scale(1.1);
}

/* 控制栏 */
.controls-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.8));
  padding: 20px 12px 8px;
  opacity: 0;
  transition: opacity 0.3s;
}
.controls-bar.controls-visible,
.video-player:hover .controls-bar {
  opacity: 1;
}

.progress-track {
  position: relative;
  height: 4px;
  background: rgba(255, 255, 255, 0.25);
  border-radius: 2px;
  cursor: pointer;
  margin-bottom: 8px;
  transition: height 0.15s;
}
.progress-track:hover {
  height: 6px;
}

.progress-buffered {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  background: rgba(255, 255, 255, 0.35);
  border-radius: 2px;
}

.progress-filled {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  background: #409eff;
  border-radius: 2px;
}

.progress-thumb {
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 12px;
  height: 12px;
  background: #409eff;
  border-radius: 50%;
  opacity: 0;
  transition: opacity 0.15s;
}
.progress-track:hover .progress-thumb {
  opacity: 1;
}

.controls-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.controls-left,
.controls-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ctrl-btn {
  background: none;
  border: none;
  color: #fff;
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: background 0.15s;
}
.ctrl-btn:hover {
  background: rgba(255, 255, 255, 0.15);
}

.time-display {
  color: #fff;
  font-size: 12px;
  font-family: monospace;
  white-space: nowrap;
}

.volume-control {
  display: flex;
  align-items: center;
  gap: 4px;
}

.volume-icon-off,
.volume-icon-low,
.volume-icon-high {
  font-size: 14px;
  line-height: 1;
}

.volume-slider {
  width: 60px;
  --el-slider-main-bg-color: #fff;
  --el-slider-runway-bg-color: rgba(255, 255, 255, 0.3);
}
.volume-slider :deep(.el-slider__button) {
  width: 10px;
  height: 10px;
}

.speed-btn {
  font-size: 12px;
  min-width: 32px;
  justify-content: center;
  font-family: monospace;
  font-weight: 600;
}

/* 全屏适配 */
.is-fullscreen {
  border-radius: 0;
}
.is-fullscreen .video-element {
  max-height: none;
  height: 100vh;
  object-fit: contain;
}
.is-fullscreen .controls-bar {
  padding: 24px 20px 16px;
}

/* 响应式 */
@media (max-width: 768px) {
  .volume-control .volume-slider {
    width: 40px;
  }
  .time-display {
    font-size: 11px;
  }
}
</style>
