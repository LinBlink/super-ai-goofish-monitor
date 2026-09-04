import { http } from '@/lib/http'
import type {
  DashboardDipTask,
  DashboardSnapshot,
  DashboardTaskSummary,
} from '@/types/dashboard.d.ts'

export async function getDashboardSummary(): Promise<DashboardSnapshot> {
  return await http('/api/dashboard/summary')
}

export type DashboardStreamEvent =
  | { type: 'task_summary'; data: DashboardTaskSummary }
  | { type: 'declining_dip_task'; data: DashboardDipTask }
  | { type: 'complete'; data: DashboardSnapshot }
  | { type: 'error'; message: string }

export class DashboardStreamUnavailableError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'DashboardStreamUnavailableError'
  }
}

export async function streamDashboardSummary(
  onEvent: (event: DashboardStreamEvent) => void | Promise<void>,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch('/api/dashboard/summary/stream', { signal })
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }
  const contentType = response.headers.get('content-type') || ''
  if (!contentType.toLowerCase().includes('application/x-ndjson')) {
    await response.body?.cancel()
    throw new DashboardStreamUnavailableError(
      `概览流式接口返回了不支持的内容类型: ${contentType || 'unknown'}`,
    )
  }
  if (!response.body) {
    throw new DashboardStreamUnavailableError('浏览器不支持流式响应')
  }

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    buffer += value || ''
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) {
      if (line.trim()) await onEvent(JSON.parse(line) as DashboardStreamEvent)
    }
    if (done) break
  }
  if (buffer.trim()) await onEvent(JSON.parse(buffer) as DashboardStreamEvent)
}
