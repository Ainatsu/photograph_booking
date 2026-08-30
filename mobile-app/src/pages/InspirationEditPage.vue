<template>
  <ion-page>
    <DetailHeader :title="isEdit ? '编辑灵感' : '新建灵感'" default-href="/inspirations">
      <template #action><button type="button" class="header-action" aria-label="保存灵感" @click="save('saved')"><Check :size="21" /></button></template>
    </DetailHeader>
    <ion-content class="page-content">
      <main class="page-shell edit-shell">
        <FeedSkeleton v-if="loading" :count="2" />
        <form v-else @submit.prevent="save('saved')">
          <label><span class="field-label">标题 <strong>*</strong></span><input v-model="form.title" maxlength="120" placeholder="给这条灵感一个名字" required @keydown.enter.prevent /></label>
          <label><span class="field-label">摘要</span><textarea v-model="form.summary" maxlength="300" rows="3" placeholder="记住它最重要的感觉" /></label>
          <section class="content-editor">
            <div class="content-editor-heading">
              <div>
                <span class="field-label">灵感内容</span>
                <small>可自由组合文字段落与图片</small>
              </div>
              <div class="block-actions">
                <button type="button" class="editor-action" @click="addParagraph"><AlignLeft :size="18" />添加段落</button>
                <label class="editor-action upload-button" :class="{ uploading }"><ImagePlus :size="18" />{{ uploading ? '上传中…' : '添加图片' }}<input type="file" accept="image/jpeg,image/png,image/webp" :disabled="uploading" @change="onImageSelected" /></label>
              </div>
            </div>
            <div v-for="(block, index) in form.content" :key="index" class="content-block">
              <textarea v-if="block.type !== 'image'" v-model="block.text" rows="5" placeholder="写下光线、构图、情绪或拍摄想法……" />
              <div v-else class="image-block"><img :src="resolveMediaUrl(block.thumb_url || block.url)" :alt="block.alt || '灵感图片'" /><span>图片</span></div>
              <button v-if="form.content.length > 1" type="button" class="remove-block" aria-label="删除内容块" @click="removeBlock(index)"><Trash2 :size="17" /></button>
            </div>
          </section>
          <label>
            <span class="field-label">标签</span>
            <div v-if="form.tags.length" class="tag-list" aria-label="已添加标签">
              <span v-for="tag in form.tags" :key="tag" class="tag-chip">{{ tag }}<button type="button" :aria-label="`移除标签 ${tag}`" @click="removeTag(tag)"><X :size="15" /></button></span>
            </div>
            <div class="tag-input-wrap">
              <input v-model="tagDraft" maxlength="30" placeholder="输入标签" @keydown.enter.prevent="addTag" />
              <button type="button" :disabled="!tagDraft.trim() || form.tags.length >= 10" @click="addTag">确认</button>
            </div>
            <small>{{ form.tags.length }}/10，按 Enter 或确认按钮添加</small>
          </label>
          <section class="location-card"><div><MapPin :size="19" /><span>{{ form.location_name || '尚未关联拍摄地点' }}</span></div><button type="button" class="secondary-button" @click="pickerVisible = true">{{ form.location_name ? '更换地点' : '关联地点' }}</button></section>
          <div class="save-actions"><button type="button" class="secondary-button" @click="save('draft')">保存草稿</button><button type="submit" class="primary-button">保存灵感</button></div>
        </form>
      </main>
      <LocationPickerModal v-model="pickerVisible" :location="form" @confirm="setLocation" />
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { IonContent, IonPage } from '@ionic/vue'
import { AlignLeft, Check, ImagePlus, MapPin, Trash2, X } from 'lucide-vue-next'
import DetailHeader from '@/components/DetailHeader.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import LocationPickerModal from '@/components/location/LocationPickerModal.vue'
import { createInspiration, getInspiration, updateInspiration, uploadInspirationImage } from '@/api/inspirations'
import type { Inspiration, InspirationPayload } from '@/types/inspiration'
import { resolveMediaUrl } from '@/utils/media'

const route = useRoute(), router = useRouter(), loading = ref(false), pickerVisible = ref(false), tagDraft = ref(''), uploading = ref(false)
const isEdit = computed(() => Boolean(route.params.inspirationId))
const form = reactive<InspirationPayload>({ title: '', summary: '', content: [{ type: 'paragraph', text: '' }], tags: [], location_name: null, location_address: null, latitude: null, longitude: null, place_id: null, provider: null, coordinate_system: null, location_precision: null, status: 'draft' })
function addTag() { const tag = tagDraft.value.trim(); if (!tag || form.tags.length >= 10) return; if (!form.tags.includes(tag)) form.tags.push(tag); tagDraft.value = '' }
function removeTag(tag: string) { form.tags = form.tags.filter((item) => item !== tag) }
function addParagraph() { form.content.push({ type: 'paragraph', text: '' }) }
function removeBlock(index: number) { form.content.splice(index, 1) }
async function onImageSelected(event: Event) { const input = event.target as HTMLInputElement; const file = input.files?.[0]; if (!file) return; uploading.value = true; try { const image = await uploadInspirationImage(file); form.content.push({ type: 'image', url: image.url, thumb_url: image.thumb_url, alt: form.title || '灵感图片' }); if (!form.cover_url) form.cover_url = image.thumb_url || image.url } finally { uploading.value = false; input.value = '' } }
async function load() { if (!isEdit.value) return; loading.value = true; try { Object.assign(form, await getInspiration(Number(route.params.inspirationId))); if (!form.content.length) form.content = [{ type: 'paragraph', text: '' }] } finally { loading.value = false } }
async function save(status: 'draft' | 'saved') { if (!form.title.trim()) return; const content = form.content.filter((block) => block.type === 'image' ? Boolean(block.url) : Boolean(block.text?.trim())); const payload = { ...form, content, status }; const item: Inspiration = isEdit.value ? await updateInspiration(Number(route.params.inspirationId), payload) : await createInspiration(payload); if (!isEdit.value) await router.replace({ name: 'inspiration-edit', params: { inspirationId: item.id } }); if (status === 'saved') void router.replace({ name: 'inspiration-detail', params: { inspirationId: item.id } }) }
function setLocation(value: any) { Object.assign(form, { location_name: value.name, location_address: value.address, latitude: value.latitude, longitude: value.longitude, place_id: value.place_id, provider: value.provider, coordinate_system: value.coordinate_system, location_precision: value.precision }) }
onMounted(() => void load())
</script>

<style scoped>
.edit-shell{padding-top:var(--space-4);padding-bottom:calc(var(--bottom-nav-height) + 40px)}form{display:grid;gap:var(--space-5)}label,.content-editor{display:grid;gap:8px;color:var(--ink);font-size:var(--text-sm);font-weight:750}.field-label strong{color:var(--danger)}label small,.content-editor small{display:block;margin-top:3px;color:var(--ink-tertiary);font-size:var(--text-xs);font-weight:500}input,textarea{width:100%;min-height:var(--touch-target);padding:12px 14px;border:1px solid var(--border);border-radius:var(--radius-md);background:#fff!important;background-color:#fff!important;background-clip:padding-box;color:#1c1c1e!important;-webkit-text-fill-color:#1c1c1e;box-shadow:0 1px 0 rgba(0,0,0,.03);font-size:var(--text-base);color-scheme:light;outline:none;-webkit-appearance:none;appearance:none}input::placeholder,textarea::placeholder{color:#8e8e93;-webkit-text-fill-color:#8e8e93}input:focus,textarea:focus{border-color:var(--brand);box-shadow:0 0 0 3px var(--focus-ring)}textarea{min-height:110px;resize:vertical}.content-editor{gap:12px;padding:14px;border:1px solid var(--border);border-radius:var(--radius-lg);background:#fff;box-shadow:0 1px 0 rgba(0,0,0,.03)}.content-editor-heading{display:grid;gap:12px}.content-block{position:relative}.content-block textarea{display:block;padding-right:52px;background:#fff!important;background-color:#fff!important}.image-block{position:relative;min-height:150px;overflow:hidden;border:1px solid var(--border);border-radius:var(--radius-md);background:#fff}.image-block img{display:block;width:100%;max-height:360px;object-fit:contain}.image-block span{position:absolute;top:8px;left:8px;padding:3px 8px;border-radius:var(--radius-pill);background:rgba(255,255,255,.92);color:var(--ink-secondary);font-size:var(--text-xs)}.remove-block{position:absolute;top:8px;right:8px;display:grid;width:44px;height:44px;place-items:center;border:1px solid var(--border);border-radius:50%;background:#fff;color:var(--danger)}.block-actions{display:grid;grid-template-columns:1fr 1fr;gap:var(--space-2)}.editor-action{display:inline-flex;min-height:48px;align-items:center;justify-content:center;gap:7px;margin:0;padding:0 12px;border:1px solid color-mix(in srgb,var(--brand) 35%,var(--border));border-radius:var(--radius-md);background:#fff;color:var(--brand);font-size:var(--text-sm);font-weight:800;cursor:pointer;touch-action:manipulation}.editor-action:active{background:var(--brand-soft)}.upload-button{width:100%}.upload-button.uploading{opacity:.6;pointer-events:none}.upload-button input{display:none}.tag-input-wrap{position:relative}.tag-input-wrap input{padding-right:82px}.tag-input-wrap>button{position:absolute;top:4px;right:4px;bottom:4px;min-height:40px;padding:0 14px;border:0;border-left:1px solid var(--border);border-radius:0 calc(var(--radius-md) - 4px) calc(var(--radius-md) - 4px) 0;background:#fff;color:var(--brand);font-size:var(--text-sm);font-weight:800}.tag-input-wrap>button:disabled{color:var(--ink-tertiary);opacity:.55}.tag-list{display:flex;flex-wrap:wrap;gap:8px}.tag-chip{display:inline-flex;min-height:36px;align-items:center;gap:2px;padding-left:12px;border:1px solid color-mix(in srgb,var(--brand) 24%,transparent);border-radius:var(--radius-pill);background:var(--brand-soft);color:var(--brand);font-size:var(--text-xs);font-weight:750}.tag-chip button{display:grid;width:36px;min-height:36px;place-items:center;padding:0;border:0;border-radius:50%;background:transparent;color:var(--brand)}.location-card{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px;border:1px solid var(--border);border-radius:var(--radius-md);background:#fff;box-shadow:0 1px 0 rgba(0,0,0,.03);color:var(--brand)}.location-card div{display:flex;align-items:center;gap:8px;min-width:0}.location-card span{overflow:hidden;color:#1c1c1e;text-overflow:ellipsis;white-space:nowrap}.secondary-button,.primary-button{display:inline-flex;min-height:var(--touch-target);align-items:center;justify-content:center;padding:0 16px;border:0;border-radius:var(--radius-md);font-weight:750}.secondary-button{background:var(--surface-secondary);color:var(--brand)}.primary-button{background:var(--brand);color:var(--white)}.save-actions{display:grid;grid-template-columns:1fr 1fr;gap:var(--space-3);padding-top:var(--space-3)}.header-action{display:grid;width:var(--touch-target);height:var(--touch-target);place-items:center;border:0;background:transparent;color:var(--brand)}
</style>
