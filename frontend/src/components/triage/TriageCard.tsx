import {
  AlertTriangle,
  CheckCircle,
  Activity,
  Home,
  Stethoscope,
  AlertOctagon,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { cn, getTriageIcon, getTriageLabel } from '@/lib/utils';
import type { TriageResponse } from '@/lib/types';
import { useState } from 'react';

interface TriageCardProps {
  data: TriageResponse;
  className?: string;
}

export function TriageCard({ data, className }: TriageCardProps) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(['triage', 'departments'])
  );

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(section)) {
        next.delete(section);
      } else {
        next.add(section);
      }
      return next;
    });
  };

  const isExpanded = (section: string) => expandedSections.has(section);

  if (!data.triage_level) {
    return null;
  }

  const triageConfig = {
    EMERGENCY: {
      icon: AlertOctagon,
      color: 'bg-red-500',
      bgColor: 'bg-red-50 dark:bg-red-950/30',
      borderColor: 'border-red-200 dark:border-red-800',
    },
    URGENT: {
      icon: AlertTriangle,
      color: 'bg-orange-500',
      bgColor: 'bg-orange-50 dark:bg-orange-950/30',
      borderColor: 'border-orange-200 dark:border-orange-800',
    },
    ROUTINE: {
      icon: Activity,
      color: 'bg-blue-500',
      bgColor: 'bg-blue-50 dark:bg-blue-950/30',
      borderColor: 'border-blue-200 dark:border-blue-800',
    },
    SELF_CARE: {
      icon: Home,
      color: 'bg-green-500',
      bgColor: 'bg-green-50 dark:bg-green-950/30',
      borderColor: 'border-green-200 dark:border-green-800',
    },
  };

  const config = triageConfig[data.triage_level] || triageConfig.ROUTINE;

  // 可折叠区块组件
  const CollapsibleSection = ({
    id,
    title,
    icon: SectionIcon,
    children,
  }: {
    id: string;
    title: string;
    icon: React.ComponentType<{ className?: string }>;
    children: React.ReactNode;
  }) => {
    const expanded = isExpanded(id);
    return (
      <div className="border-b border-border last:border-0">
        <button
          onClick={() => toggleSection(id)}
          className="w-full flex items-center justify-between p-3 hover:bg-muted/50 transition-colors"
        >
          <span className="flex items-center gap-2 text-sm font-medium">
            <SectionIcon className="w-4 h-4 text-muted-foreground" />
            {title}
          </span>
          {expanded ? (
            <ChevronUp className="w-4 h-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="w-4 h-4 text-muted-foreground" />
          )}
        </button>
        {expanded && <div className="px-3 pb-3 text-sm">{children}</div>}
      </div>
    );
  };

  return (
    <div
      className={cn(
        'overflow-hidden rounded-lg border',
        config.bgColor,
        config.borderColor,
        className
      )}
    >
      {/* 分诊等级头部 */}
      <div className="p-4">
        <div className="flex items-center gap-3">
          <div
            className={cn(
              'w-12 h-12 rounded-full flex items-center justify-center text-white text-2xl',
              config.color
            )}
          >
            {getTriageIcon(data.triage_level)}
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  'px-2 py-0.5 rounded text-white text-xs font-semibold',
                  config.color
                )}
              >
                {getTriageLabel(data.triage_level)}
              </span>
              {data.triage_source && (
                <span className="text-xs text-muted-foreground">
                  评估方式: {data.triage_source === 'llm' ? 'AI分析' : data.triage_source === 'rule_engine' ? '规则引擎' : '综合评估'}
                </span>
              )}
            </div>
            {data.triage_reason && (
              <p className="text-sm mt-1 text-foreground/80">
                {data.triage_reason}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* 详细信息区块 */}
      <div className="bg-background/50 backdrop-blur-sm">
        {/* 推荐科室 */}
        {data.recommended_departments.length > 0 && (
          <CollapsibleSection
            id="departments"
            title="推荐科室"
            icon={Stethoscope}
          >
            <div className="flex flex-wrap gap-2">
              {data.recommended_departments.map((dept, idx) => (
                <span
                  key={idx}
                  className="px-2 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded text-sm"
                >
                  {dept}
                </span>
              ))}
            </div>
          </CollapsibleSection>
        )}

        {/* 可能病因 */}
        {data.possible_causes.length > 0 && (
          <CollapsibleSection id="causes" title="可能病因" icon={Activity}>
            <ul className="space-y-1">
              {data.possible_causes.map((cause, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <span className="text-muted-foreground">•</span>
                  <span>{cause}</span>
                </li>
              ))}
            </ul>
          </CollapsibleSection>
        )}

        {/* 自我护理建议 */}
        {data.self_care_tips.length > 0 && (
          <CollapsibleSection id="tips" title="护理建议" icon={CheckCircle}>
            <ul className="space-y-1">
              {data.self_care_tips.map((tip, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />
                  <span>{tip}</span>
                </li>
              ))}
            </ul>
          </CollapsibleSection>
        )}

        {/* 警示信号 */}
        {data.red_flags.length > 0 && (
          <CollapsibleSection
            id="flags"
            title="警示信号"
            icon={AlertTriangle}
          >
            <ul className="space-y-1">
              {data.red_flags.map((flag, idx) => (
                <li
                  key={idx}
                  className="flex items-start gap-2 text-red-600 dark:text-red-400"
                >
                  <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  <span>{flag}</span>
                </li>
              ))}
            </ul>
          </CollapsibleSection>
        )}

        {/* 天气预警 */}
        {data.weather_alert && (
          <CollapsibleSection
            id="weather"
            title="天气提醒"
            icon={Activity}
          >
            <div className="p-2 bg-blue-50 dark:bg-blue-950/30 rounded">
              <p className="text-sm">
                <span className="font-medium">天气: </span>
                {data.weather_alert.condition}
              </p>
              <p className="text-sm">
                <span className="font-medium">气温: </span>
                {data.weather_alert.temperature_c}°C
              </p>
              {data.weather_alert.advice && (
                <p className="text-sm mt-1 text-muted-foreground">
                  {data.weather_alert.advice}
                </p>
              )}
            </div>
          </CollapsibleSection>
        )}

        {/* 视觉发现 */}
        {data.visual_findings && data.visual_findings.observations.length > 0 && (
          <CollapsibleSection
            id="visual"
            title="图片分析"
            icon={Activity}
          >
            <div className="space-y-1">
              {data.visual_findings.observations.map((obs, idx) => (
                <p key={idx} className="text-sm text-muted-foreground">
                  • {obs}
                </p>
              ))}
              <p className="text-xs text-muted-foreground mt-2">
                置信度: {(data.visual_findings.confidence * 100).toFixed(0)}%
              </p>
            </div>
          </CollapsibleSection>
        )}

        {/* 证据链 */}
        {data.evidence && data.evidence.length > 0 && (
          <CollapsibleSection
            id="evidence"
            title="分析依据"
            icon={CheckCircle}
          >
            <div className="space-y-2">
              {data.evidence.map((ev, idx) => (
                <div
                  key={idx}
                  className="p-2 bg-muted/50 rounded text-sm"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium">{ev.source_description}</span>
                    <span className="text-xs text-muted-foreground">
                      {(ev.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  <p className="text-muted-foreground">{ev.content}</p>
                </div>
              ))}
            </div>
          </CollapsibleSection>
        )}
      </div>

      {/* 免责声明 */}
      {data.disclaimer && (
        <div className="p-3 bg-amber-50 dark:bg-amber-950/30 border-t border-amber-200 dark:border-amber-800">
          <p className="text-xs text-amber-800 dark:text-amber-200">
            ⚠️ {data.disclaimer}
          </p>
        </div>
      )}
    </div>
  );
}
