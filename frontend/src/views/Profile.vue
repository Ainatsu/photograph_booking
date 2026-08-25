<template>
  <div class="profile-page">
    <!-- 个人信息头部 -->
    <div
      class="profile-header-card"
      :class="`bio-height-${bioHeightMode}`"
      :style="{ backgroundImage: `url(${backgroundPreviewUrl || backgroundUrl || ''})` }"
    >
      <!-- 隐藏的文件选择器 -->
      <input
        ref="bgInputRef"
        type="file"
        accept="image/*"
        style="display:none"
        @change="handleBackgroundChange"
      />
      <!-- 切换身份图标 -->
      <div class="role-switch-btn" @click="toggleProfileMode" :title="profileMode === 'photographer' ? '切换至客户' : '切换至摄影师'">
        <el-icon><Refresh /></el-icon>
      </div>
      <!-- 更换背景图标 -->
      <div class="bg-change-btn" @click="triggerBackgroundUpload" :title="'更换背景'">
        <el-icon v-if="!uploadingBackground"><Camera /></el-icon>
        <el-icon v-else class="is-loading"><Loading /></el-icon>
      </div>
      <div class="profile-header">
        <div class="profile-avatar-wrap">
          <el-upload
            :auto-upload="false"
            :show-file-list="false"
            :on-change="handleAvatarChange"
            accept="image/*"
            class="avatar-upload-btn"
          >
            <el-avatar :size="100" :src="avatarSrc" class="profile-avatar">
              {{ displayName[0] || '?' }}
            </el-avatar>
          </el-upload>
          <el-tooltip v-if="canUsePhotographerFeatures" content="已认证摄影师" placement="top">
            <span class="verified-badge" aria-label="已认证摄影师">
              <el-icon><Check /></el-icon>
            </span>
          </el-tooltip>
        </div>
        <div class="profile-info">
          <div class="profile-name-row">
            <div class="profile-name-group">
              <span class="profile-name">{{ displayName || '未设置网名' }}</span>
              <el-tooltip content="编辑资料" placement="top">
                <el-icon class="edit-icon" @click="openEditDialog"><Edit /></el-icon>
              </el-tooltip>
            </div>

          </div>
          <div class="profile-bio">
            <p v-for="(para, idx) in bioParagraphs" :key="idx">{{ para }}</p>
            <p v-if="!bioParagraphs.length" class="bio-empty">这个人很懒，什么都没写~</p>
          </div>
          <!-- 可点击的关注/粉丝计数 -->
          <FollowCounts
            :following-count="followCounts.following_count"
            :follower-count="followCounts.follower_count"
            :clickable="true"
            @show-following="showFollowList('following')"
            @show-followers="showFollowList('followers')"
          />
        </div>
      </div>
    </div>

    <!-- Tab 切换 -->
    <el-tabs v-model="activeTab" class="profile-tabs">
      <el-tab-pane label="作品" name="works">
        <div class="works-grid" v-loading="loadingWorks || loadingWorkDrafts">
          <div
            class="work-card draft-work-card"
            v-for="draft in workDrafts"
            :key="`draft-${draft.id}`"
            @click="goWorkDraft(draft)"
          >
            <el-card shadow="never" :body-style="{ padding: '0' }">
              <div class="work-img-wrap draft-img-wrap">
                <video
                  v-if="isVideoDraft(draft) && draft.previewUrl"
                  :src="draft.previewUrl"
                  class="work-img work-video-preview"
                  preload="metadata"
                  muted
                  playsinline
                />
                <img
                  v-else-if="draft.previewUrl"
                  :src="draft.previewUrl"
                  alt=""
                  class="work-img draft-preview-img"
                />
                <div v-else class="draft-empty-preview">暂无预览</div>
                <span class="draft-badge">草稿</span>
              </div>
              <div class="work-card-body">
                <div class="work-card-title">{{ draft.title || '未命名草稿' }}</div>
                <div class="draft-action-row">
                  <div class="draft-meta">{{ formatDraftTime(draft.updatedAt) }}</div>
                  <button class="draft-delete-btn" type="button" title="删除草稿" aria-label="删除草稿" @click.stop="deleteDraftCard(draft)">
                    <el-icon><Delete /></el-icon>
                  </button>
                </div>
              </div>
            </el-card>
          </div>

          <div class="work-card" v-for="(work, i) in portfolio" :key="work.id || i" @click="goWorkDetail(work)">
            <el-card shadow="never" :body-style="{ padding: '0' }">
              <div class="work-img-wrap" :style="{ aspectRatio: getPortfolioPreviewRatio(work) }">
                <video
                  v-if="shouldUseVideoElementPreview(work)"
                  :src="getVideoStreamUrl(work)"
                  class="work-img work-video-preview"
                  preload="metadata"
                  muted
                  playsinline
                />
                <el-image
                  v-else
                  :src="getWorkPreviewUrl(work)"
                  fit="cover"
                  class="work-img"
                  lazy
                  @error="handleWorkPreviewError(work)"
                />
                <div v-if="isVideoWork(work)" class="work-video-overlay">
                  <el-icon :size="24"><VideoPlay /></el-icon>
                </div>
              </div>
              <div class="work-card-body">
                <div class="work-card-title" v-if="work.title">{{ work.title }}</div>
                <div class="photographer-row">
                  <span class="photographer-info">
                    <el-avatar :size="24" :src="avatarSrc" class="photographer-avatar">
                      {{ (displayName || '?')[0] }}
                    </el-avatar>
                    <span class="photographer-name">{{ displayName || '摄影师' }}</span>
                  </span>
                  <span @click.stop>
                    <LikeButton
                      v-if="work.id"
                      target-type="portfolio"
                      :target-id="work.id"
                      :liked="likeStore.get('portfolio', work.id).liked"
                      :count="likeStore.get('portfolio', work.id).count"
                      class="row-like-btn"
                    />
                  </span>
                </div>
              </div>
            </el-card>
          </div>
          <el-empty v-if="!loadingWorks && !loadingWorkDrafts && !portfolio.length && !workDrafts.length" description="暂无作品" />
        </div>
      </el-tab-pane>

      <el-tab-pane v-if="isOrdersTabVisible" label="我的订单" name="orders">
        <section v-if="canViewCurrentModeOrders" class="workspace-panel workspace-panel-flat" v-loading="loadingOrders">
          <div class="workspace-filter-bar">
            <button
              v-for="item in orderFilterOptions"
              :key="item.key"
              :class="['filter-btn', { 'filter-btn-active': orderFilter === item.key }]"
              @click="orderFilter = item.key"
            >
              {{ item.label }}
              <span class="filter-count">{{ item.count }}</span>
            </button>
          </div>

          <div v-if="filteredOrders.length" class="profile-order-card-list">
            <article v-for="row in filteredOrders" :key="row.id" class="profile-order-card">
              <div class="profile-order-main">
                <div class="profile-card-heading">
                  <span>订单 #{{ row.id }}</span>
                  <el-tag :type="statusType(row.status)" effect="plain">{{ statusLabel(row.status) }}</el-tag>
                </div>
                <h3>{{ formatProfileOrderTitle(row.package_snapshot) }}</h3>
                <p v-if="row.notes">{{ row.notes }}</p>
                <div class="profile-order-facts">
                  <div><span>预约日期</span><strong>{{ formatProfileDateOnly(row.appointment_time) }}</strong></div>
                  <div><span>下一步</span><strong>{{ orderNextText(row) }}</strong></div>
                  <div v-if="row.active_reschedule_request"><span>改期日期</span><strong class="pending-reschedule">{{ formatProfileDateOnly(row.active_reschedule_request.requested_appointment_time) }}</strong></div>
                </div>
              </div>
              <div class="profile-card-actions">
                <el-button type="primary" plain @click="goOrderDetail(row)">{{ profileOrderActionLabel(row) }}</el-button>
              </div>
            </article>
          </div>

          <el-table v-if="false" :data="filteredOrders" class="workspace-table">
            <el-table-column label="订单" min-width="260">
              <template #default="{ row }">
                <div class="entity-cell">
                  <span class="entity-id">#{{ row.id }}</span>
                  <strong>{{ row.package_snapshot || '未命名方案' }}</strong>
                  <small>{{ row.notes || '无备注' }}</small>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="预约时间" width="210">
              <template #default="{ row }">
                <div class="time-cell">
                  <strong>{{ formatDate(row.appointment_time) }}</strong>
                  <span v-if="row.active_reschedule_request" class="pending-reschedule">
                    改期候选：{{ formatDate(row.active_reschedule_request.requested_appointment_time) }}
                  </span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-tag :type="statusType(row.status)" effect="plain">{{ statusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="下一步" min-width="220">
              <template #default="{ row }">
                <span class="next-step-text">{{ orderNextText(row) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="250" fixed="right">
              <template #default="{ row }">
                <div class="row-actions">
                  <template v-if="isPhotographerOrdersMode">
                    <el-button v-if="row.status === 'pending'" type="success" size="small" @click="handleConfirm(row.id)">确认</el-button>
                    <el-button v-if="row.status === 'pending'" type="danger" size="small" @click="handleReject(row.id)">拒绝</el-button>
                    <el-button v-if="row.status === 'confirmed'" type="primary" size="small" @click="handleStart(row.id)">开始服务</el-button>
                    <el-button v-if="row.status === 'in_progress'" type="primary" size="small" @click="openDeliveryDialog(row)">交付</el-button>
                    <el-button v-if="['delivered', 'received', 'reviewed', 'completed'].includes(row.status)" size="small" @click="openViewDelivery(row)">作品</el-button>
                    <el-button v-if="row.rating" size="small" @click="openViewReview(row)">评价</el-button>
                  </template>
                  <template v-else>
                    <el-button v-if="['delivered', 'received', 'reviewed', 'completed'].includes(row.status)" size="small" @click="openViewDelivery(row)">作品</el-button>
                    <el-button v-if="row.status === 'delivered'" type="success" size="small" @click="handleAccept(row.id)">验收</el-button>
                    <el-button v-if="['received', 'completed'].includes(row.status) && !row.rating" type="primary" size="small" @click="openReviewDialog(row)">评价</el-button>
                    <el-button v-if="row.rating" size="small" @click="openViewReview(row)">评价</el-button>
                  </template>
                  <el-button type="primary" size="small" plain @click="goOrderDetail(row)">详情</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else-if="!loadingOrders" description="暂无订单" />
        </section>
        <PhotographerApplicationGate v-if="!canViewCurrentModeOrders && activeTab === 'orders'" />
      </el-tab-pane>

      <!-- 我的应邀（摄影师专属） -->
      <el-tab-pane v-if="isPhotographerMode" label="我的应邀" name="applications">
        <section v-if="canUsePhotographerFeatures" class="workspace-panel" v-loading="loadingApplications">
          <div class="workspace-filter-bar">
            <button
              v-for="item in applicationFilterOptions"
              :key="item.key"
              :class="['filter-btn', { 'filter-btn-active': applicationFilter === item.key }]"
              @click="applicationFilter = item.key"
            >
              {{ item.label }}
              <span class="filter-count">{{ item.count }}</span>
            </button>
          </div>

          <el-table v-if="filteredApplications.length" :data="filteredApplications" class="workspace-table">
            <el-table-column label="企划" min-width="280">
              <template #default="{ row }">
                <div class="entity-cell">
                  <strong>{{ row.project?.title || `企划 #${row.project_id}` }}</strong>
                  <small>{{ row.project?.city || '未填写城市' }}</small>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="客户预算" width="150">
              <template #default="{ row }">{{ formatProjectBudget(row.project) }}</template>
            </el-table-column>
            <el-table-column label="我的报价" width="130">
              <template #default="{ row }">
                <strong class="money-text">¥{{ row.price_quote }}</strong>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-tag :type="appStatusType(row.status)" effect="plain">{{ appStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="提交时间" width="180">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="180" fixed="right">
              <template #default="{ row }">
                <div class="row-actions">
                  <el-button size="small" :icon="View" @click="router.push(`/projects/${row.project_id}`)">详情</el-button>
                  <el-button
                    v-if="row.status === 'selected' && row.project?.converted_order_id"
                    size="small"
                    type="primary"
                    :icon="Tickets"
                    @click="router.push(`/orders/${row.project.converted_order_id}`)"
                  >
                    订单
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else-if="!loadingApplications" description="暂无应邀" />
        </section>
        <PhotographerApplicationGate v-if="!canUsePhotographerFeatures && activeTab === 'applications'" />
      </el-tab-pane>

      <!-- 我的企划（两种角色都可查看） -->
      <el-tab-pane v-if="isCustomerMode" label="我的企划" name="my-projects">
        <section class="workspace-panel workspace-panel-flat" v-loading="loadingProjects">
          <div class="workspace-filter-bar">
            <button
              v-for="item in projectFilterOptions"
              :key="item.key"
              :class="['filter-btn', { 'filter-btn-active': projectFilter === item.key }]"
              @click="projectFilter = item.key"
            >
              {{ item.label }}
              <span class="filter-count">{{ item.count }}</span>
            </button>
          </div>

          <div v-if="filteredProjects.length" class="profile-project-card-list">
            <article v-for="row in filteredProjects" :key="row.id" class="profile-project-card">
              <div class="profile-project-content">
                <div class="profile-project-info">
                  <div class="profile-card-heading">
                    <div><h3>{{ row.title }}</h3><span>{{ row.city || '地点待定' }}</span></div>
                    <el-tag :type="projectStatusType(row.status)" effect="plain">{{ projectStatusLabel(row.status) }}</el-tag>
                  </div>
                  <div class="profile-project-facts">
                    <div><span>预算</span><strong>{{ formatBudget(row) }}</strong></div>
                    <div><span>收到应邀</span><strong>{{ row.application_count || 0 }} 人</strong></div>
                    <div><span>发布日期</span><strong>{{ formatProfileDateOnly(row.created_at) }}</strong></div>
                  </div>
                </div>
                <el-image v-if="row.reference_images?.length" :src="row.reference_images[0]" fit="cover" class="profile-project-cover" :alt="`${row.title} 示意图`" />
              </div>
              <div class="profile-card-actions is-project-actions">
                <el-button :icon="View" @click="router.push(`/projects/${row.id}`)">详情</el-button>
                <el-button v-if="row.converted_order_id" type="primary" :icon="Tickets" @click="router.push(`/orders/${row.converted_order_id}`)">订单</el-button>
                <el-button v-if="row.status === 'open' || row.status === 'draft'" @click="closeProjectRow(row)">关闭</el-button>
                <el-button v-if="row.status === 'open' || row.status === 'draft' || row.status === 'expired'" :icon="Edit" @click="router.push(`/projects/${row.id}/edit`)">编辑</el-button>
              </div>
            </article>
          </div>

          <el-table v-if="false" :data="filteredProjects" class="workspace-table">
            <el-table-column prop="title" label="企划" min-width="280">
              <template #default="{ row }">
                <div class="entity-cell">
                  <strong>{{ row.title }}</strong>
                  <small>{{ row.city || '未填写城市' }}</small>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="预算" width="160">
              <template #default="{ row }">{{ formatBudget(row) }}</template>
            </el-table-column>
            <el-table-column label="应邀" width="100">
              <template #default="{ row }">
                <strong class="count-text">{{ row.application_count || 0 }}</strong>
                <span class="muted-unit"> 人</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-tag :type="projectStatusType(row.status)" effect="plain">{{ projectStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="创建时间" width="180">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="230" fixed="right">
              <template #default="{ row }">
                <div class="row-actions">
                  <el-button size="small" :icon="View" @click="router.push(`/projects/${row.id}`)">详情</el-button>
                  <el-button
                    v-if="row.converted_order_id"
                    size="small"
                    type="primary"
                    :icon="Tickets"
                    @click="router.push(`/orders/${row.converted_order_id}`)"
                  >
                    订单
                  </el-button>
                  <el-button
                    v-if="row.status === 'open' || row.status === 'draft'"
                    size="small"
                    @click="closeProjectRow(row)"
                  >
                    关闭
                  </el-button>
                  <el-button
                    v-if="row.status === 'open' || row.status === 'draft' || row.status === 'expired'"
                    size="small"
                    :icon="Edit"
                    @click="router.push(`/projects/${row.id}/edit`)"
                  >
                    编辑
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else-if="!loadingProjects" description="暂无企划" />
        </section>
      </el-tab-pane>

      <el-tab-pane v-if="isCustomerMode" label="我的收藏" name="favorites">
        <div v-if="favItems.length > 0 || pkgFavItems.length > 0 || !loadingFavs" class="workspace-filter-bar">
          <button
            v-for="item in favoriteFilterOptions"
            :key="item.key"
            type="button"
            :class="['filter-btn', { 'filter-btn-active': favTab === item.key }]"
            :aria-pressed="favTab === item.key"
            @click="favTab = item.key"
          >
            {{ item.label }}
            <span class="filter-count">{{ item.count }}</span>
          </button>
        </div>

        <div v-if="favTab === 'works'" class="fav-waterfall" v-loading="loadingFavs">
          <div
            class="fav-item"
            v-for="item in favItems"
            :key="item.work_id"
            @click="goFavoriteWork(item)"
          >
            <el-card shadow="never" :body-style="{ padding: '0' }">
              <div
                v-if="item.work_data?.url"
                class="fav-img-wrap"
                :style="{ aspectRatio: getFavoriteWorkPreviewRatio(item) }"
              >
                <el-image
                  :src="getFavoriteWorkPreviewUrl(item)"
                  fit="cover"
                  class="fav-img"
                  lazy
                />
              </div>
              <div v-else class="fav-placeholder">暂无图片</div>
              <div class="fav-body">
                <div class="fav-title" v-if="item.work_data?.title">{{ item.work_data.title }}</div>
                <div class="fav-photog">
                  <el-avatar :size="20" :src="getFullUrl(item.photographer_avatar)">
                    {{ (item.photographer_name || '?')[0] }}
                  </el-avatar>
                  <span class="fav-photog-name">{{ item.photographer_name || '摄影师' }}</span>
                  <span class="fav-time">{{ formatFavTime(item.created_at) }}</span>
                </div>
              </div>
            </el-card>
          </div>
          <el-empty v-if="!loadingFavs && !favItems.length" description="还没有收藏作品">
            <el-button type="primary" @click="$router.push('/works')">去发现</el-button>
          </el-empty>
        </div>

        <div v-if="favTab === 'packages'" class="fav-waterfall" v-loading="loadingPkgFavs">
          <div
            class="fav-item"
            v-for="item in pkgFavItems"
            :key="item.package_id"
            @click="goFavoritePackage(item)"
          >
            <el-card shadow="never" :body-style="{ padding: '0' }">
              <div
                v-if="getFavoritePackageCoverUrl(item)"
                class="fav-img-wrap"
                :style="{ aspectRatio: getFavoritePackagePreviewRatio(item) }"
              >
                <el-image
                  :src="getFavoritePackageCoverUrl(item)"
                  fit="cover"
                  class="fav-img"
                  lazy
                />
              </div>
              <div v-else class="fav-placeholder">暂无示例图</div>
              <div class="fav-body">
                <div class="fav-title" v-if="item.package_data?.package_name">{{ item.package_data.package_name }}</div>
                <div class="fav-price" v-if="item.package_data?.price">¥{{ item.package_data.price }}</div>
                <div class="fav-photog">
                  <el-avatar :size="20" :src="getFullUrl(item.photographer_avatar)">
                    {{ (item.photographer_name || '?')[0] }}
                  </el-avatar>
                  <span class="fav-photog-name">{{ item.photographer_name || '摄影师' }}</span>
                  <span class="fav-time">{{ formatFavTime(item.created_at) }}</span>
                </div>
              </div>
            </el-card>
          </div>
          <el-empty v-if="!loadingPkgFavs && !pkgFavItems.length" description="还没有收藏方案">
            <el-button type="primary" @click="$router.push('/packages')">浏览方案</el-button>
          </el-empty>
        </div>
      </el-tab-pane>

      <el-tab-pane v-if="isCustomerMode" label="我喜欢的作品" name="likes">
        <div class="fav-waterfall" v-loading="loadingLikedWorks">
          <div
            class="fav-item"
            v-for="item in likedWorkItems"
            :key="item.work_id"
            @click="goLikedWork(item)"
          >
            <el-card shadow="never" :body-style="{ padding: '0' }">
              <div
                v-if="item.work_data?.url"
                class="fav-img-wrap"
                :style="{ aspectRatio: getLikedWorkPreviewRatio(item) }"
              >
                <el-image
                  :src="getFavoriteWorkPreviewUrl(item)"
                  fit="cover"
                  class="fav-img"
                  lazy
                />
              </div>
              <div v-else class="fav-placeholder">暂无图片</div>
              <div class="fav-body">
                <div class="fav-title" v-if="item.work_data?.title">{{ item.work_data.title }}</div>
                <div class="fav-photog">
                  <el-avatar :size="20" :src="getFullUrl(item.photographer_avatar)">
                    {{ (item.photographer_name || '?')[0] }}
                  </el-avatar>
                  <span class="fav-photog-name">{{ item.photographer_name || '摄影师' }}</span>
                  <span class="fav-time">{{ formatFavTime(item.liked_at) }}</span>
                </div>
              </div>
            </el-card>
          </div>
          <el-empty v-if="!loadingLikedWorks && !likedWorkItems.length" description="还没有喜欢的作品">
            <el-button type="primary" @click="$router.push('/works')">去发现</el-button>
          </el-empty>
        </div>
      </el-tab-pane>

      <el-tab-pane v-if="isPhotographerMode" label="方案管理" name="pkg-mgmt">
        <template v-if="canUsePhotographerFeatures">
          <div class="workspace-panel package-management-panel">
            <div class="managed-package-grid">
              <button class="managed-package-add" type="button" @click="openPackageDialog(-1)">
                <el-icon><Plus /></el-icon>
                <strong>添加新方案</strong>
                <span>补充价格、样片、城市和风格标签</span>
              </button>

              <article
                v-for="(pkg, index) in packagesList"
                :key="`${pkg.name || 'package'}-${index}`"
                class="managed-package-card"
              >
                <div class="managed-package-cover">
                  <el-image
                    v-if="pkg.samples && pkg.samples.length"
                    :src="getManagedPackageCoverUrl(pkg)"
                    fit="cover"
                    class="managed-package-img"
                    :style="{ aspectRatio: getOrPreload(getManagedPackageCoverUrl(pkg), getManagedPackageKey(pkg, index)) }"
                    :preview-src-list="pkg.samples.map(getFullUrl)"
                  />
                  <div v-else class="managed-package-placeholder">暂无样片</div>
                </div>
                <div class="managed-package-body">
                  <div class="managed-package-title-row">
                    <h4>{{ pkg.name || '未命名方案' }}</h4>
                    <strong>¥{{ pkg.price }}</strong>
                  </div>
                  <p>{{ pkg.description || '暂无描述' }}</p>
                  <div class="managed-package-meta">
                    <span>{{ pkg.duration || '待定' }} 分钟</span>
                    <span>{{ pkg.city || '不限城市' }}</span>
                  </div>
                  <div v-if="(pkg.styles || pkg.includes || []).length" class="managed-package-tags">
                    <el-tag
                      v-for="tag in (pkg.styles || pkg.includes || []).slice(0, 4)"
                      :key="tag"
                      size="small"
                      effect="plain"
                    >
                      {{ tag }}
                    </el-tag>
                  </div>
                  <div class="managed-package-actions">
                    <el-button type="primary" plain size="small" @click="openPackageDialog(index)">编辑</el-button>
                    <el-button type="danger" plain size="small" @click="removePackage(index)">删除</el-button>
                  </div>
                </div>
              </article>
            </div>
          </div>
        </template>
        <PhotographerApplicationGate v-else-if="activeTab === 'pkg-mgmt'" />
      </el-tab-pane>

      <el-tab-pane v-if="isPhotographerMode" label="档期设置" name="availability">
        <template v-if="canUsePhotographerFeatures">
          <div class="availability-panel" v-loading="loadingAvailability">
            <div class="availability-topbar">
              <div class="availability-month-control">
                <el-button
                  :icon="ArrowLeft"
                  circle
                  title="上个月"
                  :disabled="!canGoPreviousAvailabilityMonth"
                  @click="shiftAvailabilityMonth(-1)"
                />
                <div class="availability-month-heading">
                  <span>档期日历</span>
                  <strong>{{ availabilityMonthLabel }}</strong>
                </div>
                <el-button
                  :icon="ArrowRight"
                  circle
                  title="下个月"
                  :disabled="!canGoNextAvailabilityMonth"
                  @click="shiftAvailabilityMonth(1)"
                />
              </div>

              <div class="availability-summary">
                <div class="availability-summary-item">
                  <span>可约</span>
                  <strong>{{ availabilityMonthStats.free }}</strong>
                </div>
                <div class="availability-summary-item is-busy">
                  <span>忙碌</span>
                  <strong>{{ availabilityMonthStats.busy }}</strong>
                </div>
                <div class="availability-summary-item is-selected">
                  <span>已选</span>
                  <strong>{{ availabilityMonthStats.selected }}</strong>
                </div>
              </div>

              <div class="availability-mode-actions">
                <div class="availability-limit-field">
                  <label for="max-booking-date">最远可预约到</label>
                  <el-date-picker id="max-booking-date" v-model="maxBookingDate" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" :disabled-date="disableMaxBookingDate" />
                </div>
                <el-segmented
                  v-model="availabilitySelectionMode"
                  :options="availabilityModeOptions"
                  class="availability-mode-segment"
                />
                <el-button type="primary" @click="saveAvailability" :loading="savingAvailability">保存档期</el-button>
              </div>
            </div>

            <div class="availability-layout">
              <section class="availability-calendar-card">
                <div class="availability-calendar-meta">
                  <div class="availability-legend">
                    <span><i class="availability-dot is-free"></i>可约</span>
                    <span><i class="availability-dot is-busy"></i>忙碌</span>
                  </div>
                  <span class="availability-meta-text">{{ availabilityModeHint }}</span>
                </div>

                <div class="availability-calendar">
                  <div
                    v-for="weekday in availabilityWeekdays"
                    :key="weekday"
                    class="availability-weekday"
                  >
                    {{ weekday }}
                  </div>
                  <template v-for="cell in availabilityCalendarCells" :key="cell.key">
                    <div v-if="cell.isBlank" class="availability-date-cell is-blank"></div>
                    <button
                      v-else
                      type="button"
                      :class="[
                        'availability-date-cell',
                        `is-${cell.status}`,
                        {
                          'is-today': cell.isToday,
                          'is-disabled': cell.disabled,
                          'is-selected': cell.isSelected,
                          'is-range-start': cell.isRangeStart,
                          'is-range-end': cell.isRangeEnd,
                          'is-in-range': cell.isInRange,
                        },
                      ]"
                      :disabled="cell.disabled"
                      @click="selectAvailabilityDate(cell)"
                    >
                      <span class="availability-date-top">
                        <span class="availability-date-number">{{ cell.day }}</span>
                        <span v-if="cell.isToday" class="availability-today-tag">今天</span>
                      </span>
                      <span :class="['availability-status-badge', `is-${cell.status}`]">
                        {{ availabilityStatusLabel(cell.status) }}
                      </span>
                      <span v-if="cell.location" class="availability-location">{{ cell.location }}</span>
                    </button>
                  </template>
                </div>
              </section>

              <aside class="availability-detail-panel">
                <div class="availability-detail-header">
                  <span>当前日期</span>
                  <h3>{{ selectedAvailabilityLabel || '未选择日期' }}</h3>
                  <p>{{ selectedAvailabilityWeekday || '本月档期总览' }}</p>
                </div>

                <div v-if="selectedAvailabilityDate" class="availability-detail-body">
                  <div :class="['availability-current-status', `is-${availabilityDayForm.status}`]">
                    <span>{{ availabilityStatusLabel(availabilityDayForm.status) }}</span>
                  </div>

                  <div class="availability-field">
                    <span class="availability-field-label">状态</span>
                    <el-radio-group v-model="availabilityDayForm.status" class="availability-status-toggle">
                      <el-radio-button value="free">可约</el-radio-button>
                      <el-radio-button value="busy">忙碌</el-radio-button>
                    </el-radio-group>
                  </div>

                  <div class="availability-field">
                    <span class="availability-field-label">所在地</span>
                    <el-input
                      v-model="availabilityDayForm.location"
                      maxlength="60"
                      clearable
                      placeholder="如：上海 / 杭州"
                    />
                  </div>

                  <div class="availability-detail-actions">
                    <el-button type="primary" @click="applyAvailabilityDayForm">更新这一天</el-button>
                    <el-button @click="clearSelectedAvailability">恢复默认</el-button>
                  </div>
                </div>

                <div v-else class="availability-empty-detail">
                  <strong>{{ availabilityMonthStats.total }}</strong>
                  <span>天可管理档期</span>
                </div>

                <div class="availability-presets">
                  <div class="availability-section-title">快速排期</div>
                  <div class="availability-preset-list">
                    <el-button @click="applyAvailabilityQuickAction('next-month-busy')">下个月都忙碌</el-button>
                    <el-button @click="applyAvailabilityQuickAction('weekdays-busy')">本月周中忙碌</el-button>
                    <el-button @click="applyAvailabilityQuickAction('weekends-busy')">本月周末忙碌</el-button>
                    <el-button @click="applyAvailabilityQuickAction('clear-month-busy')">清空本月忙碌</el-button>
                  </div>
                </div>
              </aside>
            </div>

            <div v-if="availabilityMultiSelect && selectedAvailabilityKeys.length" class="availability-bulk-bar">
              <div class="availability-bulk-summary">
                <strong>{{ selectedAvailabilityKeys.length }}</strong>
                <span>{{ selectedAvailabilityRangeLabel }}</span>
              </div>
              <div class="availability-bulk-location">
                <el-checkbox v-model="availabilityRangeForm.applyLocation">同步所在地</el-checkbox>
                <el-input
                  v-model="availabilityRangeForm.location"
                  maxlength="60"
                  clearable
                  placeholder="所在地"
                  :disabled="!availabilityRangeForm.applyLocation"
                />
              </div>
              <div class="availability-bulk-actions">
                <el-button @click="applyBulkAvailability('free')">设为可约</el-button>
                <el-button type="danger" plain @click="applyBulkAvailability('busy')">设为忙碌</el-button>
                <el-button text @click="resetAvailabilityRange">取消选择</el-button>
              </div>
            </div>
          </div>
        </template>
        <PhotographerApplicationGate v-else-if="activeTab === 'availability'" />
      </el-tab-pane>

      <el-tab-pane v-if="isPhotographerMode" label="数据仪表盘" name="stats">
        <template v-if="canUsePhotographerFeatures">
          <PhotographerStats />
        </template>
        <PhotographerApplicationGate v-else-if="activeTab === 'stats'" />
      </el-tab-pane>
    </el-tabs>

    <!-- 编辑资料弹窗 -->
    <el-dialog v-model="showEditDialog" title="编辑个人资料" width="500px">
      <el-form :model="editForm" label-width="120px">
        <el-form-item label="昵称">
          <el-input v-model="editForm.display_name" />
        </el-form-item>
        <el-form-item label="个人简介">
          <el-input v-model="editForm.bio" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="公开邮箱" v-if="canUsePhotographerFeatures">
          <el-switch v-model="showEmailOnProfile" :disabled="!email" />
          <span class="security-hint inline-hint">仅展示已验证邮箱，这是公开信息。</span>
        </el-form-item>
        <template v-if="canUsePhotographerFeatures">
          <el-divider content-position="left">摄影师信息</el-divider>
          <el-form-item label="地区"><RegionSelector v-model="editForm.location" /></el-form-item>
          <el-form-item label="设备信息"><el-input v-model="editForm.equipment" /></el-form-item>
          <el-form-item label="风格领域">
            <TagInput v-model="styleTags" placeholder="输入风格领域后按回车添加，如：人像" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button plain @click="showSecurityDialog = true">账户与安全</el-button>
        <el-button type="primary" @click="saveProfile" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showSecurityDialog" title="账户与安全" width="520px">
      <section class="security-section">
        <div class="security-row">
          <div>
            <strong>用户 ID</strong>
            <p class="security-value">{{ userId || '—' }}</p>
            <p class="security-hint">系统生成的唯一数字标识，不可修改。</p>
          </div>
          <el-tag type="info">不可修改</el-tag>
        </div>
        <div class="security-row">
          <div>
            <strong>用户名</strong>
            <p class="security-value">@{{ username || '尚未设置' }}</p>
            <p class="security-hint">注册时设置，可用于登录，不可修改。</p>
          </div>
          <el-tag type="info">不可修改</el-tag>
        </div>
        <div class="security-row">
          <div><strong>手机号</strong><p class="security-value">{{ phone || '未绑定' }}</p></div>
          <div class="security-actions"><el-tag :type="phoneVerified ? 'success' : phone ? 'warning' : 'info'">{{ phoneVerified ? '已验证' : phone ? '待验证' : '未绑定' }}</el-tag><el-button size="small" @click="openIdentityBinding('phone')">{{ phone ? '更换' : '绑定' }}</el-button></div>
        </div>
        <div class="security-row">
          <div><strong>邮箱</strong><p class="security-value">{{ email || pendingEmail || '未绑定' }}</p></div>
          <div class="security-actions"><el-tag :type="email ? 'success' : pendingEmail ? 'warning' : 'info'">{{ email ? '已验证' : pendingEmail ? '待验证' : '未绑定' }}</el-tag><el-button size="small" @click="openIdentityBinding('email')">{{ email ? '更换' : '绑定' }}</el-button></div>
        </div>
        <el-divider />
        <el-form :model="passwordForm" label-position="top">
          <el-form-item label="当前密码"><el-input v-model="passwordForm.current_password" type="password" show-password autocomplete="current-password" /></el-form-item>
          <el-form-item label="新密码"><el-input v-model="passwordForm.new_password" type="password" show-password autocomplete="new-password" /></el-form-item>
          <el-form-item label="确认新密码"><el-input v-model="passwordForm.confirm_password" type="password" show-password autocomplete="new-password" /></el-form-item>
          <el-button type="primary" :loading="changingPassword" @click="changeMyPassword">修改密码</el-button>
        </el-form>
        <el-divider />
        <div class="security-row security-danger-row">
          <div><strong>退出全部设备</strong><p class="security-hint">会立即使其他设备上的登录令牌失效。</p></div>
          <el-button type="danger" plain @click="logoutAllDevices">退出全部</el-button>
        </div>
      </section>
    </el-dialog>

    <el-dialog v-model="showIdentityBindingDialog" :title="bindingChannel === 'phone' ? '绑定手机号' : '绑定邮箱'" width="420px" append-to-body>
      <el-form label-position="top">
        <el-form-item :label="bindingChannel === 'phone' ? '手机号' : '邮箱'">
          <el-input v-model="bindingTarget" :type="bindingChannel === 'phone' ? 'tel' : 'email'" :disabled="Boolean(bindingChallengeId)" />
        </el-form-item>
        <el-form-item v-if="bindingChallengeId" label="验证码">
          <el-input v-model="bindingCode" inputmode="numeric" autocomplete="one-time-code" />
        </el-form-item>
      </el-form>
      <p class="security-hint">验证成功后，该{{ bindingChannel === 'phone' ? '手机号' : '邮箱' }}即可用于登录。</p>
      <template #footer>
        <el-button @click="showIdentityBindingDialog = false">取消</el-button>
        <el-button v-if="!bindingChallengeId" type="primary" :loading="sendingBindingCode" @click="requestIdentityBinding">获取验证码</el-button>
        <el-button v-else type="primary" :loading="confirmingIdentityBinding" @click="confirmIdentityBinding">确认绑定</el-button>
      </template>
    </el-dialog>

    <!-- 方案弹窗 -->
    <el-dialog v-model="showPackageDialog" :title="editingPackageIndex >= 0 ? '编辑方案' : '添加方案'" width="550px" @closed="resetPackageForm">
      <el-form :model="packageForm" label-width="100px">
        <el-form-item label="方案名称"><el-input v-model="packageForm.name" placeholder="如：个人写真" /></el-form-item>
        <el-form-item label="价格（元）"><el-input-number v-model="packageForm.price" :min="0" :step="100" style="width:100%" /></el-form-item>
        <el-form-item label="时长（分钟）"><el-input-number v-model="packageForm.duration" :min="30" :step="30" style="width:100%" /></el-form-item>
        <el-form-item label="风格领域">
          <TagInput v-model="packageStyleTags" placeholder="输入风格领域后按回车添加，如：复古" />
        </el-form-item>
        <el-form-item label="所在城市">
          <el-input v-model="packageForm.city" placeholder="留空表示不限制城市" clearable />
        </el-form-item>
        <el-form-item label="描述"><el-input v-model="packageForm.description" type="textarea" :rows="2" placeholder="方案简介" /></el-form-item>
        <el-form-item label="示例图">
          <el-upload
            v-model:file-list="sampleFiles"
            :auto-upload="false"
            list-type="picture-card"
            accept="image/*"
            multiple
          >
            <el-icon><Plus /></el-icon>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPackageDialog = false">取消</el-button>
        <el-button type="primary" @click="savePackage" :loading="uploadingSamples">确定</el-button>
      </template>
    </el-dialog>

    <!-- 交付作品弹窗 -->
    <el-dialog v-model="showDeliveryDialog" title="交付作品" width="500px" @closed="resetDeliveryForm">
      <el-form label-width="80px">
        <el-form-item label="上传作品">
          <el-upload
            v-model:file-list="deliveryFiles"
            :auto-upload="false"
            list-type="picture-card"
            accept="image/*"
            multiple
          >
            <el-icon><Plus /></el-icon>
          </el-upload>
        </el-form-item>
        <el-form-item label="交付说明">
          <el-input
            v-model="deliveryDescription"
            type="textarea"
            :rows="3"
            placeholder="如：精修已完成，请查收"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDeliveryDialog = false">取消</el-button>
        <el-button type="primary" @click="submitDelivery" :loading="submittingDelivery">确认交付</el-button>
      </template>
    </el-dialog>

    <!-- 查看作品弹窗 -->
    <el-dialog v-model="showViewDialog" title="交付作品" width="700px">
      <div v-if="currentViewOrder?.delivery?.description" class="view-desc">
        {{ currentViewOrder.delivery.description }}
      </div>
      <div class="view-images">
        <el-image
          v-for="(img, i) in (currentViewOrder?.delivery?.images || [])"
          :key="i"
          :src="getFullUrl(img)"
          fit="cover"
          class="delivery-img"
          :preview-src-list="(currentViewOrder?.delivery?.images || []).map(getFullUrl)"
          :initial-index="i"
        />
      </div>
      <el-empty v-if="!currentViewOrder?.delivery?.images?.length" description="暂无交付作品" />
    </el-dialog>

    <!-- 评价弹窗 -->
    <el-dialog v-model="showReviewDialog" title="评价作品" width="450px" @closed="resetReviewForm">
      <el-form label-width="80px">
        <el-form-item label="评分">
          <el-rate v-model="reviewRating" :max="10" show-score score-template="{value} 分" />
        </el-form-item>
        <el-form-item label="评价内容">
          <el-input v-model="reviewText" type="textarea" :rows="4" placeholder="分享您的拍摄体验..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showReviewDialog = false">取消</el-button>
        <el-button type="primary" @click="submitReview" :loading="submittingReview">提交评价</el-button>
      </template>
    </el-dialog>

    <!-- 查看评价弹窗 -->
    <el-dialog v-model="showViewReviewDialog" title="客户评价" width="450px">
      <div class="review-score">
        <el-rate v-model="currentReviewOrderRating" :max="10" disabled show-score score-template="{value} 分" />
      </div>
      <div class="review-text-content" v-if="currentReviewOrder?.review_text">
        {{ currentReviewOrder.review_text }}
      </div>
      <el-empty v-else description="暂无评价文字" />
    </el-dialog>

  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft,
  ArrowRight,
  Camera,
  Check,
  Eye as View,
  LoaderCircle as Loading,
  Pencil as Edit,
  Play as VideoPlay,
  Plus,
  RefreshCw as Refresh,
  Ticket as Tickets,
  Trash2 as Delete,
} from 'lucide-vue-next'
import api from '../utils/api'
import { getMyCustomerOrders, getMyPhotographerOrders, confirmOrder, rejectOrder, deliverWorks, acceptOrder, reviewOrder, startOrder } from '../api/order'
import { getMyApplications, getMyProjects, closeProject } from '../api/project'
import { getUserFavorites, getUserPackageFavorites } from '@/api/favorite'
import { getUserLikedWorks } from '@/api/like'
import PhotographerStats from '../components/PhotographerStats.vue'
import PhotographerApplicationGate from '../components/PhotographerApplicationGate.vue'
import TagInput from '../components/TagInput.vue'
import RegionSelector from '../components/RegionSelector.vue'
import FollowCounts from '../components/FollowCounts.vue'
import { getFollowCounts } from '@/api/follow'
import { useImageAspectRatio } from '@/composables/useImageAspectRatio'
import { useProfileMode, normalizeProfileMode } from '@/composables/useProfileMode'
import LikeButton from '../components/LikeButton.vue'
import { useLikeStore } from '@/stores/like'
import {
  getFavoritePackagePreviewUrl as getFavoritePackageCardPreviewUrl,
  getFavoriteWorkPreviewUrl,
  getVideoStreamUrl,
  getWorkPreviewUrl,
  isVideoWork,
} from '@/utils/imagePreview'
import { promptRejectReason } from '@/utils/orderRejectPrompt'
import { deleteWorkDraft, listWorkDrafts } from '@/utils/workDrafts'

const router = useRouter()
const route = useRoute()
const userRole = ref('customer')
const { profileMode, initProfileMode, setProfileMode } = useProfileMode()
const likeStore = useLikeStore()
const userId = ref(null)
const displayName = ref('')
const username = ref('')
const phone = ref('')
const phoneVerified = ref(false)
const email = ref('')
const pendingEmail = ref('')
const showEmailOnProfile = ref(false)

const followCounts = reactive({
  following_count: 0,
  follower_count: 0,
})
const failedWorkPreviews = reactive({})
const bio = ref('')
const bioParagraphs = computed(() => {
  if (!bio.value) return []
  return bio.value.split('\n\n').filter(p => p.trim())
})
const bioHeightMode = computed(() => {
  const count = bioParagraphs.value.length
  if (count <= 1) return 'min'
  if (count === 2) return 'medium'
  return 'max'
})
const avatarUrl = ref('')
const loadingWorks = ref(false)
const loadingWorkDrafts = ref(false)
const portfolio = ref([])
const workDrafts = ref([])
const packagesList = ref([])
const loadingAvailability = ref(false)
const savingAvailability = ref(false)
const availabilityDays = ref({})
const maxBookingDate = ref('')
const availabilityCurrentMonth = ref(new Date(new Date().getFullYear(), new Date().getMonth(), 1))
const availabilityMultiSelect = ref(false)
const availabilityRangeStart = ref('')
const availabilityRangeEnd = ref('')
const selectedAvailabilityDate = ref('')
const availabilityDayForm = reactive({ status: 'free', location: '' })
const availabilityRangeForm = reactive({ status: 'busy', applyLocation: false, location: '' })
const favItems = ref([])
const loadingFavs = ref(false)
const likedWorkItems = ref([])
const loadingLikedWorks = ref(false)

// 收藏作品/方案切换
const pkgFavItems = ref([])
const loadingPkgFavs = ref(false)

// 我的应邀
const applications = ref([])
const loadingApplications = ref(false)
const applicationFilter = ref('all')

// 我的企划
const projects = ref([])
const loadingProjects = ref(false)
const projectFilter = ref('all')

const { getOrPreload } = useImageAspectRatio()

const ROLE_PROFILE_TABS = {
  photographer: new Set(['works', 'orders', 'applications', 'pkg-mgmt', 'availability', 'stats']),
  customer: new Set(['works', 'orders', 'my-projects', 'favorites', 'likes']),
}
const FAVORITE_TABS = new Set(['works', 'packages'])

const getQueryValue = (value) => Array.isArray(value) ? value[0] : value

const normalizeRole = normalizeProfileMode
const canUsePhotographerFeatures = computed(() => userRole.value === 'photographer')
const isPhotographerMode = computed(() => profileMode.value === 'photographer')
const isCustomerMode = computed(() => profileMode.value === 'customer')
const isOrdersTabVisible = computed(() => isPhotographerMode.value || isCustomerMode.value)
const isPhotographerOrdersMode = computed(() => isPhotographerMode.value && canUsePhotographerFeatures.value)
const canViewCurrentModeOrders = computed(() => isCustomerMode.value || isPhotographerOrdersMode.value)

const isTabAvailableForMode = (tab, mode = profileMode.value) => {
  const tabs = ROLE_PROFILE_TABS[normalizeRole(mode)]
  return Boolean(tab && tabs?.has(tab))
}

const normalizeProfileTab = (value, mode = profileMode.value) => {
  const tab = getQueryValue(value)
  return isTabAvailableForMode(tab, mode) ? tab : 'works'
}

const normalizeFavoriteTab = (value) => {
  const tab = getQueryValue(value)
  return FAVORITE_TABS.has(tab) ? tab : 'works'
}

const activeTab = ref(normalizeProfileTab(route.query.tab, profileMode.value))
const favTab = ref(normalizeFavoriteTab(route.query.fav))

const getProfileRouteForState = (tab = activeTab.value, favorite = favTab.value) => {
  const normalizedTab = normalizeProfileTab(tab, profileMode.value)
  const query = {}
  if (normalizedTab && normalizedTab !== 'works') {
    query.tab = normalizedTab
  }
  if (normalizedTab === 'favorites') {
    query.fav = FAVORITE_TABS.has(favorite) ? favorite : 'works'
  }
  return { path: '/profile', query }
}

const syncProfileRouteState = () => {
  if (route.path !== '/profile') return
  const target = getProfileRouteForState()
  const targetFullPath = router.resolve(target).fullPath
  const currentFullPath = route.fullPath || route.path
  if (currentFullPath !== targetFullPath) {
    router.replace(target)
  }
}

const toggleProfileMode = () => {
  const next = profileMode.value === 'photographer' ? 'customer' : 'photographer'
  switchProfileMode(next)
}

const switchProfileMode = (mode) => {
  setProfileMode(mode)
  activeTab.value = normalizeProfileTab(activeTab.value, profileMode.value)
  loadProfileTabData(activeTab.value)
  syncProfileRouteState()
}

const ensureFavoriteReturnRoute = async (favorite) => {
  const target = getProfileRouteForState('favorites', favorite)
  const targetFullPath = router.resolve(target).fullPath
  const currentFullPath = route.fullPath || route.path
  if (route.path === '/profile' && currentFullPath !== targetFullPath) {
    await router.replace(target)
  }
  return targetFullPath
}

const ensureLikedWorksReturnRoute = async () => {
  const target = getProfileRouteForState('likes')
  const targetFullPath = router.resolve(target).fullPath
  const currentFullPath = route.fullPath || route.path
  if (route.path === '/profile' && currentFullPath !== targetFullPath) {
    await router.replace(target)
  }
  return targetFullPath
}

const getFullUrl = (url) => {
  if (!url) return ''
  if (url.startsWith('http')) return url
  return url
}

const ratioKey = (type, id) => (id ? `${type}:${id}` : '')

const getPortfolioPreviewRatio = (work) => {
  if (shouldUseVideoElementPreview(work)) return '16/9'
  const url = getWorkPreviewUrl(work)
  return getOrPreload(url, ratioKey('profile-work', work?.id || work?.url))
}

const revokeDraftPreviewUrls = () => {
  workDrafts.value.forEach((draft) => {
    if (draft.previewUrl) URL.revokeObjectURL(draft.previewUrl)
  })
}

const buildDraftPreviewUrl = (draft) => {
  const file = Array.isArray(draft.files) ? draft.files[0] : null
  return file ? URL.createObjectURL(file) : ''
}

const loadWorkDrafts = async () => {
  if (!userId.value) return
  loadingWorkDrafts.value = true
  try {
    const drafts = await listWorkDrafts(userId.value)
    revokeDraftPreviewUrls()
    workDrafts.value = drafts.map((draft) => ({
      ...draft,
      previewUrl: buildDraftPreviewUrl(draft),
    }))
  } catch {
    revokeDraftPreviewUrls()
    workDrafts.value = []
  } finally {
    loadingWorkDrafts.value = false
  }
}

const getWorkPreviewFailureKey = (work) => `${work?.id || work?.url || ''}:${work?.thumbnail_url || ''}`

const shouldUseVideoElementPreview = (work) => {
  if (!isVideoWork(work)) return false
  const videoUrl = getVideoStreamUrl(work)
  if (!videoUrl) return false
  const previewUrl = getWorkPreviewUrl(work)
  return !previewUrl || Boolean(failedWorkPreviews[getWorkPreviewFailureKey(work)])
}

const handleWorkPreviewError = (work) => {
  if (!isVideoWork(work)) return
  const key = getWorkPreviewFailureKey(work)
  if (key) failedWorkPreviews[key] = true
}

const getFavoriteWorkPreviewRatio = (item) => {
  const url = getFavoriteWorkPreviewUrl(item)
  return getOrPreload(url, ratioKey('favorite-work', item?.work_id || item?.work_data?.url))
}

const getLikedWorkPreviewRatio = (item) => {
  const url = getFavoriteWorkPreviewUrl(item)
  return getOrPreload(url, ratioKey('liked-work', item?.work_id || item?.work_data?.url))
}

const getFavoritePackageCoverUrl = (item) => {
  return getFavoritePackageCardPreviewUrl(item)
}

const getFavoritePackagePreviewRatio = (item) => {
  const url = getFavoritePackageCoverUrl(item)
  return getOrPreload(url, ratioKey('favorite-package', item?.package_id || url))
}

const getManagedPackageCoverUrl = (pkg) => {
  return getFullUrl(pkg?.sample_thumbnails?.[0] || pkg?.samples?.[0] || '')
}

const getManagedPackageKey = (pkg, index) => {
  return ratioKey('managed-package', pkg?.id || pkg?.name || pkg?.package_name || index)
}

const avatarSrc = computed(() => {
  if (avatarPreviewUrl.value) return avatarPreviewUrl.value
  return getFullUrl(avatarUrl.value)
})

// ---- 编辑资料 ----
const showEditDialog = ref(false)
const saving = ref(false)
const editForm = ref({ display_name: '', bio: '', location: '', equipment: '' })
const styleTags = ref([])
const showSecurityDialog = ref(false)
const changingPassword = ref(false)
const passwordForm = reactive({ current_password: '', new_password: '', confirm_password: '' })
const showIdentityBindingDialog = ref(false)
const bindingChannel = ref('phone')
const bindingTarget = ref('')
const bindingCode = ref('')
const bindingChallengeId = ref('')
const sendingBindingCode = ref(false)
const confirmingIdentityBinding = ref(false)

const openEditDialog = () => {
  editForm.value.display_name = displayName.value
  editForm.value.bio = bio.value
  showEditDialog.value = true
}

const openIdentityBinding = (channel) => {
  bindingChannel.value = channel
  bindingTarget.value = channel === 'phone' ? phone.value : (email.value || pendingEmail.value)
  bindingCode.value = ''
  bindingChallengeId.value = ''
  showIdentityBindingDialog.value = true
}

const requestIdentityBinding = async () => {
  if (!bindingTarget.value.trim()) return ElMessage.warning(`请输入${bindingChannel.value === 'phone' ? '手机号' : '邮箱'}`)
  sendingBindingCode.value = true
  try {
    const { data } = await api.post(`/users/me/${bindingChannel.value}/request`, { target: bindingTarget.value.trim() })
    bindingChallengeId.value = data.challenge_id
    ElMessage.success('验证码已发送')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '验证码发送失败')
  } finally { sendingBindingCode.value = false }
}

const confirmIdentityBinding = async () => {
  if (!bindingCode.value.trim()) return ElMessage.warning('请输入验证码')
  confirmingIdentityBinding.value = true
  try {
    const verification = await api.post('/auth/verifications/confirm', { challenge_id: bindingChallengeId.value, code: bindingCode.value.trim() })
    const { data } = await api.post(`/users/me/${bindingChannel.value}/confirm`, { verification_token: verification.data.verification_token })
    phone.value = data.phone || ''
    phoneVerified.value = Boolean(data.phone_verified)
    email.value = data.email || ''
    pendingEmail.value = data.pending_email || ''
    showIdentityBindingDialog.value = false
    ElMessage.success('绑定成功，现在可以用于登录')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '验证失败')
  } finally { confirmingIdentityBinding.value = false }
}

const changeMyPassword = async () => {
  if (passwordForm.new_password !== passwordForm.confirm_password) {
    ElMessage.error('两次输入的新密码不一致')
    return
  }
  changingPassword.value = true
  try {
    await api.post('/users/me/change-password', {
      current_password: passwordForm.current_password,
      new_password: passwordForm.new_password,
    })
    localStorage.removeItem('token')
    ElMessage.success('密码已修改，请重新登录')
    await router.replace('/login')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '密码修改失败')
  } finally { changingPassword.value = false }
}

const logoutAllDevices = async () => {
  try {
    await ElMessageBox.confirm('这会使所有设备重新登录，确定继续吗？', '退出全部设备', { type: 'warning' })
    await api.post('/users/me/logout-all')
    localStorage.removeItem('token')
    await router.replace('/login')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(error.response?.data?.detail || '操作失败')
  }
}

// ---- 头像 ----
const avatarFile = ref(null)
const avatarPreviewUrl = ref('')
const uploadingAvatar = ref(false)

const handleAvatarChange = async (file) => {
  avatarFile.value = file.raw
  avatarPreviewUrl.value = URL.createObjectURL(file.raw)
  uploadingAvatar.value = true
  try {
    const fd = new FormData()
    fd.append('file', file.raw)
    const res = await api.post('/users/me/avatar', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
    avatarUrl.value = res.data.avatar_url
    ElMessage.success('头像已更新')
  } catch {
    ElMessage.error('头像上传失败')
    avatarPreviewUrl.value = ''
  } finally {
    uploadingAvatar.value = false
    avatarFile.value = null
  }
}

// ---- 背景图 ----
const bgInputRef = ref(null)
const backgroundUrl = ref('')
const backgroundPreviewUrl = ref('')
const uploadingBackground = ref(false)

const triggerBackgroundUpload = () => {
  bgInputRef.value?.click()
}

/**
 * 将图片按 cover 模式裁切并缩放至指定尺寸，返回裁切后的 Blob
 */
const cropImageToCover = (file, targetWidth = 1200, targetHeight = 400) => {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = targetWidth
      canvas.height = targetHeight
      const ctx = canvas.getContext('2d')

      // cover 算法：计算缩放比，取较大值
      const scaleX = targetWidth / img.width
      const scaleY = targetHeight / img.height
      const scale = Math.max(scaleX, scaleY)

      const scaledW = img.width * scale
      const scaledH = img.height * scale

      // 居中裁剪
      const sx = (scaledW - targetWidth) / 2 / scale
      const sy = (scaledH - targetHeight) / 2 / scale
      const sw = targetWidth / scale
      const sh = targetHeight / scale

      ctx.drawImage(img, sx, sy, sw, sh, 0, 0, targetWidth, targetHeight)

      canvas.toBlob((blob) => {
        if (blob) resolve(blob)
        else reject(new Error('图片裁切失败'))
      }, 'image/jpeg', 0.92)
    }
    img.onerror = () => reject(new Error('图片加载失败'))
    img.src = URL.createObjectURL(file)
  })
}

const handleBackgroundChange = async (event) => {
  const file = event.target.files?.[0]
  if (!file) return

  // 显示本地预览
  backgroundPreviewUrl.value = URL.createObjectURL(file)
  uploadingBackground.value = true

  try {
    // 裁切图片（cover 模式，1200x400 适应卡片比例）
    const croppedBlob = await cropImageToCover(file, 1200, 400)
    const croppedFile = new File([croppedBlob], file.name.replace(/\.[^.]+$/, '.jpg'), { type: 'image/jpeg' })

    const fd = new FormData()
    fd.append('file', croppedFile)
    const res = await api.post('/users/me/background', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    backgroundUrl.value = res.data.background_url || res.data.url || ''
    ElMessage.success('背景图已更新')
  } catch {
    ElMessage.error('背景图上传失败')
    backgroundPreviewUrl.value = ''
  } finally {
    uploadingBackground.value = false
    // 重置 input 以允许重复选择同一文件
    if (bgInputRef.value) bgInputRef.value.value = ''
  }
}

// ---- 数据加载 ----
const fetchUserData = async () => {
  try {
    const meRes = await api.get('/users/me')
    const me = meRes.data
    const resolvedRole = normalizeRole(me.role)
    userRole.value = resolvedRole
    userId.value = me.id || null
    initProfileMode({ userId: userId.value, role: resolvedRole })
    displayName.value = me.display_name || ''
    username.value = me.username || ''
    phone.value = me.phone || ''
    phoneVerified.value = Boolean(me.phone_verified)
    email.value = me.email || ''
    pendingEmail.value = me.pending_email || ''
    showEmailOnProfile.value = Boolean(me.show_email_on_profile)
    bio.value = me.bio || ''
    avatarUrl.value = me.avatar_url || ''
    backgroundUrl.value = me.background_url || ''
    activeTab.value = normalizeProfileTab(route.query.tab, profileMode.value)

    // 在 userId 赋值后加载关注/粉丝计数
    fetchFollowCounts()

    loadingAvailability.value = true
    try {
      const pRes = await api.get(`/photographers/profile/${me.id}`, { skipErrorHandler: true })
      const p = pRes.data
      portfolio.value = p.portfolio || []
      packagesList.value = p.packages || []
      availabilityDays.value = hydrateAvailabilityDays(p.availability_exceptions || [])
      maxBookingDate.value = p.max_booking_date || ''
      editForm.value.location = p.location || ''
      editForm.value.equipment = p.equipment || ''
      styleTags.value = p.styles || []
      // 加载作品点赞状态
      const ids = portfolio.value.map((w) => w.id).filter(Boolean)
      if (ids.length) await likeStore.loadMany('portfolio', ids)
    } catch {
      portfolio.value = []
      packagesList.value = []
      availabilityDays.value = {}
    } finally {
      loadingAvailability.value = false
    }
    loadProfileTabData(activeTab.value)
    syncProfileRouteState()
  } catch {}
}

// ---- 订单 ----
const orders = ref([])
const loadingOrders = ref(false)
const orderFilter = ref('all')

const countByStatus = (items, statuses) => {
  const statusSet = new Set(Array.isArray(statuses) ? statuses : [statuses])
  return items.filter(item => statusSet.has(item.status)).length
}

const orderFilterOptions = computed(() => [
  { key: 'all', label: '全部', count: orders.value.length },
  { key: 'pending', label: '待确认', count: countByStatus(orders.value, 'pending') },
  { key: 'active', label: isPhotographerOrdersMode.value ? '待交付' : '待接收', count: isPhotographerOrdersMode.value ? countByStatus(orders.value, ['confirmed', 'in_progress']) : countByStatus(orders.value, 'delivered') },
  { key: 'done', label: '已完成', count: countByStatus(orders.value, ['reviewed', 'completed']) },
])

const filteredOrders = computed(() => {
  if (orderFilter.value === 'pending') return orders.value.filter(o => o.status === 'pending')
  if (orderFilter.value === 'active') {
    return isPhotographerOrdersMode.value
      ? orders.value.filter(o => o.status === 'confirmed' || o.status === 'in_progress')
      : orders.value.filter(o => o.status === 'delivered')
  }
  if (orderFilter.value === 'done') return orders.value.filter(o => o.status === 'reviewed' || o.status === 'completed')
  return orders.value
})

const applicationFilterOptions = computed(() => [
  { key: 'all', label: '全部', count: applications.value.length },
  { key: 'selected', label: '被选中', count: countByStatus(applications.value, 'selected') },
  { key: 'submitted', label: '待结果', count: countByStatus(applications.value, 'submitted') },
])

const filteredApplications = computed(() => {
  if (applicationFilter.value === 'selected') return applications.value.filter(a => a.status === 'selected')
  if (applicationFilter.value === 'submitted') return applications.value.filter(a => a.status === 'submitted')
  return applications.value
})

const projectFilterOptions = computed(() => [
  { key: 'all', label: '全部', count: projects.value.length },
  { key: 'open', label: '招募中', count: countByStatus(projects.value, 'open') },
  { key: 'expired', label: '已过期', count: countByStatus(projects.value, 'expired') },
  { key: 'converted', label: '已转订单', count: countByStatus(projects.value, 'converted') },
])

const favoriteFilterOptions = computed(() => [
  { key: 'works', label: '作品收藏', count: favItems.value.length },
  { key: 'packages', label: '方案收藏', count: pkgFavItems.value.length },
])

const filteredProjects = computed(() => {
  if (projectFilter.value === 'open') return projects.value.filter(p => p.status === 'open')
  if (projectFilter.value === 'expired') return projects.value.filter(p => p.status === 'expired')
  if (projectFilter.value === 'converted') return projects.value.filter(p => p.status === 'converted')
  return projects.value
})

const fetchOrders = async () => {
  if (!canViewCurrentModeOrders.value) {
    orders.value = []
    return
  }
  loadingOrders.value = true
  try {
    const request = isPhotographerOrdersMode.value ? getMyPhotographerOrders : getMyCustomerOrders
    const res = await request()
    orders.value = res.data
  } finally {
    loadingOrders.value = false
  }
}

// ---- 我的应邀 ----
const fetchApplications = async () => {
  if (!canUsePhotographerFeatures.value) {
    applications.value = []
    return
  }
  loadingApplications.value = true
  try {
    const res = await getMyApplications()
    applications.value = res.data
  } finally {
    loadingApplications.value = false
  }
}

// ---- 我的企划 ----
const fetchMyProjects = async () => {
  loadingProjects.value = true
  try {
    const res = await getMyProjects()
    projects.value = res.data
  } finally {
    loadingProjects.value = false
  }
}

const closeProjectRow = async (row) => {
  try {
    await ElMessageBox.confirm('关闭后不可继续接收应邀。', '关闭企划', { type: 'warning' })
  } catch {
    return
  }
  await closeProject(row.id, '用户关闭企划')
  ElMessage.info('企划已关闭')
  fetchMyProjects()
}

const appStatusLabel = (value) => ({ submitted: '已提交', selected: '被选中', rejected: '未选中', withdrawn: '已撤回' }[value] || value)
const appStatusType = (value) => ({ submitted: 'warning', selected: 'success', rejected: 'info', withdrawn: 'info' }[value] || '')
const projectStatusLabel = (value) => ({ draft: '草稿', open: '招募中', converted: '已转订单', closed: '已关闭', cancelled: '已取消', expired: '已过期' }[value] || value)
const projectStatusType = (value) => ({ draft: 'info', open: 'success', converted: 'primary', closed: 'info', cancelled: 'danger', expired: 'warning' }[value] || '')

const formatBudget = (row) => {
  if (row.budget_min && row.budget_max) return `¥${row.budget_min} - ¥${row.budget_max}`
  if (row.budget_min) return `¥${row.budget_min} 起`
  if (row.budget_max) return `¥${row.budget_max} 内`
  return '待沟通'
}

const formatProjectBudget = (project) => {
  if (!project) return '-'
  if (project.budget_min && project.budget_max) return `¥${project.budget_min} - ¥${project.budget_max}`
  if (project.budget_min) return `¥${project.budget_min} 起`
  if (project.budget_max) return `¥${project.budget_max} 内`
  return '待沟通'
}

const formatDate = (value) => value ? new Date(value).toLocaleString() : '-'

const handleConfirm = async (id) => {
  try { await ElMessageBox.confirm('确认接受？', '提示', { type: 'warning' }) } catch { return }
  await confirmOrder(id)
  ElMessage.success('已确认')
  fetchOrders()
}

const handleReject = async (id) => {
  let reason
  try { reason = await promptRejectReason() } catch { return }
  await rejectOrder(id, reason)
  ElMessage.info('已拒绝')
  fetchOrders()
}

const handleStart = async (id) => {
  try { await ElMessageBox.confirm('确认开始本次服务？', '开始服务', { type: 'warning' }) } catch { return }
  await startOrder(id)
  ElMessage.success('订单已进入履约中')
  fetchOrders()
}

// ---- 评价 ----
const showReviewDialog = ref(false)
const submittingReview = ref(false)
const reviewRating = ref(0)
const reviewText = ref('')
const currentReviewOrder = ref(null)

const openReviewDialog = (order) => {
  currentReviewOrder.value = order
  reviewRating.value = 0
  reviewText.value = ''
  showReviewDialog.value = true
}

const resetReviewForm = () => {
  currentReviewOrder.value = null
}

const submitReview = async () => {
  if (!reviewRating.value) {
    ElMessage.warning('请给出评分')
    return
  }
  submittingReview.value = true
  try {
    await reviewOrder(currentReviewOrder.value.id, {
      rating: reviewRating.value,
      review_text: reviewText.value || undefined
    })
    ElMessage.success('评价已提交')
    showReviewDialog.value = false
    fetchOrders()
  } catch {
  } finally {
    submittingReview.value = false
  }
}

// ---- 查看评价 ----
const showViewReviewDialog = ref(false)
const currentReviewOrderRating = ref(0)

const openViewReview = (order) => {
  currentReviewOrder.value = order
  currentReviewOrderRating.value = order.rating || 0
  showViewReviewDialog.value = true
}

const statusType = (s) => ({ pending: 'warning', awaiting_customer_payment: 'warning', confirmed: 'success', reschedule_requested: 'warning', in_progress: 'success', delivered: 'warning', received: 'success', reviewed: 'success', completed: 'success', cancelled: 'info' }[s] || '')
const statusLabel = (s) => ({ pending: '待确认', awaiting_customer_payment: '待支付', confirmed: '已确认', reschedule_requested: '改期待确认', in_progress: '拍摄中/待交付', delivered: '待验收', received: '已完成', reviewed: '已完成', completed: '已完成', cancelled: '已取消' }[s] || s)

const formatProfileDateOnly = value => value
  ? new Date(value).toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
  : '-'
const formatProfileOrderTitle = value => String(value || '摄影服务')
  .replace(/\s*\/\s*\d+\s*(?:分钟|minutes?)/gi, '')
  .replace(/\s*时长\s*\d+\s*(?:分钟|小时)/gi, '')
  .trim()
const profileOrderActionLabel = row => {
  if (row.active_reschedule_request) return '处理改期'
  if (row.status === 'awaiting_customer_payment') return '去支付'
  if (row.status === 'delivered') return isPhotographerOrdersMode.value ? '查看交付' : '验收与查看'
  return '查看详情'
}

const orderNextText = (order) => {
  const status = order?.status
  if (isPhotographerOrdersMode.value) {
    return {
      pending: '请确认或拒绝预约',
      confirmed: order.active_reschedule_request ? '有待处理的改期申请，请进入详情' : '请开始服务',
      reschedule_requested: '客户申请改期，请进入详情确认',
      in_progress: '拍摄完成后交付作品',
      delivered: order.after_sales_status === 'revision_requested' ? '请重新交付修改版本' : '等待客户验收',
      received: '订单已完成，评价可选',
      reviewed: '订单已完成',
      completed: '订单已完成',
      cancelled: '订单已取消',
    }[status] || '查看详情'
  }
  return {
    pending: '等待摄影师确认',
    confirmed: order.active_reschedule_request ? '改期申请处理中，原档期继续有效' : '等待拍摄与交付',
    reschedule_requested: '改期申请待摄影师确认',
    in_progress: '等待摄影师交付',
    delivered: order.after_sales_status === 'revision_requested' ? '等待摄影师重新交付' : '请验收或申请修改',
    received: '订单已完成，可选评价',
    reviewed: '订单已完成',
    completed: order.rating ? '订单已完成并评价' : '订单已完成，可选评价',
    cancelled: '订单已取消',
  }[status] || '查看详情'
}

const goOrderDetail = (order) => {
  if (order?.id) {
    router.push(`/orders/${order.id}`)
  }
}

// ---- 接收作品 ----
const handleAccept = async (id) => {
  try { await ElMessageBox.confirm('确认接收作品？', '接收确认', { type: 'success' }) } catch { return }
  await acceptOrder(id)
  ElMessage.success('已接收作品')
  fetchOrders()
}

// ---- 交付作品 ----
const showDeliveryDialog = ref(false)
const submittingDelivery = ref(false)
const deliveryFiles = ref([])
const deliveryDescription = ref('')
const currentDeliverOrder = ref(null)

// ---- 查看作品 ----
const showViewDialog = ref(false)
const currentViewOrder = ref(null)

const openViewDelivery = (order) => {
  currentViewOrder.value = order
  showViewDialog.value = true
}

const openDeliveryDialog = (order) => {
  currentDeliverOrder.value = order
  showDeliveryDialog.value = true
}

const resetDeliveryForm = () => {
  deliveryFiles.value = []
  deliveryDescription.value = ''
  currentDeliverOrder.value = null
}

const submitDelivery = async () => {
  if (!deliveryFiles.value.length) {
    ElMessage.warning('请至少上传一张作品')
    return
  }
  submittingDelivery.value = true
  try {
    const formData = new FormData()
    deliveryFiles.value.forEach(file => {
      formData.append('files', file.raw)
    })
    formData.append('description', deliveryDescription.value)
    await deliverWorks(currentDeliverOrder.value.id, formData)
    ElMessage.success('作品已交付')
    showDeliveryDialog.value = false
    fetchOrders()
  } finally {
    submittingDelivery.value = false
  }
}

// ---- 保存资料 ----
const saveProfile = async () => {
  saving.value = true
  try {
    await api.patch('/users/me', {
      display_name: editForm.value.display_name,
      bio: editForm.value.bio,
      avatar_url: avatarUrl.value,
      show_email_on_profile: showEmailOnProfile.value,
    })
    displayName.value = editForm.value.display_name
    bio.value = editForm.value.bio

    if (canUsePhotographerFeatures.value) {
      await api.post('/photographers/profile', {
        location: editForm.value.location,
        equipment: editForm.value.equipment,
        styles: styleTags.value,
      })
    }
    showEditDialog.value = false
    ElMessage.success('资料已保存')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

// ---- 作品导航 ----
const goWorkDetail = (work) => {
  if (work && work.id) {
    router.push({ 
      path: `/work/${work.id}`, 
      state: { 
        from: router.currentRoute.value.fullPath,
        work: { ...work, user_id: userId.value, user_display_name: displayName.value, user_avatar_url: avatarUrl.value }
      } 
    })
  }
}

const isVideoDraft = (draft) => draft?.mediaType === 'video'

const formatDraftTime = (value) => {
  if (!value) return '刚刚保存'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '刚刚保存'
  return `保存于 ${date.toLocaleString('zh-CN')}`
}

const goWorkDraft = (draft) => {
  if (!draft?.id) return
  router.push({ path: '/upload-work', query: { draftId: draft.id } })
}

const deleteDraftCard = async (draft) => {
  if (!draft?.id) return
  try {
    await ElMessageBox.confirm('确定删除这个草稿吗？', '删除草稿', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }

  try {
    await deleteWorkDraft(draft.id)
    if (draft.previewUrl) URL.revokeObjectURL(draft.previewUrl)
    workDrafts.value = workDrafts.value.filter((item) => item.id !== draft.id)
    ElMessage.success('草稿已删除')
  } catch {
    ElMessage.error('草稿删除失败')
  }
}

const goFavoriteWork = async (item) => {
  if (item.work_id) {
    const returnTo = await ensureFavoriteReturnRoute('works')
    router.push({ path: `/work/${item.work_id}`, state: { from: returnTo, work: item.work_data } })
  }
}

const goLikedWork = async (item) => {
  if (item.work_id) {
    const returnTo = await ensureLikedWorksReturnRoute()
    router.push({ path: `/work/${item.work_id}`, state: { from: returnTo, work: item.work_data } })
  }
}

const goFavoritePackage = async (item) => {
  if (item.package_id) {
    const returnTo = await ensureFavoriteReturnRoute('packages')
    router.push({ path: `/package/${item.package_id}`, state: { from: returnTo } })
  }
}

// ---- 档期设置 ----
const availabilityWeekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const availabilityModeOptions = [
  { label: '单日', value: 'single' },
  { label: '多选', value: 'multi' },
]

const padDatePart = (value) => String(value).padStart(2, '0')

const toDateKey = (date) => (
  `${date.getFullYear()}-${padDatePart(date.getMonth() + 1)}-${padDatePart(date.getDate())}`
)

const parseDateKey = (key) => {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(key || '')
  if (!match) return null
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
  return Number.isNaN(date.getTime()) ? null : date
}

const startOfToday = () => {
  const now = new Date()
  return new Date(now.getFullYear(), now.getMonth(), now.getDate())
}

const addDays = (date, days) => {
  const next = new Date(date)
  next.setDate(next.getDate() + days)
  return next
}

const addMonths = (date, months) => new Date(date.getFullYear(), date.getMonth() + months, 1)

const availabilityMaxDate = computed(() => addDays(startOfToday(), 365))
const availabilityCurrentMonthStart = computed(() => {
  const today = startOfToday()
  return new Date(today.getFullYear(), today.getMonth(), 1)
})
const availabilityMaxMonthStart = computed(() => {
  const maxDate = availabilityMaxDate.value
  return new Date(maxDate.getFullYear(), maxDate.getMonth(), 1)
})

const isSameDateKey = (date, key) => toDateKey(date) === key
const compareDateKeys = (a, b) => a.localeCompare(b)
const normalizeAvailabilityStatus = (status) => status === 'busy' || status === 'closed' ? 'busy' : 'free'
const availabilityStatusLabel = (status) => normalizeAvailabilityStatus(status) === 'busy' ? '忙碌' : '可约'

const isAvailabilityDateAllowed = (date) => {
  const today = startOfToday()
  return date >= today && date <= availabilityMaxDate.value
}

const getAvailabilityDay = (dateKey) => availabilityDays.value[dateKey] || { status: 'free', location: '' }

const setAvailabilityDay = (dateKey, status = 'free', location) => {
  const date = parseDateKey(dateKey)
  if (!date || !isAvailabilityDateAllowed(date)) return

  const nextStatus = normalizeAvailabilityStatus(status)
  const current = getAvailabilityDay(dateKey)
  const nextLocation = typeof location === 'string' ? location.trim() : (current.location || '')
  const nextDays = { ...availabilityDays.value }

  if (nextStatus === 'free' && !nextLocation) {
    delete nextDays[dateKey]
  } else {
    nextDays[dateKey] = {
      status: nextStatus,
      ...(nextLocation ? { location: nextLocation } : {}),
    }
  }
  availabilityDays.value = nextDays
}

const hydrateAvailabilityDays = (items = []) => {
  const days = {}
  ;(items || []).forEach(item => {
    if (!item?.date) return
    const date = parseDateKey(String(item.date).split('T')[0])
    if (!date || !isAvailabilityDateAllowed(date)) return
    const key = toDateKey(date)
    const status = normalizeAvailabilityStatus(item.status || item.type)
    const location = String(item.location || '').trim()
    if (status === 'busy' || location) {
      days[key] = {
        status,
        ...(location ? { location } : {}),
      }
    }
  })
  return days
}

const buildAvailabilityExceptions = () => Object.entries(availabilityDays.value)
  .map(([date, item]) => ({
    date,
    status: normalizeAvailabilityStatus(item.status),
    location: String(item.location || '').trim(),
  }))
  .filter(item => {
    const date = parseDateKey(item.date)
    return date && isAvailabilityDateAllowed(date) && (item.status === 'busy' || item.location)
  })
  .sort((a, b) => compareDateKeys(a.date, b.date))

const availabilityMonthLabel = computed(() => {
  const month = availabilityCurrentMonth.value
  return `${month.getFullYear()}年${month.getMonth() + 1}月`
})

const canGoPreviousAvailabilityMonth = computed(() => (
  availabilityCurrentMonth.value > availabilityCurrentMonthStart.value
))

const canGoNextAvailabilityMonth = computed(() => (
  availabilityCurrentMonth.value < availabilityMaxMonthStart.value
))

const shiftAvailabilityMonth = (months) => {
  const next = addMonths(availabilityCurrentMonth.value, months)
  if (next < availabilityCurrentMonthStart.value || next > availabilityMaxMonthStart.value) return
  availabilityCurrentMonth.value = next
  resetAvailabilityRange()
}

const dateRangeKeys = (startKey, endKey) => {
  const startDate = parseDateKey(compareDateKeys(startKey, endKey) <= 0 ? startKey : endKey)
  const endDate = parseDateKey(compareDateKeys(startKey, endKey) <= 0 ? endKey : startKey)
  if (!startDate || !endDate) return []

  const keys = []
  const cursor = new Date(startDate)
  while (cursor <= endDate) {
    if (isAvailabilityDateAllowed(cursor)) keys.push(toDateKey(cursor))
    cursor.setDate(cursor.getDate() + 1)
  }
  return keys
}

const selectedAvailabilityKeys = computed(() => {
  if (availabilityMultiSelect.value) {
    if (!availabilityRangeStart.value) return []
    if (!availabilityRangeEnd.value) return [availabilityRangeStart.value]
    return dateRangeKeys(availabilityRangeStart.value, availabilityRangeEnd.value)
  }
  return selectedAvailabilityDate.value ? [selectedAvailabilityDate.value] : []
})

const isDateKeyInSelectedRange = (dateKey) => {
  if (!availabilityRangeStart.value || !availabilityRangeEnd.value) return false
  const start = compareDateKeys(availabilityRangeStart.value, availabilityRangeEnd.value) <= 0
    ? availabilityRangeStart.value
    : availabilityRangeEnd.value
  const end = start === availabilityRangeStart.value ? availabilityRangeEnd.value : availabilityRangeStart.value
  return compareDateKeys(dateKey, start) >= 0 && compareDateKeys(dateKey, end) <= 0
}

const availabilityCalendarCells = computed(() => {
  const monthStart = availabilityCurrentMonth.value
  const firstDayOffset = (monthStart.getDay() + 6) % 7
  const daysInMonth = new Date(monthStart.getFullYear(), monthStart.getMonth() + 1, 0).getDate()
  const selectedKeys = new Set(selectedAvailabilityKeys.value)
  const cells = Array.from({ length: firstDayOffset }, (_, index) => ({
    key: `blank-${index}`,
    isBlank: true,
  }))

  for (let day = 1; day <= daysInMonth; day += 1) {
    const date = new Date(monthStart.getFullYear(), monthStart.getMonth(), day)
    const key = toDateKey(date)
    const entry = getAvailabilityDay(key)
    cells.push({
      key,
      day,
      date,
      status: normalizeAvailabilityStatus(entry.status),
      location: entry.location || '',
      isBlank: false,
      disabled: !isAvailabilityDateAllowed(date),
      isToday: isSameDateKey(date, toDateKey(startOfToday())),
      isSelected: selectedKeys.has(key),
      isRangeStart: availabilityRangeStart.value === key,
      isRangeEnd: availabilityRangeEnd.value === key,
      isInRange: isDateKeyInSelectedRange(key),
    })
  }

  return cells
})

const monthDateKeys = (monthStart, filterFn = () => true) => {
  const daysInMonth = new Date(monthStart.getFullYear(), monthStart.getMonth() + 1, 0).getDate()
  const keys = []
  for (let day = 1; day <= daysInMonth; day += 1) {
    const date = new Date(monthStart.getFullYear(), monthStart.getMonth(), day)
    if (isAvailabilityDateAllowed(date) && filterFn(date)) keys.push(toDateKey(date))
  }
  return keys
}

const resetAvailabilityRange = () => {
  availabilityRangeStart.value = ''
  availabilityRangeEnd.value = ''
  availabilityRangeForm.applyLocation = false
  availabilityRangeForm.location = ''
}

const availabilitySelectionMode = computed({
  get: () => availabilityMultiSelect.value ? 'multi' : 'single',
  set: (value) => {
    availabilityMultiSelect.value = value === 'multi'
    resetAvailabilityRange()
  },
})

const syncAvailabilityDayForm = (dateKey) => {
  const current = getAvailabilityDay(dateKey)
  availabilityDayForm.status = normalizeAvailabilityStatus(current.status)
  availabilityDayForm.location = current.location || ''
}

const selectAvailabilityDate = (cell) => {
  if (!cell || cell.disabled) return
  selectedAvailabilityDate.value = cell.key
  syncAvailabilityDayForm(cell.key)

  if (availabilityMultiSelect.value) {
    if (!availabilityRangeStart.value || availabilityRangeEnd.value) {
      availabilityRangeStart.value = cell.key
      availabilityRangeEnd.value = ''
      return
    }
    availabilityRangeEnd.value = cell.key
    return
  }
}

const formatAvailabilityDateLabel = (dateKey) => {
  const date = parseDateKey(dateKey)
  if (!date) return ''
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`
}

const formatAvailabilityWeekdayLabel = (dateKey) => {
  const date = parseDateKey(dateKey)
  if (!date) return ''
  return availabilityWeekdays[(date.getDay() + 6) % 7]
}

const selectedAvailabilityRangeLabel = computed(() => {
  const keys = selectedAvailabilityKeys.value
  if (!keys.length) return ''
  if (keys.length === 1) return formatAvailabilityDateLabel(keys[0])
  return `${formatAvailabilityDateLabel(keys[0])} - ${formatAvailabilityDateLabel(keys[keys.length - 1])}`
})

const selectedAvailabilityLabel = computed(() => formatAvailabilityDateLabel(selectedAvailabilityDate.value))
const selectedAvailabilityWeekday = computed(() => formatAvailabilityWeekdayLabel(selectedAvailabilityDate.value))
const availabilityModeHint = computed(() => availabilityMultiSelect.value ? '批量选择日期' : '单日编辑')

const availabilityMonthStats = computed(() => {
  const days = availabilityCalendarCells.value.filter(cell => !cell.isBlank && !cell.disabled)
  return {
    total: days.length,
    free: days.filter(cell => cell.status === 'free').length,
    busy: days.filter(cell => cell.status === 'busy').length,
    selected: selectedAvailabilityKeys.value.length,
  }
})

const applyAvailabilityDayForm = () => {
  if (!selectedAvailabilityDate.value) return
  setAvailabilityDay(
    selectedAvailabilityDate.value,
    availabilityDayForm.status,
    availabilityDayForm.location,
  )
  syncAvailabilityDayForm(selectedAvailabilityDate.value)
  ElMessage.success('已更新 1 天档期')
}

const clearSelectedAvailability = () => {
  if (!selectedAvailabilityDate.value) return
  setAvailabilityDay(selectedAvailabilityDate.value, 'free', '')
  syncAvailabilityDayForm(selectedAvailabilityDate.value)
  ElMessage.success('已恢复为默认可约')
}

const applyBulkAvailability = (status) => {
  const keys = selectedAvailabilityKeys.value
  if (!keys.length) return
  const nextStatus = normalizeAvailabilityStatus(status)

  keys.forEach(key => {
    const location = availabilityRangeForm.applyLocation
      ? availabilityRangeForm.location
      : getAvailabilityDay(key).location
    setAvailabilityDay(key, nextStatus, location)
  })
  resetAvailabilityRange()
  if (selectedAvailabilityDate.value) syncAvailabilityDayForm(selectedAvailabilityDate.value)
  ElMessage.success(`已更新 ${keys.length} 天档期`)
}

const applyAvailabilityQuickAction = (type) => {
  let keys = []
  if (type === 'next-month-busy') {
    const nextMonth = addMonths(availabilityCurrentMonth.value, 1)
    if (nextMonth <= availabilityMaxMonthStart.value) {
      keys = monthDateKeys(nextMonth)
      availabilityCurrentMonth.value = nextMonth
    }
  } else if (type === 'weekdays-busy') {
    keys = monthDateKeys(availabilityCurrentMonth.value, date => date.getDay() >= 1 && date.getDay() <= 5)
  } else if (type === 'weekends-busy') {
    keys = monthDateKeys(availabilityCurrentMonth.value, date => date.getDay() === 0 || date.getDay() === 6)
  } else if (type === 'clear-month-busy') {
    keys = monthDateKeys(availabilityCurrentMonth.value)
  }

  keys.forEach(key => {
    const current = getAvailabilityDay(key)
    if (type === 'clear-month-busy') {
      setAvailabilityDay(key, 'free', current.location)
    } else {
      setAvailabilityDay(key, 'busy', current.location)
    }
  })
  resetAvailabilityRange()
  if (selectedAvailabilityDate.value) syncAvailabilityDayForm(selectedAvailabilityDate.value)
  if (keys.length) ElMessage.success(`已更新 ${keys.length} 天档期`)
}

const saveAvailability = async () => {
  const exceptions = buildAvailabilityExceptions()

  savingAvailability.value = true
  try {
    await api.post('/photographers/profile', {
      available_hours: [],
      availability_exceptions: exceptions,
      max_booking_date: maxBookingDate.value || null
    })
    availabilityDays.value = hydrateAvailabilityDays(exceptions)
    if (selectedAvailabilityDate.value) syncAvailabilityDayForm(selectedAvailabilityDate.value)
    ElMessage.success('档期已保存')
  } catch {
    ElMessage.error('档期保存失败')
  } finally {
    savingAvailability.value = false
  }
}

// ---- 方案管理 ----
const showPackageDialog = ref(false)
const editingPackageIndex = ref(-1)
const packageForm = ref({ name: '', price: 699, duration: 120, description: '', city: '' })
const packageStyleTags = ref([])
const sampleFiles = ref([])
const uploadingSamples = ref(false)

const resetPackageForm = () => {
  packageForm.value = { name: '', price: 699, duration: 120, description: '', city: '' }
  packageStyleTags.value = []
  editingPackageIndex.value = -1
  sampleFiles.value = []
}

const openPackageDialog = (index) => {
  sampleFiles.value = []
  if (index >= 0) {
    const pkg = packagesList.value[index]
    packageForm.value = { name: pkg.name, price: pkg.price, duration: pkg.duration, description: pkg.description || '', city: pkg.city || '' }
    packageStyleTags.value = pkg.styles || pkg.includes || []
    editingPackageIndex.value = index
    if (pkg.samples && pkg.samples.length) {
      sampleFiles.value = pkg.samples.map((url, i) => ({
        name: `sample_${i}`,
        url: getFullUrl(pkg.sample_thumbnails?.[i] || url),
        uid: url,
        thumbUrl: pkg.sample_thumbnails?.[i] || '',
      }))
    }
  } else {
    resetPackageForm()
  }
  showPackageDialog.value = true
}

const savePackage = async () => {
  const newFiles = sampleFiles.value.filter(f => f.raw)
  const existingSamples = sampleFiles.value
    .filter(f => !f.raw)
    .map(f => ({ url: f.uid, thumbnailUrl: f.thumbUrl || '' }))
  let sampleUrls = existingSamples.map(f => f.url)
  let sampleThumbnailUrls = existingSamples.map(f => f.thumbnailUrl)

  if (newFiles.length) {
    uploadingSamples.value = true
    try {
      const fd = new FormData()
      newFiles.forEach(f => fd.append('files', f.raw))
      const res = await api.post('/photographers/package-samples/upload', fd, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      const uploadedUrls = res.data.urls || []
      const uploadedThumbnailUrls = (res.data.thumbnail_urls && res.data.thumbnail_urls.length)
        ? res.data.thumbnail_urls
        : uploadedUrls
      sampleUrls = [...sampleUrls, ...uploadedUrls]
      sampleThumbnailUrls = [...sampleThumbnailUrls, ...uploadedThumbnailUrls]
    } catch {
      ElMessage.error('示例图上传失败')
      return
    } finally {
      uploadingSamples.value = false
    }
  }

  const pkg = {
    name: packageForm.value.name,
    price: packageForm.value.price,
    duration: packageForm.value.duration,
    description: packageForm.value.description,
    styles: packageStyleTags.value,
    city: packageForm.value.city || '',
    samples: sampleUrls,
    sample_thumbnails: sampleThumbnailUrls
  }
  if (editingPackageIndex.value >= 0) {
    packagesList.value[editingPackageIndex.value] = pkg
  } else {
    packagesList.value.push(pkg)
  }
  showPackageDialog.value = false
  uploadPackages()
}

const removePackage = async (index) => {
  try { await ElMessageBox.confirm('确定删除该方案？', '提示', { type: 'warning' }) } catch { return }
  packagesList.value.splice(index, 1)
  uploadPackages()
}

const uploadPackages = async () => {
  try {
    await api.post('/photographers/profile', { packages: packagesList.value })
    ElMessage.success('方案已保存')
  } catch {
    ElMessage.error('方案保存失败')
  }
}

let favLoaded = false
let pkgFavLoaded = false
let likedWorksLoaded = false

const fetchFavs = async () => {
  if (favLoaded) return
  loadingFavs.value = true
  try {
    const { data } = await getUserFavorites(0, 200)
    favItems.value = data.items || []
    favLoaded = true
  } finally {
    loadingFavs.value = false
  }
}

const fetchPkgFavs = async () => {
  if (pkgFavLoaded) return
  loadingPkgFavs.value = true
  try {
    const { data } = await getUserPackageFavorites(0, 200)
    pkgFavItems.value = data.items || []
    pkgFavLoaded = true
  } finally {
    loadingPkgFavs.value = false
  }
}

const fetchLikedWorks = async () => {
  if (likedWorksLoaded) return
  loadingLikedWorks.value = true
  try {
    const { data } = await getUserLikedWorks(0, 200)
    likedWorkItems.value = data.items || []
    likedWorksLoaded = true
  } finally {
    loadingLikedWorks.value = false
  }
}

const loadProfileTabData = (tab = activeTab.value) => {
  const normalizedTab = normalizeProfileTab(tab, profileMode.value)
  if (normalizedTab === 'works') {
    loadWorkDrafts()
  } else if (normalizedTab === 'favorites') {
    fetchFavs()
    fetchPkgFavs()
  } else if (normalizedTab === 'likes') {
    fetchLikedWorks()
  } else if (normalizedTab === 'orders' && canViewCurrentModeOrders.value) {
    fetchOrders()
  } else if (normalizedTab === 'applications' && canUsePhotographerFeatures.value) {
    fetchApplications()
  } else if (normalizedTab === 'my-projects') {
    fetchMyProjects()
  }
}

const formatFavTime = (dt) => {
  if (!dt) return ''
  const d = new Date(dt)
  const now = new Date()
  const diff = now - d
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  if (diff < 2592000000) return `${Math.floor(diff / 86400000)}天前`
  return d.toLocaleDateString('zh-CN')
}

const fetchFollowCounts = async () => {
  if (!userId.value) return
  try {
    const res = await getFollowCounts(userId.value)
    followCounts.following_count = res.data.following_count ?? 0
    followCounts.follower_count = res.data.follower_count ?? 0
  } catch {
    // silently ignore
  }
}

const showFollowList = (type) => {
  router.push({
    path: `/follow-list/${userId.value}`,
    query: { type: type === 'following' ? 'following' : 'followers' },
  })
}

onMounted(() => {
  fetchUserData()
})

onUnmounted(() => {
  revokeDraftPreviewUrls()
})

watch(activeTab, (tab) => {
  loadProfileTabData(tab)
  syncProfileRouteState()
})

watch(() => [route.query.tab, route.query.fav, profileMode.value], ([tab, favorite, mode]) => {
  const nextTab = normalizeProfileTab(tab, mode)
  const nextFavTab = normalizeFavoriteTab(favorite)

  if (activeTab.value !== nextTab) {
    activeTab.value = nextTab
  }
  if (favTab.value !== nextFavTab) {
    favTab.value = nextFavTab
  }

  loadProfileTabData(nextTab)
  syncProfileRouteState()
})

watch(favTab, (tab) => {
  if (tab === 'works') fetchFavs()
  if (tab === 'packages') fetchPkgFavs()
  if (activeTab.value === 'favorites') {
    syncProfileRouteState()
  }
})
</script>

<style scoped>
.profile-page {
  max-width: var(--content-max-width);
  margin: 30px auto;
  padding: 0 20px;
}

/* 头部 - 可更换背景图卡片 */
.profile-header-card {
  position: relative;
  padding: 24px 28px 18px;
  background-color: #1F3F1A;
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  border: var(--border-default);
  border-radius: var(--radius-md);
  margin-bottom: 30px;
  isolation: isolate;
  overflow: hidden;
}
.profile-header-card::before {
  content: '';
  position: absolute;
  inset: 0;
  background: inherit;
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  z-index: 0;
}
/* 背景图存在时显示深色遮罩，保证白色文字可读 */
.profile-header-card::after {
  content: '';
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 1;
  pointer-events: none;
}
.profile-header-card > * {
  position: relative;
  z-index: 2;
}

/* 更换背景按钮 */
.bg-change-btn {
  position: absolute;
  bottom: 12px;
  right: 12px;
  z-index: 10;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 18px;
  cursor: pointer;
  border: 1px solid rgba(255, 255, 255, 0.3);
}
.bg-change-btn:hover {
  background: rgba(255, 255, 255, 0.35);
}

/* 切换身份按钮 */
.role-switch-btn {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 10;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 18px;
  cursor: pointer;
  border: 1px solid rgba(255, 255, 255, 0.3);
}
.role-switch-btn:hover {
  background: rgba(255, 255, 255, 0.35);
}

.profile-header {
  display: flex;
  gap: 28px;
  align-items: center;
}
.profile-avatar-wrap {
  position: relative;
  display: inline-flex;
  align-items: center;
}
.profile-avatar {
  flex-shrink: 0;
  cursor: pointer;
}
.verified-badge {
  position: absolute;
  bottom: 12px;
  right: 0px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--color-brand);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 14px;
  border: 2px solid #fff;
  z-index: 10;
}
.profile-info {
  flex: 1;
}
.profile-name-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.profile-name-group {
  display: flex;
  align-items: center;
  gap: 0;
}
.profile-name {
  font-size: var(--text-2xl);
  font-weight: 700;
  color: #fff;
}

.edit-icon {
  font-size: 18px;
  color: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  margin-left: 6px;
}
.edit-icon:hover {
  color: #fff;
}
.profile-bio {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.85);
  line-height: 1.6;
  margin: 0 0 12px;
}
.profile-bio p {
  margin: 0 0 8px;
  white-space: pre-wrap;
}
.profile-bio p:last-child {
  margin-bottom: 0;
}

/* 高度自适应：卡片过渡 */
.profile-header-card {
  transition: min-height 0.45s ease, padding 0.3s ease;
}

/* 三种高度模式 - 背景图位置适配 */
.bio-height-min::before {
  background-position: center 25%;
}
.bio-height-medium::before {
  background-position: center 40%;
}
.bio-height-max::before {
  background-position: center 55%;
}

/* 个人信息卡片内的 FollowCounts 文字适配白色背景 */
.profile-header-card :deep(.follow-counts),
.profile-header-card :deep(.follow-counts span),
.profile-header-card :deep(.follow-counts strong) {
  color: #fff !important;
}

/* Tabs — 简洁下划线样式 */
.profile-tabs {
  margin-top: -10px;
}
.profile-tabs :deep(.el-tabs__header) {
  margin: 0 0 16px;
  padding: 6px;
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-paper-light);
  overflow: hidden;
}
.profile-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}
.profile-tabs :deep(.el-tabs__nav-wrap) {
  overflow-x: auto;
}
.profile-tabs :deep(.el-tabs__nav) {
  border: none;
}
.profile-tabs :deep(.el-tabs__item) {
  height: var(--tap-target-min);
  line-height: var(--tap-target-min);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--color-ink-secondary);
  padding: 0 14px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
}
.profile-tabs :deep(.el-tabs__item:hover) {
  color: var(--color-brand);
}
.profile-tabs :deep(.el-tabs__item.is-active) {
  color: var(--color-brand);
  font-weight: 600;
  border-color: var(--color-border);
  background: var(--color-brand-light);
}
.profile-tabs :deep(.el-tabs__active-bar) {
  display: none;
}

/* 管理型工作台 */
.workspace-panel {
  min-width: 0;
  padding: 18px;
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-paper-light);
}

.workspace-panel-flat {
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
}
.workspace-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}
.workspace-kicker {
  margin: 0 0 4px;
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
  font-weight: 600;
}

/* 筛选按钮栏 - 左侧对齐一级 Tab */
.workspace-filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
  padding: var(--space-3);
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-paper-light);
}

.filter-btn {
  appearance: none;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-paper);
  color: var(--color-ink-secondary);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s, color 0.2s;
}

.filter-btn:hover {
  border-color: var(--color-brand);
  color: var(--color-brand);
}

.filter-btn-active {
  background: var(--color-brand);
  border-color: var(--color-brand);
  color: #fff;
}

.filter-btn-active:hover {
  background: var(--color-brand-hover);
  border-color: var(--color-brand-hover);
  color: #fff;
}

.filter-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 5px;
  border-radius: 999px;
  background: var(--color-paper);
  color: var(--color-ink-secondary);
  font-size: var(--text-xs);
  font-weight: 600;
  line-height: 1;
  transition: background 0.2s, color 0.2s;
}

.filter-btn-active .filter-count {
  background: rgba(255, 255, 255, 0.25);
  color: #fff;
}
.workspace-head h3 {
  margin: 0;
  color: var(--color-ink);
  font-size: var(--text-xl);
  line-height: 1.25;
}
.workspace-metrics {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}
.workspace-metric {
  min-width: 78px;
  padding: 8px 12px;
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-paper);
  text-align: center;
}
.workspace-metric span {
  display: block;
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
  line-height: 1;
}
.workspace-metric strong {
  display: block;
  margin-top: 5px;
  color: var(--color-ink);
  font-size: var(--text-xl);
  line-height: 1;
}
.workspace-table {
  --el-table-border-color: var(--color-border-light);
  --el-table-header-bg-color: var(--color-paper);
  border: var(--border-default);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.profile-order-card-list,
.profile-project-card-list {
  display: grid;
  gap: var(--space-3);
}

.profile-project-card-list {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
}

.profile-order-card,
.profile-project-card {
  padding: var(--space-5);
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-paper-light);
}

.profile-project-cover {
  display: block;
  width: 190px;
  height: 190px;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  background: var(--color-paper);
}

.profile-project-content {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-5);
}

.profile-project-info {
  min-width: 0;
}

.profile-order-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--space-6);
}

.profile-project-card {
  display: grid;
  gap: var(--space-5);
}

.profile-card-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
}

.profile-card-heading > span,
.profile-card-heading > div > span {
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
}

.profile-order-card h3,
.profile-project-card h3 {
  margin: var(--space-2) 0;
  color: var(--color-ink);
  font-size: var(--text-lg);
  line-height: var(--leading-normal);
}

.profile-order-card p {
  display: -webkit-box;
  margin: 0 0 var(--space-4);
  overflow: hidden;
  color: var(--color-ink-secondary);
  font-size: var(--text-sm);
  line-height: var(--leading-normal);
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.profile-order-facts,
.profile-project-facts {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-4);
}

.profile-project-facts {
  grid-template-columns: 1fr;
  gap: 0;
  border-top: 1px solid var(--color-divider);
  margin-top: var(--space-4);
}

.profile-order-facts div,
.profile-project-facts div {
  display: grid;
  gap: var(--space-1);
}

.profile-project-facts div {
  grid-template-columns: 82px minmax(0, 1fr);
  align-items: baseline;
  padding: var(--space-2) 0;
  border-right: 0;
  border-bottom: 1px solid var(--color-divider);
}

.profile-project-facts div:first-child {
  padding-left: 0;
}

.profile-project-facts div:last-child {
  border-bottom: 0;
}

.profile-order-facts span,
.profile-project-facts span {
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
}

.profile-order-facts strong,
.profile-project-facts strong {
  color: var(--color-ink-secondary);
  font-size: var(--text-sm);
  font-weight: 500;
}

.profile-card-actions {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  flex-direction: column;
  gap: var(--space-2);
}

.profile-card-actions .el-button {
  min-height: var(--tap-target-min);
  margin: 0;
}

.profile-card-actions.is-project-actions {
  align-items: center;
  justify-content: flex-start;
  flex-direction: row;
  flex-wrap: wrap;
}
.workspace-table :deep(.el-table__header th) {
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
  font-weight: 600;
  background: var(--color-paper);
}
.workspace-table :deep(.el-table__row) {
  height: 76px;
}
.workspace-table :deep(.el-table__cell) {
  padding: 12px 0;
}
.workspace-table :deep(.el-table__row:hover > td.el-table__cell) {
  background: var(--color-paper);
}
.entity-cell,
.time-cell {
  min-width: 0;
  display: grid;
  gap: 4px;
}
.entity-id {
  width: fit-content;
  padding: 2px 7px;
  border-radius: 999px;
  background: var(--color-paper);
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
  line-height: 1.2;
}
.entity-cell strong,
.time-cell strong {
  color: var(--color-ink);
  font-size: 14px;
  line-height: 1.35;
}
.entity-cell small,
.time-cell span {
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
  line-height: 1.4;
}
.money-text {
  color: var(--color-ink);
  font-size: 16px;
}
.count-text {
  color: var(--color-brand);
  font-size: 18px;
}
.muted-unit {
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
}
.row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.row-actions .el-button {
  margin-left: 0;
}

/* 作品网格 */
.works-grid {
  column-count: 4;
  column-gap: 16px;
}
.work-card {
  break-inside: avoid;
  margin-bottom: 16px;
  cursor: pointer;
  border-radius: var(--radius-md);
  overflow: hidden;
  transition: border-color 0.2s;
}
.work-card :deep(.el-card) {
  border: var(--border-default);
  background: var(--color-paper-light);
  border-radius: var(--radius-md);
  overflow: hidden;
}
.work-card:hover :deep(.el-card) {
  border-color: var(--color-brand);
}
.work-card :deep(.el-card__body) {
  padding: 0;
}
.draft-work-card :deep(.el-card) {
  border: 1px dashed var(--color-warning);
  background: var(--color-paper-light);
}
.work-img-wrap {
  overflow: hidden;
  background: var(--color-paper);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}
.draft-img-wrap {
  aspect-ratio: 1 / 1;
  background: var(--color-paper);
}
.work-img {
  width: 100%;
  height: 100%;
  display: block;
}
.draft-preview-img {
  object-fit: cover;
}
.draft-empty-preview {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-warning);
  font-size: var(--text-sm);
  background: var(--color-paper);
}
.draft-badge {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 2;
  padding: 3px 8px;
  border-radius: 999px;
  background: var(--color-warning);
  color: #fff;
  font-size: var(--text-xs);
  line-height: 1.3;
  font-weight: 600;
}
.draft-meta {
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
  line-height: 1.4;
}
.draft-action-row {
  min-height: 30px;
  margin-top: 4px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.draft-delete-btn {
  appearance: none;
  flex: 0 0 auto;
  width: 30px;
  height: 30px;
  border: 0;
  border-radius: 50%;
  background: #fef0f0;
  color: var(--color-danger);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.draft-delete-btn:hover {
  background: var(--color-danger);
  color: #fff;
}
.work-video-preview {
  object-fit: cover;
  background: #000;
}
.work-video-overlay {
  position: absolute;
  top: 8px;
  left: 8px;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  z-index: 2;
}
.work-video-overlay .el-icon {
  margin-left: 1px;
}
.work-card-body {
  padding: 10px 14px 6px;
  background: var(--color-paper-light);
}
.work-card-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 2px;
  color: var(--color-ink);
}
.photographer-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 0;
  justify-content: space-between;
}
.photographer-info {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.photographer-avatar {
  flex-shrink: 0;
}
.photographer-name {
  font-size: var(--text-sm);
  color: var(--color-ink-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.row-like-btn {
  flex-shrink: 0;
}

/* 方案管理卡片 */
.managed-package-grid {
  column-count: 4;
  column-gap: 16px;
}
.managed-package-add,
.managed-package-card {
  break-inside: avoid;
  width: 100%;
  min-width: 0;
  margin-bottom: 16px;
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-paper-light);
  overflow: hidden;
}
.managed-package-add {
  appearance: none;
  aspect-ratio: 1 / 1;
  padding: 24px;
  border-style: dashed;
  color: var(--color-brand);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  text-align: center;
  transition: border-color 0.2s, background 0.2s;
}
.managed-package-add:hover {
  border-color: var(--color-brand);
  background: var(--color-brand-light);
}
.managed-package-add .el-icon {
  font-size: 28px;
}
.managed-package-add strong {
  color: var(--color-ink);
  font-size: 16px;
}
.managed-package-add span {
  max-width: 180px;
  color: var(--color-ink-tertiary);
  font-size: var(--text-sm);
  line-height: var(--leading-normal);
}
.managed-package-card {
  display: block;
  transition: border-color 0.2s;
}
.managed-package-card:hover {
  border-color: var(--color-brand);
}
.managed-package-cover {
  width: 100%;
  background: var(--color-paper);
}
.managed-package-img {
  width: 100%;
  display: block;
}
.managed-package-img :deep(img) {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.managed-package-placeholder {
  width: 100%;
  aspect-ratio: 4 / 3;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-ink-tertiary);
  font-size: var(--text-sm);
}
.managed-package-body {
  display: grid;
  gap: 10px;
  padding: 14px;
}
.managed-package-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}
.managed-package-title-row h4 {
  min-width: 0;
  margin: 0;
  color: var(--color-ink);
  font-size: 16px;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.managed-package-title-row strong {
  flex-shrink: 0;
  color: var(--color-ink);
  font-size: 18px;
  line-height: 1.2;
}
.managed-package-body p {
  min-height: 40px;
  margin: 0;
  color: var(--color-ink-secondary);
  font-size: var(--text-sm);
  line-height: 1.55;
  display: -webkit-box;
  overflow: hidden;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.managed-package-meta,
.managed-package-tags,
.managed-package-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.managed-package-meta {
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
}
.managed-package-actions {
  padding-top: 4px;
}
.managed-package-actions .el-button {
  margin-left: 0;
}

/* 档期设置 */
.availability-panel {
  width: 100%;
  display: grid;
  gap: 16px;
}
.availability-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
  padding: 14px 16px;
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-paper-light);
}
.availability-month-control,
.availability-summary,
.availability-mode-actions,
.availability-calendar-meta,
.availability-legend,
.availability-bulk-actions {
  display: flex;
  align-items: center;
}
.availability-month-control {
  gap: 12px;
  min-width: 0;
}
.availability-month-heading {
  display: grid;
  gap: 2px;
  min-width: 116px;
  text-align: center;
}
.availability-month-heading span,
.availability-detail-header span,
.availability-section-title,
.availability-field-label,
.availability-meta-text {
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
}
.availability-month-heading strong {
  color: var(--color-ink);
  font-size: var(--text-xl);
  font-weight: 700;
  line-height: 1.2;
}
.availability-summary {
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
}
.availability-summary-item {
  min-width: 68px;
  padding: 8px 10px;
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-paper);
  text-align: center;
}
.availability-summary-item span {
  display: block;
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
  line-height: 1;
}
.availability-summary-item strong {
  display: block;
  margin-top: 5px;
  color: var(--color-brand);
  font-size: 18px;
  line-height: 1;
}
.availability-summary-item.is-busy strong {
  color: var(--color-danger);
}
.availability-summary-item.is-selected strong {
  color: var(--color-brand-hover);
}
.availability-mode-actions {
  justify-content: flex-end;
  gap: 10px;
}
.availability-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 16px;
  align-items: start;
}
.availability-calendar-card,
.availability-detail-panel {
  min-width: 0;
  padding: 16px;
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-paper-light);
}
.availability-calendar-meta {
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.availability-legend {
  flex-wrap: wrap;
  gap: 12px;
  color: var(--color-ink-secondary);
  font-size: var(--text-sm);
}
.availability-dot,
.availability-status-badge::before {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.availability-dot {
  margin-right: 6px;
}
.availability-dot.is-free,
.availability-status-badge.is-free::before {
  background: var(--color-brand);
}
.availability-dot.is-busy,
.availability-status-badge.is-busy::before {
  background: var(--color-danger);
}
.availability-calendar {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 8px;
}
.availability-weekday {
  min-width: 0;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
  font-weight: 600;
}
.availability-date-cell {
  position: relative;
  width: 100%;
  min-width: 0;
  min-height: 96px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px;
  overflow: hidden;
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-paper-light);
  color: var(--color-ink);
  text-align: left;
  cursor: pointer;
  font: inherit;
  transition: border-color 0.2s, background 0.2s;
}
.availability-date-cell:hover {
  border-color: var(--color-brand);
}
.availability-date-cell.is-blank {
  min-height: 96px;
  border-color: transparent;
  background: transparent;
  cursor: default;
  pointer-events: none;
}
.availability-date-cell.is-disabled {
  cursor: not-allowed;
  color: var(--color-ink-tertiary);
  background: var(--color-paper);
}
.availability-date-cell.is-busy {
  background: #fef7f7;
  border-color: #f3d2d2;
}
.availability-date-cell.is-today {
  border-color: var(--color-brand);
}
.availability-date-cell.is-selected,
.availability-date-cell.is-in-range {
  background: var(--color-brand-light);
  border-color: var(--color-brand);
}
.availability-date-cell.is-range-start,
.availability-date-cell.is-range-end {
  box-shadow: inset 0 0 0 2px var(--color-brand);
}
.availability-date-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}
.availability-date-number {
  font-weight: 700;
  font-size: 16px;
  line-height: 1;
}
.availability-today-tag {
  padding: 2px 5px;
  border-radius: 999px;
  background: var(--color-brand-light);
  color: var(--color-brand);
  font-size: 11px;
  line-height: 1.2;
}
.availability-status-badge {
  width: fit-content;
  max-width: 100%;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 7px;
  border-radius: 999px;
  background: var(--color-brand-light);
  color: var(--color-brand);
  font-size: var(--text-xs);
  line-height: 1.2;
  white-space: nowrap;
}
.availability-status-badge.is-busy {
  background: #fef0f0;
  color: var(--color-danger);
}
.availability-time-summary {
  color: var(--color-ink-secondary);
  font-size: var(--text-xs);
  line-height: 1.3;
}
.availability-location {
  max-width: 100%;
  margin-top: auto;
  color: var(--color-ink-secondary);
  font-size: var(--text-xs);
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.availability-detail-panel {
  display: grid;
  gap: 16px;
}
.availability-detail-header {
  display: grid;
  gap: 5px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--color-divider);
}
.availability-detail-header h3 {
  margin: 0;
  color: var(--color-ink);
  font-size: var(--text-xl);
  line-height: 1.25;
}
.availability-detail-header p {
  margin: 0;
  color: var(--color-ink-secondary);
  font-size: var(--text-sm);
}
.availability-detail-body,
.availability-field,
.availability-presets,
.availability-preset-list {
  display: grid;
  gap: 12px;
}
.availability-current-status {
  display: grid;
  gap: 4px;
  padding: 12px;
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-brand-light);
}
.availability-current-status.is-busy {
  background: #fef0f0;
  border-color: #f3d2d2;
}
.availability-current-status span {
  color: var(--color-brand);
  font-size: var(--text-sm);
}
.availability-current-status.is-busy span {
  color: var(--color-danger);
}
.availability-current-status strong {
  color: var(--color-ink);
  font-size: 16px;
}
.availability-field-label,
.availability-section-title {
  font-weight: 600;
  color: var(--color-ink);
}
.availability-status-toggle {
  width: 100%;
}
.availability-status-toggle :deep(.el-radio-button) {
  width: 50%;
}
.availability-status-toggle :deep(.el-radio-button__inner) {
  width: 100%;
}
.availability-detail-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.availability-detail-actions .el-button,
.availability-preset-list .el-button,
.availability-bulk-actions .el-button {
  margin-left: 0;
}
.availability-preset-list .el-button {
  justify-content: flex-start;
}
.availability-empty-detail {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 14px;
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-paper);
  color: var(--color-ink-secondary);
}
.availability-empty-detail strong {
  color: var(--color-brand);
  font-size: var(--text-2xl);
  line-height: 1;
}
.availability-bulk-bar {
  position: sticky;
  bottom: 12px;
  z-index: 2;
  display: grid;
  grid-template-columns: auto minmax(220px, 1fr) auto;
  align-items: center;
  gap: 14px;
  padding: 12px 14px;
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-brand-light);
}
.availability-bulk-summary {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
}
.availability-bulk-summary strong {
  color: var(--color-brand);
  font-size: var(--text-2xl);
  line-height: 1;
}
.availability-bulk-summary span {
  color: var(--color-ink);
  font-size: var(--text-sm);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.availability-bulk-location {
  display: grid;
  grid-template-columns: auto minmax(150px, 1fr);
  align-items: center;
  gap: 8px;
}
.availability-bulk-actions {
  justify-content: flex-end;
  gap: 8px;
}

/* 查看交付作品 */
.view-desc {
  margin-bottom: 16px;
  padding: 10px 14px;
  background: var(--color-paper);
  border-radius: var(--radius-md);
  font-size: 14px;
  color: var(--color-ink-secondary);
}
.view-images {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
.delivery-img {
  width: 180px;
  height: 180px;
  border-radius: var(--radius-md);
  cursor: pointer;
}

/* 评价 */
.review-score {
  margin-bottom: 16px;
  display: flex;
  justify-content: center;
}
.review-text-content {
  padding: 14px;
  background: var(--color-paper);
  border-radius: var(--radius-md);
  font-size: 14px;
  color: var(--color-ink);
  line-height: var(--leading-relaxed);
}

.next-step-text {
  color: var(--color-ink-secondary);
  font-size: var(--text-sm);
}

.pending-reschedule {
  margin-top: 4px;
  color: var(--color-warning);
  font-size: var(--text-xs);
  line-height: 1.4;
}

/* el-tag overrides */
:deep(.el-tag--success) {
  background: var(--color-brand);
  border-color: var(--color-brand);
  color: #fff;
}
:deep(.el-tag--warning) {
  background: #fdf6ec;
  border-color: #f1d9a7;
  color: var(--color-warning);
}
:deep(.el-tag--info) {
  background: var(--color-paper);
  border-color: var(--color-border);
  color: var(--color-ink-secondary);
}
:deep(.el-tag--danger) {
  background: #fef0f0;
  border-color: #f3d4d4;
  color: var(--color-danger);
}
:deep(.el-tag--primary) {
  background: var(--color-brand-light);
  border-color: var(--color-brand-light);
  color: var(--color-brand);
}

/* el-tag small in package tags */
.managed-package-tags :deep(.el-tag--small) {
  background: var(--color-brand-light);
  color: var(--color-brand);
  border-color: var(--color-brand-light);
}

/* 收藏 */
.fav-waterfall { column-count: 4; column-gap: 16px; }
.fav-item {
  break-inside: avoid; margin-bottom: 16px; cursor: pointer;
  border-radius: var(--radius-md);
  transition: border-color 0.2s;
}
.fav-item :deep(.el-card) {
  border: var(--border-default);
  background: var(--color-paper-light);
  border-radius: var(--radius-md);
  overflow: hidden;
}
.fav-item:hover :deep(.el-card) {
  border-color: var(--color-brand);
}
.fav-img-wrap {
  overflow: hidden;
  background: var(--color-paper);
  display: flex;
  align-items: center;
  justify-content: center;
}
.fav-img { width: 100%; height: 100%; display: block; }
.fav-placeholder {
  width: 100%; aspect-ratio: 1/1; background: var(--color-paper);
  display: flex; align-items: center; justify-content: center; color: var(--color-ink-tertiary); font-size: 14px;
}
.fav-body { padding: 12px 14px; }
.fav-title { font-size: 15px; font-weight: 600; margin-bottom: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--color-ink); }
.fav-price { font-size: 14px; font-weight: 600; color: var(--color-ink); margin-bottom: 6px; }
.fav-photog { display: flex; align-items: center; gap: 8px; }
.fav-photog-name { font-size: var(--text-sm); color: var(--color-ink-secondary); flex: 1; }
.fav-time { font-size: var(--text-xs); color: var(--color-ink-tertiary); white-space: nowrap; }

.security-section { display: flex; flex-direction: column; gap: 14px; }
.security-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; min-height: 44px; }
.security-actions { display: flex; flex: 0 0 auto; align-items: center; gap: var(--space-2); }
.security-row strong { color: var(--color-ink); font-size: var(--text-sm); }
.security-value { margin: 4px 0 0; color: var(--color-ink-secondary); font-size: var(--text-sm); word-break: break-word; }
.security-hint { margin: 4px 0 0; color: var(--color-ink-tertiary); font-size: var(--text-xs); line-height: 1.5; }
.inline-hint { display: inline-block; margin-left: 8px; }
.security-danger-row { padding-top: 4px; }

@media (max-width: 992px) {
  .profile-project-card-list {
    grid-template-columns: 1fr;
  }
  .works-grid { column-count: 3; }
  .managed-package-grid { column-count: 3; }
}
@media (max-width: 768px) {
  .profile-project-content {
    grid-template-columns: 1fr;
  }

  .profile-project-cover {
    width: 100%;
    height: auto;
    aspect-ratio: 1;
    order: -1;
  }
  .profile-order-card {
    grid-template-columns: 1fr;
  }

  .profile-order-facts,
  .profile-project-facts {
    grid-template-columns: 1fr;
  }

  .profile-project-facts div,
  .profile-project-facts div:first-child {
    padding: var(--space-3) 0;
    border-right: 0;
    border-bottom: 1px solid var(--color-divider);
  }

  .profile-project-facts div:last-child {
    border-bottom: 0;
  }

  .profile-card-actions {
    align-items: stretch;
  }

  .profile-card-actions .el-button {
    width: 100%;
  }

  .profile-card-actions.is-project-actions {
    align-items: stretch;
  }
  .profile-header { flex-direction: column; text-align: center; }
  .profile-name-row { justify-content: center; }
  .works-grid { column-count: 2; }
  .workspace-panel {
    padding: 14px;
  }
  .workspace-panel-flat {
    padding: 0;
  }
  .workspace-head {
    align-items: stretch;
    flex-direction: column;
  }
  .workspace-metrics {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .workspace-metric {
    min-width: 0;
  }
  .managed-package-grid {
    column-count: 2;
  }
  .availability-layout,
  .availability-bulk-bar {
    grid-template-columns: 1fr;
  }
  .availability-topbar {
    align-items: stretch;
    flex-direction: column;
  }
  .availability-month-control,
  .availability-summary,
  .availability-mode-actions {
    width: 100%;
  }
  .availability-month-control,
  .availability-mode-actions {
    justify-content: space-between;
  }
  .availability-summary {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .availability-calendar {
    gap: 6px;
  }
  .availability-weekday {
    height: 24px;
    font-size: 11px;
  }
  .availability-date-cell {
    min-height: 74px;
    padding: 8px;
    border-radius: var(--radius-sm);
  }
  .availability-date-cell.is-blank {
    min-height: 74px;
  }
  .availability-date-number {
    font-size: 14px;
  }
  .availability-time-summary {
    display: none;
  }
  .availability-detail-actions {
    grid-template-columns: 1fr;
  }
  .availability-bulk-bar {
    position: static;
  }
  .availability-bulk-location {
    grid-template-columns: 1fr;
  }
  .availability-bulk-actions {
    flex-wrap: wrap;
    justify-content: flex-start;
  }
}
@media (max-width: 480px) {
  .works-grid { column-count: 1; }
  .managed-package-grid {
    column-count: 1;
  }
  .workspace-metrics {
    grid-template-columns: 1fr;
  }
  .workspace-head h3 {
    font-size: 18px;
  }
  .availability-calendar-card,
  .availability-detail-panel,
  .availability-topbar {
    padding: 12px;
  }
  .availability-calendar {
    gap: 4px;
  }
  .availability-date-cell {
    min-height: 62px;
    padding: 6px;
  }
  .availability-date-cell.is-blank {
    min-height: 62px;
  }
  .availability-status-badge {
    padding: 2px 5px;
    font-size: 11px;
  }
  .availability-location {
    display: none;
  }
  .fav-waterfall { column-count: 1; }
}
@media (max-width: 992px) { .fav-waterfall { column-count: 3; } }
@media (max-width: 768px) { .fav-waterfall { column-count: 2; } }
@media (max-width: 480px) { .fav-waterfall { column-count: 1; } }
</style>
