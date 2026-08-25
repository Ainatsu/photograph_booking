<template>
  <div class="discover">
    <div class="photographer-list" v-loading="loading">
      <div
        class="photographer-row"
        v-for="profile in profiles"
        :key="profile.id"
        @click="goDetail(profile.user_id)"
      >
        <div class="row-avatar">
          <img
            v-if="getAvatarUrl(profile)"
            :src="getAvatarUrl(profile)"
            class="avatar-img"
            :alt="profile.user_display_name || '摄影师'"
          />
          <div v-else class="avatar-fallback">
            {{ (profile.user_display_name || '?')[0] }}
          </div>
        </div>

        <div class="row-info">
          <div class="info-name">{{ profile.user_display_name || '摄影师' }}</div>
          <div class="info-rating" v-if="profile.avg_rating != null">
            <svg class="rating-star-icon" viewBox="0 0 24 24" width="14" height="14">
              <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" fill="#8B6914"/>
            </svg>
            <span class="rating-score">{{ profile.avg_rating }}</span>
          </div>
          <div class="info-rating info-rating--empty" v-else>
            <span class="rating-no-data">暂无评分</span>
          </div>
          <button
            class="msg-btn"
            @click.stop="goMessage(profile.user_id)"
          >
            邀请
          </button>
        </div>

        <div class="row-works">
          <div class="work-cell" v-for="i in 4" :key="i">
            <img
              v-if="getWorkUrl(profile, i - 1)"
              :src="getWorkUrl(profile, i - 1)"
              class="work-img"
              loading="lazy"
              :alt="profile.user_display_name + ' 作品 ' + i"
            />
            <div v-else class="work-placeholder"></div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="!loading && profiles.length === 0" class="empty-state">
      <div class="empty-icon">—</div>
      <div class="empty-text">暂无摄影师</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getPhotographerList } from '../api/photographer'
import { getWorkPreviewUrl } from '@/utils/imagePreview'

defineOptions({ name: 'Discover' })

const router = useRouter()
const profiles = ref([])
const loading = ref(false)

const fetchList = async () => {
  loading.value = true
  try {
    const res = await getPhotographerList()
    profiles.value = res.data
  } finally {
    loading.value = false
  }
}

const getWorkUrl = (profile, index) => {
  if (profile.portfolio && profile.portfolio[index]) {
    return getWorkPreviewUrl(profile.portfolio[index])
  }
  return ''
}

const getAvatarUrl = (profile) => {
  if (profile.user_avatar_url) {
    if (profile.user_avatar_url.startsWith('http')) return profile.user_avatar_url
    return profile.user_avatar_url
  }
  return ''
}

const goDetail = (userId) => {
  router.push(`/photographer/${userId}`)
}

const goMessage = (userId) => {
  router.push(`/messages?to=${userId}`)
}

onMounted(fetchList)
</script>

<style scoped>
/* ===== Layout ===== */
.discover {
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: var(--space-6);
}

.photographer-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

/* ===== Row Card ===== */
.photographer-row {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  padding: var(--space-6);
  background: var(--color-paper-light);
  border: var(--border-default);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: border-color 0.2s ease;
}

.photographer-row:hover {
  border-color: var(--color-ink-secondary);
}

/* ===== Avatar ===== */
.row-avatar {
  flex-shrink: 0;
  width: 108px;
  height: 108px;
}

.avatar-img {
  width: 108px;
  height: 108px;
  border-radius: var(--radius-md);
  object-fit: cover;
  display: block;
  border: var(--border-default);
}

.avatar-fallback {
  width: 108px;
  height: 108px;
  border-radius: var(--radius-md);
  background: var(--color-divider);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-2xl);
  font-weight: 600;
  color: var(--color-ink-secondary);
  border: var(--border-default);
}

/* ===== Info ===== */
.row-info {
  flex-shrink: 0;
  width: 160px;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.info-name {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--color-ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Rating */
.info-rating {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.rating-star-icon {
  flex-shrink: 0;
}

.rating-score {
  font-size: var(--text-sm);
  font-weight: 600;
  color: #8B6914;
}

.rating-no-data {
  font-size: var(--text-xs);
  color: var(--color-ink-tertiary);
}

/* Invite Button */
.msg-btn {
  margin-top: var(--space-1);
  align-self: flex-start;
  min-width: var(--tap-target-min);
  min-height: var(--tap-target-min);
  padding: 0 calc(var(--space-4) * 1.8);
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-paper);
  background: var(--color-brand);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.msg-btn:hover {
  background: var(--color-brand-hover);
}

/* ===== Works Grid ===== */
.row-works {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-2);
  min-width: 0;
}

.work-cell {
  aspect-ratio: 1 / 1;
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: var(--color-divider);
  border: var(--border-default);
}

.work-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.work-placeholder {
  width: 100%;
  height: 100%;
  background: var(--color-divider);
}

/* ===== Empty State ===== */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-8) 0;
  gap: var(--space-3);
}

.empty-icon {
  font-size: var(--text-3xl, 2rem);
  color: var(--color-ink-tertiary);
  line-height: 1;
}

.empty-text {
  font-size: var(--text-sm);
  color: var(--color-ink-tertiary);
}

/* ===== Responsive ===== */
@media (max-width: 768px) {
  .discover {
    padding: var(--space-3);
  }

  .photographer-row {
    flex-wrap: wrap;
    gap: var(--space-3);
    padding: var(--space-4);
  }

  .row-avatar {
    width: 84px;
    height: 84px;
  }

  .avatar-img,
  .avatar-fallback {
    width: 84px;
    height: 84px;
    font-size: var(--text-xl);
  }

  .row-info {
    width: auto;
    flex: 1;
    min-width: 140px;
  }

  .row-works {
    flex: 1 1 100%;
    grid-template-columns: repeat(4, 1fr);
    gap: var(--space-1);
  }
}

@media (max-width: 480px) {
  .photographer-row {
    align-items: flex-start;
  }

  .row-avatar {
    align-self: center;
  }

  .row-info {
    flex: 1;
    min-width: 0;
  }

  .row-works {
    grid-template-columns: repeat(2, 1fr);
    gap: var(--space-1);
  }
}
</style>
