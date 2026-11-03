<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { NButton, NInput, NInputNumber, NModal, NSelect, NSlider } from "naive-ui";
import type { AttachmentUpload } from "../api/attachments";

const props = defineProps<{ show: boolean; aspect?: number | null }>();
const emit = defineEmits<{ "update:show": [boolean]; confirm: [AttachmentUpload] }>();

const formatOptions = [
  { label: "JPEG（适合照片，体积最小）", value: "image/jpeg" },
  { label: "WebP（体积与画质兼顾）", value: "image/webp" },
  { label: "PNG（保留透明背景）", value: "image/png" },
];
const ratioOptions = [
  { label: "自由裁剪", value: 0 },
  { label: "1:1", value: 1 },
  { label: "4:3", value: 4 / 3 },
  { label: "3:4", value: 3 / 4 },
  { label: "16:9", value: 16 / 9 },
];

const fileInput = ref<HTMLInputElement | null>(null);
const stage = ref<HTMLDivElement | null>(null);
const bitmap = ref<ImageBitmap | null>(null);
const sourceUrl = ref("");
const sourceW = ref(0);
const sourceH = ref(0);
const crop = ref({ x: 0, y: 0, w: 1, h: 1 });
const ratio = ref(props.aspect || 0);
const linked = ref(true);
const outWidth = ref(1);
const outHeight = ref(1);
const format = ref("image/jpeg");
const quality = ref(82);
const caption = ref("");
const error = ref("");
const note = ref("");
const previewUrl = ref("");
const previewSize = ref(0);
const originalName = ref("image");
const preparing = ref(false);
const pendingBlob = ref<Blob | null>(null);
let previewTimer: number | undefined;

const shown = computed({
  get: () => props.show,
  set: (value: boolean) => emit("update:show", value),
});
const cropStyle = computed(() => ({
  left: `${(crop.value.x / Math.max(1, sourceW.value)) * 100}%`,
  top: `${(crop.value.y / Math.max(1, sourceH.value)) * 100}%`,
  width: `${(crop.value.w / Math.max(1, sourceW.value)) * 100}%`,
  height: `${(crop.value.h / Math.max(1, sourceH.value)) * 100}%`,
}));
const cropRatio = computed(() => crop.value.w / Math.max(1, crop.value.h));
const previewKb = computed(() => (previewSize.value / 1024).toFixed(1));
const qualityEnabled = computed(() => format.value !== "image/png");

watch(() => props.show, (value) => {
  if (value) resetState();
  else { endDrag(); clearPreview(); }
});
watch(ratio, () => { if (bitmap.value) applyRatio(); });
watch([format, quality], () => schedulePreview());

function clearPreview() {
  window.clearTimeout(previewTimer);
  pendingBlob.value = null;
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value);
  previewUrl.value = "";
  previewSize.value = 0;
}

function resetState() {
  bitmap.value?.close();
  bitmap.value = null;
  if (sourceUrl.value) URL.revokeObjectURL(sourceUrl.value);
  sourceUrl.value = "";
  sourceW.value = 0;
  sourceH.value = 0;
  clearPreview();
  error.value = "";
  note.value = "";
  caption.value = "";
  ratio.value = props.aspect || 0;
  format.value = "image/jpeg";
  quality.value = 82;
  linked.value = true;
  preparing.value = false;
}

function pick() { fileInput.value?.click(); }
function choose(event: Event) {
  const input = event.currentTarget as HTMLInputElement;
  void loadFile(input.files?.[0]);
  input.value = "";
}
function drop(event: DragEvent) { void loadFile(event.dataTransfer?.files?.[0]); }

async function loadFile(file: File | null | undefined) {
  if (!file) return;
  error.value = "";
  note.value = "";
  if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) {
    error.value = "只支持 PNG、JPEG 或 WebP 图片";
    return;
  }
  try {
    const image = await createImageBitmap(file);
    bitmap.value?.close();
    bitmap.value = image;
    if (sourceUrl.value) URL.revokeObjectURL(sourceUrl.value);
    sourceUrl.value = URL.createObjectURL(file);
    sourceW.value = image.width;
    sourceH.value = image.height;
    originalName.value = file.name.replace(/\.[^.]+$/, "") || "image";
    applyRatio();
  } catch {
    error.value = "无法读取这张图片，请换一张试试";
  }
}

function clamp(value: number, low: number, high: number) {
  return Math.min(high, Math.max(low, value));
}

function applyRatio() {
  if (!sourceW.value || !sourceH.value) return;
  const target = ratio.value > 0 ? ratio.value : 0;
  let width = sourceW.value;
  let height = sourceH.value;
  if (target) {
    if (width / height > target) width = height * target;
    else height = width / target;
  }
  crop.value = {
    x: Math.round((sourceW.value - width) / 2),
    y: Math.round((sourceH.value - height) / 2),
    w: Math.max(16, Math.round(width)),
    h: Math.max(16, Math.round(height)),
  };
  linked.value = true;
  outWidth.value = Math.min(crop.value.w, 1200);
  outHeight.value = target
    ? Math.max(16, Math.round(outWidth.value / target))
    : Math.max(16, Math.round(outWidth.value * (crop.value.h / crop.value.w)));
  schedulePreview();
}

function setOutWidth(value: number | null) {
  outWidth.value = clamp(Math.round(value || 16), 16, 20000);
  if (linked.value) outHeight.value = Math.max(16, Math.round(outWidth.value / cropRatio.value));
  schedulePreview();
}
function setOutHeight(value: number | null) {
  outHeight.value = clamp(Math.round(value || 16), 16, 20000);
  if (linked.value) outWidth.value = Math.max(16, Math.round(outHeight.value * cropRatio.value));
  schedulePreview();
}

type DragMode = "move" | "nw" | "ne" | "sw" | "se" | "n" | "e" | "s" | "w";
interface CropRect { x: number; y: number; w: number; h: number }
let drag: { mode: DragMode; startX: number; startY: number; crop: CropRect } | null = null;

function startDrag(event: PointerEvent, mode: DragMode) {
  if (!bitmap.value) return;
  event.preventDefault();
  event.stopPropagation();
  drag = { mode, startX: event.clientX, startY: event.clientY, crop: { ...crop.value } };
  window.addEventListener("pointermove", onPointerMove);
  window.addEventListener("pointerup", endDrag);
}
function endDrag() {
  drag = null;
  window.removeEventListener("pointermove", onPointerMove);
  window.removeEventListener("pointerup", endDrag);
}

function resizeFree(start: CropRect, mode: DragMode, dx: number, dy: number, min: number): CropRect {
  let left = start.x, top = start.y, right = start.x + start.w, bottom = start.y + start.h;
  if (mode.includes("w")) left = clamp(left + dx, 0, right - min);
  if (mode.includes("e")) right = clamp(right + dx, left + min, sourceW.value);
  if (mode.includes("n")) top = clamp(top + dy, 0, bottom - min);
  if (mode.includes("s")) bottom = clamp(bottom + dy, top + min, sourceH.value);
  return { x: left, y: top, w: right - left, h: bottom - top };
}

function resizeLocked(start: CropRect, mode: DragMode, dx: number, dy: number, min: number): CropRect {
  const target = ratio.value;
  const west = mode.includes("w");
  const north = mode.includes("n");
  const anchorX = west ? start.x + start.w : start.x;
  const anchorY = north ? start.y + start.h : start.y;
  const maxW = west ? anchorX : sourceW.value - anchorX;
  const maxH = north ? anchorY : sourceH.value - anchorY;
  const widthFromX = west ? start.w - dx : start.w + dx;
  const widthFromY = (north ? start.h - dy : start.h + dy) * target;
  let width = Math.abs(dx) >= Math.abs(dy) ? widthFromX : widthFromY;
  const limit = Math.max(min, Math.min(maxW, maxH * target));
  width = clamp(width, min, limit);
  const height = width / target;
  return { x: west ? anchorX - width : anchorX, y: north ? anchorY - height : anchorY, w: width, h: height };
}

function onPointerMove(event: PointerEvent) {
  if (!drag || !stage.value) return;
  const box = stage.value.getBoundingClientRect();
  if (!box.width || !box.height) return;
  const dx = (event.clientX - drag.startX) * (sourceW.value / box.width);
  const dy = (event.clientY - drag.startY) * (sourceH.value / box.height);
  const min = 16;
  let next: CropRect;
  if (drag.mode === "move") {
    next = {
      ...drag.crop,
      x: clamp(drag.crop.x + dx, 0, sourceW.value - drag.crop.w),
      y: clamp(drag.crop.y + dy, 0, sourceH.value - drag.crop.h),
    };
  } else if (ratio.value > 0) {
    next = resizeLocked(drag.crop, drag.mode, dx, dy, min);
  } else {
    next = resizeFree(drag.crop, drag.mode, dx, dy, min);
  }
  const rounded = {
    x: Math.round(next.x),
    y: Math.round(next.y),
    w: Math.max(1, Math.round(next.w)),
    h: Math.max(1, Math.round(next.h)),
  };
  if (ratio.value > 0) {
    rounded.h = Math.max(1, Math.round(rounded.w / ratio.value));
    rounded.x = clamp(rounded.x, 0, sourceW.value - rounded.w);
    rounded.y = clamp(rounded.y, 0, sourceH.value - rounded.h);
  }
  crop.value = rounded;
  if (linked.value) outHeight.value = Math.max(16, Math.round(outWidth.value / cropRatio.value));
  schedulePreview();
}

function schedulePreview() {
  window.clearTimeout(previewTimer);
  previewTimer = window.setTimeout(() => { void renderPreview(); }, 120);
}

async function renderPreview() {
  if (!bitmap.value) return;
  preparing.value = true;
  const width = clamp(outWidth.value, 1, 20000);
  const height = clamp(outHeight.value, 1, 20000);
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (!context) { preparing.value = false; return; }
  if (format.value === "image/jpeg") {
    context.fillStyle = "#fff";
    context.fillRect(0, 0, width, height);
  }
  context.imageSmoothingEnabled = true;
  context.imageSmoothingQuality = "high";
  context.drawImage(bitmap.value, crop.value.x, crop.value.y, crop.value.w, crop.value.h, 0, 0, width, height);
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, format.value, quality.value / 100));
  preparing.value = false;
  if (!blob) { error.value = "无法生成预览，请调整尺寸后重试"; return; }
  pendingBlob.value = blob;
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value);
  previewUrl.value = URL.createObjectURL(blob);
  previewSize.value = blob.size;
  note.value = blob.type !== format.value ? "当前浏览器不支持所选格式，将改用 PNG 输出。" : "";
}

async function confirm() {
  await renderPreview();
  const blob = pendingBlob.value;
  if (!blob) { error.value = "无法生成图片，请调整尺寸后重试"; return; }
  const ext = blob.type === "image/jpeg" ? "jpg" : blob.type === "image/webp" ? "webp" : "png";
  emit("confirm", {
    blob,
    filename: `${originalName.value}.${ext}`,
    width: clamp(outWidth.value, 1, 20000),
    height: clamp(outHeight.value, 1, 20000),
    caption: caption.value.trim(),
  });
  shown.value = false;
}

onBeforeUnmount(() => {
  endDrag();
  clearPreview();
  bitmap.value?.close();
  if (sourceUrl.value) URL.revokeObjectURL(sourceUrl.value);
});
</script>

<template>
  <NModal v-model:show="shown" preset="card" title="准备图片" class="dialog prepare-dialog"
    :style="{ width: '960px', maxWidth: 'calc(100vw - 24px)' }">
    <template v-if="!bitmap">
      <div class="prepare-drop" role="button" tabindex="0" @click="pick" @keydown.enter="pick"
        @dragover.prevent @drop.prevent="drop">
        <strong>选择或拖入图片</strong>
        <span>支持 PNG、JPEG、WebP；上传前可裁剪、缩放并降低清晰度，把文件控制到几十 KB。</span>
      </div>
      <input ref="fileInput" type="file" accept="image/png,image/jpeg,image/webp" hidden @change="choose" />
    </template>
    <template v-else>
      <div class="prepare-layout">
        <div class="prepare-editor">
          <div class="prepare-stage" @dragover.prevent @drop.prevent="drop">
            <div ref="stage" class="prepare-canvas">
              <img :src="sourceUrl" alt="待处理图片" draggable="false" />
              <div class="prepare-crop" :style="cropStyle" @pointerdown="startDrag($event, 'move')">
                <span class="prepare-grid" aria-hidden="true" />
                <span class="prepare-handle corner nw" @pointerdown="startDrag($event, 'nw')" />
                <span class="prepare-handle corner ne" @pointerdown="startDrag($event, 'ne')" />
                <span class="prepare-handle corner sw" @pointerdown="startDrag($event, 'sw')" />
                <span class="prepare-handle corner se" @pointerdown="startDrag($event, 'se')" />
                <template v-if="ratio === 0">
                  <span class="prepare-handle edge n" @pointerdown="startDrag($event, 'n')" />
                  <span class="prepare-handle edge e" @pointerdown="startDrag($event, 'e')" />
                  <span class="prepare-handle edge s" @pointerdown="startDrag($event, 's')" />
                  <span class="prepare-handle edge w" @pointerdown="startDrag($event, 'w')" />
                </template>
              </div>
            </div>
          </div>
          <p class="prepare-meta">
            原图 {{ sourceW }} × {{ sourceH }}，裁剪区域 {{ Math.round(crop.w) }} × {{ Math.round(crop.h) }}。
            拖动选区移动，拖动角点或边调整大小；固定比例时角点按比例缩放。
          </p>
        </div>
        <div class="prepare-controls">
          <div class="prepare-preview-card">
            <div class="prepare-preview-stage">
              <img v-if="previewUrl" :src="previewUrl" alt="处理效果预览" />
              <span v-else>{{ preparing ? "正在生成预览…" : "效果预览" }}</span>
            </div>
            <p class="prepare-preview-size">
              <template v-if="previewSize">预计 {{ previewKb }} KB · {{ outWidth }} × {{ outHeight }}</template>
              <template v-else>调整裁剪或尺寸后在这里查看效果</template>
            </p>
          </div>
          <label>裁剪比例<NSelect v-model:value="ratio" :options="ratioOptions" /></label>
          <label>输出尺寸
            <div class="prepare-size">
              <NInputNumber :value="outWidth" :min="16" :max="20000" @update:value="setOutWidth" />
              <span>×</span>
              <NInputNumber :value="outHeight" :min="16" :max="20000" @update:value="setOutHeight" />
            </div>
          </label>
          <p class="prepare-hint">
            <span v-if="linked">宽高按裁剪比例联动；</span>
            <span v-else>宽高独立，会拉伸图片；</span>
            <NButton text type="primary" size="tiny" @click="linked = !linked">{{ linked ? "解除联动以拉伸" : "恢复按比例联动" }}</NButton>
          </p>
          <label>格式<NSelect v-model:value="format" :options="formatOptions" /></label>
          <label>清晰度 {{ quality }}%<NSlider v-model:value="quality" :min="30" :max="100" :step="5" :disabled="!qualityEnabled" /></label>
          <label>说明（可选）<NInput v-model:value="caption" maxlength="200" placeholder="如：8月摊位费收据" /></label>
          <p v-if="note" class="prepare-hint">{{ note }}</p>
          <p v-if="error" class="error" role="alert">{{ error }}</p>
        </div>
      </div>
      <input ref="fileInput" type="file" accept="image/png,image/jpeg,image/webp" hidden @change="choose" />
    </template>
    <div class="actions">
      <NButton v-if="bitmap" @click="pick">重新选择</NButton>
      <NButton @click="shown = false">取消</NButton>
      <NButton type="primary" :loading="preparing" :disabled="!bitmap || !pendingBlob" @click="confirm">使用这张图片</NButton>
    </div>
  </NModal>
</template>

<style scoped>
.prepare-drop { display:flex; flex-direction:column; align-items:center; gap:8px; padding:44px 20px; border:1px dashed #9fb3c4; border-radius:8px; background:#f7f9fa; cursor:pointer; text-align:center; }
.prepare-drop span { color:#66707c; font-size:13px; max-width:520px; }
.prepare-layout { display:grid; grid-template-columns:minmax(0,1fr) 272px; gap:16px; align-items:start; }
.prepare-editor { min-width:0; }
.prepare-stage { position:relative; display:flex; justify-content:center; align-items:center; min-height:220px; max-height:480px; overflow:hidden; background:#0f1c26; border-radius:8px; touch-action:none; }
.prepare-canvas { position:relative; display:inline-block; max-width:100%; line-height:0; }
.prepare-canvas img { display:block; max-width:100%; max-height:480px; user-select:none; }
.prepare-crop { position:absolute; cursor:move; box-shadow:0 0 0 9999px rgba(15,28,38,.55); border:1px solid #fff; touch-action:none; }
.prepare-grid { position:absolute; inset:0; pointer-events:none; background-image:
  linear-gradient(to right, rgba(255,255,255,.35) 1px, transparent 1px),
  linear-gradient(to bottom, rgba(255,255,255,.35) 1px, transparent 1px);
  background-size:33.333% 33.333%; opacity:.7; }
.prepare-handle { position:absolute; background:#fff; border:1px solid #345d78; border-radius:2px; touch-action:none; }
.prepare-handle.corner { width:12px; height:12px; }
.prepare-handle.corner.nw { left:-6px; top:-6px; cursor:nwse-resize; }
.prepare-handle.corner.ne { right:-6px; top:-6px; cursor:nesw-resize; }
.prepare-handle.corner.sw { left:-6px; bottom:-6px; cursor:nesw-resize; }
.prepare-handle.corner.se { right:-6px; bottom:-6px; cursor:nwse-resize; }
.prepare-handle.edge { width:20px; height:10px; }
.prepare-handle.edge.n { left:50%; top:-5px; transform:translateX(-50%); cursor:ns-resize; }
.prepare-handle.edge.s { left:50%; bottom:-5px; transform:translateX(-50%); cursor:ns-resize; }
.prepare-handle.edge.e { top:50%; right:-5px; transform:translateY(-50%); width:10px; height:20px; cursor:ew-resize; }
.prepare-handle.edge.w { top:50%; left:-5px; transform:translateY(-50%); width:10px; height:20px; cursor:ew-resize; }
.prepare-meta, .prepare-hint { color:#66707c; font-size:12px; line-height:1.6; margin:6px 0 0; }
.prepare-controls { display:flex; flex-direction:column; gap:10px; min-width:0; }
.prepare-controls label { display:flex; flex-direction:column; gap:4px; font-size:13px; color:#34515f; }
.prepare-preview-card { display:flex; flex-direction:column; gap:6px; }
.prepare-preview-stage { display:flex; align-items:center; justify-content:center; min-height:132px; max-height:180px; padding:6px; border:1px solid #e3e8ec; border-radius:8px;
  background-color:#fafbfc;
  background-image:linear-gradient(45deg,#eef1f3 25%,transparent 25%,transparent 75%,#eef1f3 75%),linear-gradient(45deg,#eef1f3 25%,transparent 25%,transparent 75%,#eef1f3 75%);
  background-size:16px 16px; background-position:0 0,8px 8px; }
.prepare-preview-stage img { display:block; max-width:100%; max-height:168px; }
.prepare-preview-stage span { color:#8a949e; font-size:12px; }
.prepare-preview-size { margin:0; color:#66707c; font-size:12px; }
.prepare-size { display:flex; align-items:center; gap:6px; }
.prepare-size span { color:#66707c; }
.actions { display:flex; justify-content:flex-end; gap:8px; margin-top:14px; }
@media (max-width:760px) {
  .prepare-layout { grid-template-columns:minmax(0,1fr); }
  .prepare-controls { order:2; }
  .prepare-stage, .prepare-canvas img { max-height:320px; }
}
</style>
