import { AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface DisclaimerProps {
  className?: string;
}

export function Disclaimer({ className }: DisclaimerProps) {
  return (
    <div
      className={cn(
        'flex items-start gap-2 p-3 bg-amber-50 dark:bg-amber-950/30',
        'border border-amber-200 dark:border-amber-800 rounded-lg',
        'text-amber-800 dark:text-amber-200 text-sm',
        className
      )}
    >
      <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
      <div className="space-y-1">
        <p className="font-semibold">医疗免责声明</p>
        <p className="text-xs opacity-90">
          本系统仅提供健康参考信息，不能替代专业医生的诊断和治疗。
          如有紧急情况，请立即拨打 120 或前往最近的医院急诊科。
        </p>
      </div>
    </div>
  );
}
