<template>
  <main class="page">
    <section class="hero card">
      <div>
        <p class="eyebrow">Flask + MinIO + FFmpeg</p>
        <h1>实时视频转码播放</h1>
        <p class="subtitle">上传原始视频到 MinIO，播放时按 HDR / SDR 配置实时转码，不提前保存两份结果视频。</p>
      </div>
      <div class="status" :class="healthOk ? 'ok' : 'bad'">
        <span></span>
        {{ healthText }}
      </div>
    </section>

    <section class="grid">
      <form class="card panel" @submit.prevent="uploadVideo">
        <h2>1. 上传视频</h2>

        <label>
          Bucket
          <input v-model.trim="bucket" placeholder="videos" />
        </label>

        <label>
          Object Name
          <input v-model.trim="objectName" placeholder="demo.mp4" />
        </label>

        <label class="file-box">
          <input type="file" accept="video/*" @change="onFileChange" />
          <span>{{ selectedFile ? selectedFile.name : '选择本地视频文件' }}</span>
        </label>

        <button type="submit" :disabled="uploading || !selectedFile || !objectName">
          {{ uploading ? '上传中...' : '上传到 MinIO' }}
        </button>

        <div v-if="uploadProgress > 0" class="progress">
          <div :style="{ width: `${uploadProgress}%` }"></div>
        </div>

        <p v-if="uploadResult" class="message success">{{ uploadResult }}</p>
        <p v-if="error" class="message error">{{ error }}</p>
      </form>

      <section class="card panel">
        <h2>2. 实时转码参数</h2>

        <div class="segmented">
          <button type="button" :class="{ active: profile === 'hdr' }" @click="profile = 'hdr'">HDR</button>
          <button type="button" :class="{ active: profile === 'sdr' }" @click="profile = 'sdr'">SDR</button>
        </div>

        <div class="row">
          <label>
            Width
            <input v-model.number="width" type="number" min="2" step="2" />
          </label>
          <label>
            Height
            <input v-model.number="height" type="number" min="2" step="2" />
          </label>
        </div>

        <label>
          当前播放对象
          <input v-model.trim="objectName" placeholder="demo.mp4" />
        </label>

        <button type="button" :disabled="!objectName" @click="playStream">生成播放地址并播放</button>
        <button type="button" class="secondary" :disabled="!streamUrl" @click="reloadPlayer">重新加载</button>

        <textarea readonly :value="streamUrl" placeholder="播放地址会显示在这里"></textarea>
      </section>
    </section>

    <section class="card player-card">
      <div class="player-head">
        <h2>3. 播放器</h2>
        <a v-if="streamUrl" :href="streamUrl" target="_blank" rel="noreferrer">新窗口打开</a>
      </div>

      <video
        ref="videoRef"
        class="player"
        controls
        playsinline
        :src="streamUrl"
        @error="onVideoError"
      ></video>

      <p class="hint">
        当前后端输出 fragmented MP4 流。支持实时播放，但不保证拖动进度条；生产建议升级 HLS/DASH 分片。
      </p>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

const bucket = ref('videos')
const objectName = ref('')
const selectedFile = ref(null)
const uploading = ref(false)
const uploadProgress = ref(0)
const uploadResult = ref('')
const error = ref('')
const profile = ref('hdr')
const width = ref(1920)
const height = ref(1080)
const streamUrl = ref('')
const videoRef = ref(null)
const healthOk = ref(false)

const healthText = computed(() => (healthOk.value ? '后端在线' : '后端未连接'))

onMounted(() => {
  checkHealth()
})

async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/heal`)
    healthOk.value = res.ok
  } catch {
    healthOk.value = false
  }
}

function onFileChange(event) {
  const file = event.target.files?.[0]
  selectedFile.value = file || null
  error.value = ''
  uploadResult.value = ''

  if (file && !objectName.value) {
    objectName.value = file.name
  }
}

function buildStreamUrl() {
  const params = new URLSearchParams({
    bucket: bucket.value || 'videos',
    profile: profile.value,
    width: String(width.value || 1920),
    height: String(height.value || 1080),
  })
  return `${API_BASE}/video/${encodeURIComponent(objectName.value)}/stream?${params.toString()}`
}

async function uploadVideo() {
  if (!selectedFile.value || !objectName.value) return

  error.value = ''
  uploadResult.value = ''
  uploadProgress.value = 0
  uploading.value = true

  try {
    await uploadWithProgress(selectedFile.value)
    uploadResult.value = `上传成功：${bucket.value}/${objectName.value}`
    playStream()
  } catch (err) {
    error.value = err.message || '上传失败'
  } finally {
    uploading.value = false
  }
}

function uploadWithProgress(file) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    const params = new URLSearchParams({ bucket: bucket.value || 'videos' })
    xhr.open('POST', `${API_BASE}/video/${encodeURIComponent(objectName.value)}?${params.toString()}`)
    xhr.setRequestHeader('Content-Type', file.type || 'application/octet-stream')

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        uploadProgress.value = Math.round((event.loaded / event.total) * 100)
      }
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        uploadProgress.value = 100
        resolve(JSON.parse(xhr.responseText || '{}'))
        return
      }
      reject(new Error(parseError(xhr.responseText) || `上传失败：HTTP ${xhr.status}`))
    }

    xhr.onerror = () => reject(new Error('网络错误，无法连接后端'))
    xhr.send(file)
  })
}

function parseError(raw) {
  try {
    return JSON.parse(raw)?.error
  } catch {
    return raw
  }
}

function playStream() {
  error.value = ''
  streamUrl.value = buildStreamUrl()
  requestAnimationFrame(() => {
    videoRef.value?.load()
    videoRef.value?.play().catch(() => {})
  })
}

function reloadPlayer() {
  if (!streamUrl.value) return
  videoRef.value?.load()
}

function onVideoError() {
  if (!streamUrl.value) return
  error.value = '视频播放失败。请确认对象存在、后端可访问、FFmpeg 支持当前转码参数。'
}
</script>
