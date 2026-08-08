<template>
  <div class="algo-batches-wrap">
    <h4 v-if="title" class="table-title">{{ title }}</h4>
    <el-table
      :data="list"
      v-loading="loading"
      border stripe
      style="margin-top:12px"
      :empty-text="empty ? '暂无进行中的批次，可打开「含历史」查看已完成批次' : '暂无数据'"
    >
      <el-table-column prop="inst_id" label="品种" width="130" />
      <el-table-column label="方向" width="70">
        <template #default="{ row }">
          <el-tag :type="row.side === 'buy' ? 'success' : 'danger'" size="small">
            {{ row.side === 'buy' ? '买入' : '卖出' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="切片进度" min-width="220">
        <template #default="{ row }">
          <div class="progress-cell">
            <el-progress
              :percentage="Math.round(row.progress * 100)"
              :status="row.progress >= 1 ? 'success' : undefined"
              :stroke-width="12"
            />
            <div class="progress-text">
              {{ row.filled_slices }}/{{ row.total_slices }} 片已成交
              <span v-if="row.pending_slices">（待成交 {{ row.pending_slices }} 片）</span>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="数量" width="160">
        <template #default="{ row }">
          <div>总量 {{ row.total_sz }}</div>
          <div class="sub-tip">已成交 {{ row.fill_sz }}</div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag v-if="history" type="success" size="small">已完成</el-tag>
          <el-tag v-else-if="row.progress >= 1" type="success" size="small">已完成</el-tag>
          <el-tag v-else type="warning" size="small">执行中</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="170">
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column v-if="!history" label="操作" width="180" fixed="right" align="center">
        <template #default="{ row }">
          <el-button
            v-if="row.pending_slices > 0 || (row.progress > 0 && row.progress < 1)"
            size="small" type="danger" text
            @click.stop="$emit('cancel', row)"
          >撤销剩余挂单</el-button>
          <el-button
            size="small" type="primary" text
            @click.stop="expanded[row.batch_id] = !expanded[row.batch_id]"
          >
            {{ expanded[row.batch_id] ? '收起子单' : '展开子单' }}
          </el-button>
        </template>
      </el-table-column>
      <el-table-column v-if="history" label="详情" width="120" align="center">
        <template #default="{ row }">
          <el-button
            size="small" type="primary" text
            @click.stop="expanded[row.batch_id] = !expanded[row.batch_id]"
          >
            {{ expanded[row.batch_id] ? '收起' : '展开子单' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 展开子单详情 -->
    <div v-for="row in list" :key="'expand_'+row.batch_id">
      <el-collapse-transition>
        <el-table
          v-show="expanded[row.batch_id] && row.details && row.details.length"
          :data="row.details" size="small" border stripe
          style="margin: 2px 0 16px 24px"
        >
          <el-table-column label="子单ID" width="90" prop="id" />
          <el-table-column label="方向" width="70">
            <template #default="{ d }">{{ d.side === 'buy' ? '买' : '卖' }}</template>
          </el-table-column>
          <el-table-column label="类型" width="70">
            <template #default="{ d }">{{ d.ord_type }}</template>
          </el-table-column>
          <el-table-column label="数量" width="90" prop="sz" />
          <el-table-column label="限价" width="110" prop="px" />
          <el-table-column label="成交" width="90" prop="fill_sz" />
          <el-table-column label="状态" width="100">
            <template #default="{ d }">
              <el-tag
                size="small"
                :type="d.state === 'filled' ? 'success' : d.state === 'canceled' ? 'info' : d.state === 'live' ? 'warning' : 'danger'"
              >{{ d.state }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="创建" width="170">
            <template #default="{ d }">{{ formatDateTime(d.created_at) }}</template>
          </el-table-column>
        </el-table>
      </el-collapse-transition>
    </div>
  </div>
</template>

<script setup>
import { reactive } from 'vue'
import { formatDateTime } from '@/utils/time'

const props = defineProps({
  title: { type: String, default: '' },
  list: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  empty: { type: Boolean, default: false },
  history: { type: Boolean, default: false },
})

defineEmits(['cancel'])

const expanded = reactive({})
</script>

<style scoped>
.table-title { margin: 12px 0 0; font-size: 14px; color: #606266; font-weight: 600; }
.progress-cell .progress-text { font-size: 12px; margin-top: 4px; color: #606266; }
.sub-tip { font-size: 11px; color: #909399; margin-top: 2px; }
</style>
