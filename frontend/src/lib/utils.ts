import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

// Tailwind 类名合并工具
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// 生成 UUID
export function generateUUID(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

// 格式化时间
export function formatTime(date: Date): string {
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

// 分诊等级颜色映射
export function getTriageColor(level: string): string {
  const colors: Record<string, string> = {
    EMERGENCY: 'bg-red-500 text-white',
    URGENT: 'bg-orange-500 text-white',
    ROUTINE: 'bg-blue-500 text-white',
    SELF_CARE: 'bg-green-500 text-white',
  };
  return colors[level] || 'bg-gray-500 text-white';
}

// 分诊等级标签
export function getTriageLabel(level: string): string {
  const labels: Record<string, string> = {
    EMERGENCY: '紧急',
    URGENT: '急症',
    ROUTINE: '常规',
    SELF_CARE: '居家护理',
  };
  return labels[level] || level;
}

// 分诊等级图标
export function getTriageIcon(level: string): string {
  const icons: Record<string, string> = {
    EMERGENCY: '🚨',
    URGENT: '⚠️',
    ROUTINE: '🏥',
    SELF_CARE: '🏠',
  };
  return icons[level] || '📍';
}

// 路线模式标签
export function getRouteModeLabel(mode: string): string {
  const labels: Record<string, string> = {
    driving: '驾车',
    transit: '公共交通',
    walking: '步行',
  };
  return labels[mode] || mode;
}

// 格式化距离
export function formatDistance(meters: number): string {
  if (meters < 1000) {
    return `${meters.toFixed(0)}米`;
  }
  return `${(meters / 1000).toFixed(1)}公里`;
}
