<template>
  <!-- 术语提示：在专业名词旁显示一个问号图标，悬停/点击显示解释 -->
  <el-tooltip
    :content="term ? term.short : '术语解释'"
    placement="top"
    :show-after="200"
    effect="dark"
  >
    <span
      class="term-tip"
      :class="{ clickable: term }"
      role="button"
      tabindex="0"
      @click.stop="term && openDetail()"
      @keydown.enter.prevent="term && openDetail()"
    >
      <el-icon :size="size"><QuestionFilled /></el-icon>
    </span>
  </el-tooltip>

  <!-- 详细解释弹窗 -->
  <el-dialog v-model="detailVisible" :title="term?.title || '术语说明'" width="480px" append-to-body>
    <div v-if="term" class="term-detail">
      <p class="term-short">{{ term.short }}</p>
      <el-divider />
      <div class="term-detail-text">{{ term.detail }}</div>
      <el-alert
        v-if="term.tip"
        :title="term.tip"
        type="warning"
        :closable="false"
        show-icon
        class="term-tip-alert"
      />
    </div>
    <template #footer>
      <el-button type="primary" @click="detailVisible = false">明白了</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed } from 'vue'
import { QuestionFilled } from '@element-plus/icons-vue'
import { getTerm } from '@/utils/terms'

const props = defineProps({
  /** 术语 key，对应 terms.js 中的键 */
  termKey: { type: String, required: true },
  /** 图标大小 */
  size: { type: Number, default: 14 },
})

const term = computed(() => getTerm(props.termKey))
const detailVisible = ref(false)

function openDetail() {
  if (term.value) detailVisible.value = true
}
</script>

<style scoped>
.term-tip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-left: 4px;
  color: var(--el-text-color-secondary, #909399);
  vertical-align: middle;
  line-height: 1;
}

.term-tip.clickable {
  cursor: pointer;
  transition: color 0.2s;
}

.term-tip.clickable:hover {
  color: var(--el-color-primary, #409eff);
}

.term-detail {
  padding: 0 4px;
}

.term-short {
  font-size: 15px;
  font-weight: 500;
  color: var(--el-text-color-primary, #303133);
  line-height: 1.6;
}

.term-detail-text {
  font-size: 14px;
  color: var(--el-text-color-regular, #606266);
  line-height: 1.8;
  white-space: pre-line;
  margin-bottom: 16px;
}

.term-tip-alert {
  margin-top: 8px;
}
</style>
