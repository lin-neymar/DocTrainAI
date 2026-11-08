<script setup lang="ts">
/**
 * 智能对话（阶段 3）：左侧会话区 + 右侧消息区。
 * 流式期间：citation 先建引用卡片，delta 逐段追加，done 回填 message_id，
 * error 展示错误并可重试；发送中禁止再次发送与切换会话。
 */
import { nextTick, onMounted, reactive, ref } from 'vue'
import { ElButton, ElEmpty, ElInput, ElMessage, ElMessageBox, ElTag } from 'element-plus'

import {
  createSessionApi,
  deleteSessionApi,
  listMessagesApi,
  listSessionsApi,
  sendMessageStreamApi,
  type ChatSessionItem,
  type Citation,
} from '@/api/ai_ext/chat'
import CitationCard from '@/components/ai_ext/CitationCard.vue'
import { formatDateTime } from '@/utils/datetime'

/** 消息区本地条目：流式期间 id 为 null，done 事件后回填 */
interface UiMessage {
  id: string | null
  role: 'user' | 'assistant'
  content: string
  refused: boolean
  citations: Citation[]
  streaming: boolean
  /** error 后待重试的用户原文 */
  retryText?: string
  /** error 文案 */
  error?: string
}

const sessions = ref<ChatSessionItem[]>([])
const sessionsLoading = ref(false)
const activeSessionId = ref<string | null>(null)
const messages = ref<UiMessage[]>([])
const input = ref('')
const sending = ref(false)
const listRef = ref<HTMLElement | null>(null)

// 流式跟随标志：发送后置 true，用户滚动离开底部即置 false 交还控制权
let followStream = false

// 实现：滚动到最新消息（主动操作：切换会话/加载历史/贴底跟随）
async function scrollToBottom() {
  await nextTick()
  if (listRef.value) {
    listRef.value.scrollTop = listRef.value.scrollHeight
  }
}

// 实现：贴底判定——内容底部与视口底缘的间距（padding/margin 已由
// scrollHeight 涵盖，无需测量任何元素）
function isAtBottom(): boolean {
  const list = listRef.value
  if (!list) return true
  return list.scrollHeight - list.scrollTop - list.clientHeight < 4
}

// 实现：用户滚动处理——滚离底部即交还控制权；程序化贴底滚动 gap=0 不误伤
function onListScroll() {
  if (followStream && !isAtBottom()) {
    followStream = false
  }
}

// 实现：切换会话并加载历史（时间正序）
async function switchSession(id: string) {
  activeSessionId.value = id
  const data = await listMessagesApi(id)
  messages.value = data.map((m) => ({
    id: m.id,
    role: m.role,
    content: m.content,
    refused: m.refused,
    citations: m.citations ?? [],
    streaming: false,
  }))
  await scrollToBottom()
}

// 实现：加载会话列表；首个会话自动打开
async function loadSessions() {
  sessionsLoading.value = true
  try {
    const data = await listSessionsApi(1, 50)
    sessions.value = data.items
    const first = sessions.value[0]
    if (!activeSessionId.value && first) {
      await switchSession(first.id)
    }
  } finally {
    sessionsLoading.value = false
  }
}

// 实现：发送一条消息（含流式追加与失败重试入口）
async function doSend(text: string) {
  const sessionId = activeSessionId.value
  if (!sessionId || sending.value) return
  const userMsg: UiMessage = {
    id: null,
    role: 'user',
    content: text,
    refused: false,
    citations: [],
    streaming: false,
  }
  // 注意：必须用 reactive 包裹——push 进 ref 数组后若继续修改「原始对象」
  // 不会触发 Vue 渲染（数组内部存的是 proxy），流式内容会全部静默失效
  const assistantMsg = reactive<UiMessage>({
    id: null,
    role: 'assistant',
    content: '',
    refused: false,
    citations: [],
    streaming: true,
  })
  messages.value.push(userMsg, assistantMsg)
  sending.value = true
  followStream = true
  // 发送后贴底：新会话中内容不满一屏时 clamp 到 0（气泡在视口上方生长），
  // 有历史消息时气泡贴底——两种情况都由「每帧贴底 + clamp」实现两阶段滚动
  await scrollToBottom()
  // 帧合并：delta 先入缓冲，每帧（rAF）合并写入一次，避免高频重排；
  // 只做帧合并不加慢——模型 token 的自然节奏原样保留
  let pendingText = ''
  let framePending = false
  const flushFrame = () => {
    if (pendingText) {
      assistantMsg.content += pendingText
      pendingText = ''
      // 每帧贴底：气泡未触底时 scrollTop 赋值被 clamp 回原值（视口不动），
      // 触底后每帧恰好贴底——文字随输出向上滚动，滚动条持续下移
      if (followStream) {
        void scrollToBottom()
      }
    }
    framePending = false
  }
  const pushDelta = (text: string) => {
    pendingText += text
    if (!framePending) {
      framePending = true
      requestAnimationFrame(flushFrame)
    }
  }
  try {
    await sendMessageStreamApi(sessionId, text, (event) => {
      if (event.type === 'citation') {
        // 引用数据照常入队，渲染推迟到流结束（模板 !m.streaming 条件）
        assistantMsg.citations.push(event.citation)
      } else if (event.type === 'delta') {
        pushDelta(event.text)
      } else if (event.type === 'done') {
        // 冲刷残余缓冲后收尾：回填 id、展开引用、光标消失
        flushFrame()
        assistantMsg.id = event.messageId
        assistantMsg.refused = event.refused
        assistantMsg.streaming = false
        if (followStream) {
          void scrollToBottom()
        }
      } else if (event.type === 'error') {
        flushFrame()
        assistantMsg.error = event.message
        assistantMsg.retryText = text
        assistantMsg.streaming = false
      }
    })
  } catch (err) {
    flushFrame()
    assistantMsg.error = err instanceof Error ? err.message : '发送失败'
    assistantMsg.retryText = text
    assistantMsg.streaming = false
  } finally {
    sending.value = false
  }
}

// 实现：发送框提交（Enter 发送）
async function onSubmit() {
  const text = input.value.trim()
  if (!text || sending.value) return
  input.value = ''
  await doSend(text)
}

// 实现：失败重试——移除失败的问答两条（后端未落库），重新发送
async function retry(index: number) {
  const failed = messages.value[index]
  if (!failed?.retryText || sending.value) return
  messages.value.splice(index - 1, 2)
  await doSend(failed.retryText)
}

// 实现：新建会话并切换到空白消息区
async function onCreateSession() {
  if (sending.value) return
  const session = await createSessionApi()
  sessions.value.unshift(session)
  activeSessionId.value = session.id
  messages.value = []
}

// 实现：删除会话——确认后调用接口；激活会话被删时切换到剩余首个会话
async function onDeleteSession(index: number, id: string) {
  if (sending.value) return
  try {
    await ElMessageBox.confirm('删除该会话后对话记录不可恢复，确定删除？', '删除会话', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteSessionApi(id)
    const wasActive = activeSessionId.value === id
    sessions.value.splice(index, 1)
    if (wasActive) {
      activeSessionId.value = null
      messages.value = []
      const first = sessions.value[0]
      if (first) {
        await switchSession(first.id)
      }
    }
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '删除失败')
  }
}

onMounted(() => {
  void loadSessions()
})
</script>

<template>
  <div class="chat-view">
    <!-- 会话区 -->
    <aside class="sessions">
      <div class="sessions-head">
        <span class="sessions-title">会话</span>
        <ElButton
          type="primary"
          size="small"
          :disabled="sending"
          :loading="sessionsLoading"
          @click="onCreateSession"
        >
          新建
        </ElButton>
      </div>
      <div v-if="sessions.length" class="sessions-list">
        <div
          v-for="(s, i) in sessions"
          :key="s.id"
          class="session-item"
          :class="{ active: s.id === activeSessionId }"
          @click="!sending && switchSession(s.id)"
        >
          <div class="session-main">
            <span class="session-name">会话 {{ sessions.length - i }}</span>
            <span class="session-time">{{ formatDateTime(s.created_at) }}</span>
          </div>
          <button
            v-if="!sending"
            class="session-delete"
            type="button"
            title="删除会话"
            @click.stop="onDeleteSession(i, s.id)"
          >
            <svg
              viewBox="0 0 24 24"
              width="15"
              height="15"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <path d="M3 6h18" />
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
              <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              <line x1="10" y1="11" x2="10" y2="17" />
              <line x1="14" y1="11" x2="14" y2="17" />
            </svg>
          </button>
        </div>
      </div>
      <ElEmpty v-else description="暂无会话" :image-size="60" />
    </aside>

    <!-- 消息区 -->
    <section class="chat-main">
      <div
        ref="listRef"
        class="messages"
        @wheel.passive="followStream = false"
        @touchmove.passive="followStream = false"
        @scroll="onListScroll"
      >
        <ElEmpty v-if="!messages.length" description="新建会话后开始提问" class="empty" />
        <div
          v-for="(m, i) in messages"
          :key="m.id ?? `pending-${i}`"
          class="message-row"
          :class="m.role"
        >
          <div class="bubble" :class="{ refused: m.refused, failed: m.error }">
            <ElTag v-if="m.refused" type="warning" size="small" class="refuse-tag">
              未找到相关资料
            </ElTag>
            <div v-if="m.content" class="content">
              {{ m.content }}<span v-if="m.streaming" class="cursor">▍</span>
            </div>
            <div v-if="m.streaming && !m.content" class="typing">正在思考…</div>
            <div v-if="m.citations.length && !m.streaming && !m.error" class="citations">
              <CitationCard
                v-for="(c, ci) in m.citations"
                :key="`${c.chunk_id}-${ci}`"
                :citation="c"
              />
            </div>
            <div v-if="m.error" class="error-box">
              <span class="error-text">{{ m.error }}</span>
              <ElButton link type="primary" size="small" @click="retry(i)"> 重试 </ElButton>
            </div>
          </div>
        </div>
      </div>

      <footer class="composer">
        <ElInput
          v-model="input"
          type="textarea"
          :rows="3"
          resize="none"
          placeholder="输入问题，Enter 发送，Shift+Enter 换行"
          :disabled="!activeSessionId || sending"
          @keydown.enter.exact.prevent="onSubmit"
        />
        <ElButton
          type="primary"
          :disabled="!activeSessionId || sending || !input.trim()"
          :loading="sending"
          @click="onSubmit"
        >
          发送
        </ElButton>
      </footer>
    </section>
  </div>
</template>

<style scoped>
.chat-view {
  height: 100%;
  display: flex;
  gap: 16px;
  min-height: 0;
}

.sessions {
  width: 240px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--dt-bg-card);
  border: 1px solid var(--dt-border);
  border-radius: 8px;
  padding: 12px;
  box-sizing: border-box;
  min-height: 0;
}

.sessions-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.sessions-title {
  font-weight: 600;
  color: var(--dt-text);
}

.sessions-list {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.session-item {
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  color: var(--dt-text);
}

.session-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.session-item:hover {
  background: var(--dt-bg-page);
}

.session-item.active {
  background: var(--dt-color-primary);
  color: #fff;
}

.session-item.active .session-time {
  color: rgba(255, 255, 255, 0.75);
}

/* 删除图标：默认次级色，悬停变红；激活项内为白色系 */
.session-delete {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  padding: 2px;
  border: none;
  background: transparent;
  color: var(--dt-text-secondary);
  cursor: pointer;
  border-radius: 4px;
  transition: color 0.2s;
}

.session-delete:hover {
  color: var(--el-color-danger);
}

.session-item.active .session-delete {
  color: rgba(255, 255, 255, 0.75);
}

.session-item.active .session-delete:hover {
  color: var(--el-color-danger);
}

.session-name {
  font-size: 14px;
}

.session-time {
  font-size: 12px;
  color: var(--dt-text-secondary);
}

.chat-main {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--dt-bg-card);
  border: 1px solid var(--dt-border);
  border-radius: 8px;
  overflow: hidden;
}

.messages {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 16px;
  box-sizing: border-box;
}

.empty {
  margin-top: 15%;
}

.message-row {
  display: flex;
  margin-bottom: 16px;
}

.message-row.user {
  justify-content: flex-end;
}

.message-row.assistant {
  justify-content: flex-start;
}

.bubble {
  max-width: 72%;
  padding: 10px 14px;
  border-radius: 10px;
  background: var(--dt-bg-page);
  border: 1px solid var(--dt-border);
  color: var(--dt-text);
  font-size: 14px;
  line-height: 1.7;
  word-break: break-word;
}

.message-row.user .bubble {
  background: var(--dt-color-primary);
  color: #fff;
  border: none;
}

.bubble.refused {
  border-left: 3px solid var(--el-color-warning);
}

.bubble.failed {
  border-left: 3px solid var(--el-color-danger);
}

.refuse-tag {
  display: block;
  margin-bottom: 6px;
}

.content {
  white-space: pre-wrap;
  word-break: break-word;
}

/* 生成中光标：闪烁提示正在输出，done 后随 streaming=false 消失 */
.cursor {
  display: inline-block;
  margin-left: 2px;
  color: var(--dt-color-primary);
  animation: cursor-blink 1s steps(1) infinite;
}

@keyframes cursor-blink {
  50% {
    opacity: 0;
  }
}

.typing {
  color: var(--dt-text-secondary);
}

.error-box {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.error-text {
  color: var(--el-color-danger);
  font-size: 13px;
}

.composer {
  flex-shrink: 0;
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 12px 16px;
  border-top: 1px solid var(--dt-border);
  box-sizing: border-box;
}

.composer :deep(.el-textarea) {
  flex: 1;
}
</style>
