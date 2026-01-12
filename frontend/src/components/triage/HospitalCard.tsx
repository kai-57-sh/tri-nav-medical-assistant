import { Hospital, Navigation, Phone, MapPin, Clock, Star } from 'lucide-react';
import { cn, formatDistance, getRouteModeLabel } from '@/lib/utils';
import type { Hospital as HospitalType, NavigationResult } from '@/lib/types';

interface HospitalCardProps {
  navigation: NavigationResult;
  className?: string;
  onNavigate?: (hospital: HospitalType) => void;
}

export function HospitalCard({ navigation, className, onNavigate }: HospitalCardProps) {
  const topHospitals = navigation.hospitals.slice(0, 3);
  const routePlan = navigation.route_plan;

  return (
    <div
      className={cn(
        'space-y-3 p-4 bg-card border border-border rounded-lg',
        className
      )}
    >
      {/* 头部 */}
      <div className="flex items-center gap-2 text-card-foreground">
        <Hospital className="w-5 h-5 text-blue-500" />
        <h3 className="font-semibold">推荐医院</h3>
        {navigation.radius_km !== undefined && (
          <span className="text-xs text-muted-foreground ml-auto">
            搜索范围 {navigation.radius_km}km
          </span>
        )}
      </div>

      {/* 医院列表 */}
      <div className="space-y-2">
        {topHospitals.map((hospital) => (
          <div
            key={hospital.rank}
            className="p-3 bg-muted/50 rounded-lg hover:bg-muted transition-colors"
          >
            <div className="flex items-start gap-3">
              {/* 排名 */}
              <div
                className={cn(
                  'w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold',
                  hospital.rank === 1
                    ? 'bg-yellow-500 text-white'
                    : hospital.rank === 2
                      ? 'bg-gray-400 text-white'
                      : 'bg-amber-600 text-white'
                )}
              >
                {hospital.rank}
              </div>

              {/* 医院信息 */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <h4 className="font-medium text-sm">{hospital.name}</h4>
                  {hospital.is_3a && (
                    <span className="px-1.5 py-0.5 bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400 text-xs rounded">
                      三甲
                    </span>
                  )}
                </div>

                <div className="mt-1 space-y-0.5 text-xs text-muted-foreground">
                  <div className="flex items-center gap-1">
                    <MapPin className="w-3 h-3" />
                    <span className="truncate">{hospital.address}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="flex items-center gap-1">
                      <Navigation className="w-3 h-3" />
                      {formatDistance(hospital.distance_m)}
                    </span>
                    {hospital.phone && (
                      <span className="flex items-center gap-1">
                        <Phone className="w-3 h-3" />
                        {hospital.phone}
                      </span>
                    )}
                  </div>
                  {hospital.reason && (
                    <p className="text-xs mt-1 text-foreground/70">
                      推荐: {hospital.reason}
                    </p>
                  )}
                </div>
              </div>

              {/* 导航按钮 */}
              {onNavigate && hospital.rank === 1 && (
                <button
                  onClick={() => onNavigate(hospital)}
                  className="px-3 py-1.5 bg-blue-500 hover:bg-blue-600 text-white text-xs rounded-lg transition-colors flex items-center gap-1"
                >
                  <Navigation className="w-3 h-3" />
                  导航
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* 路线规划 */}
      {routePlan && (
        <div className="pt-2 border-t border-border">
          <div className="flex items-center gap-2 text-sm">
            <Clock className="w-4 h-4 text-blue-500" />
            <span className="font-medium">预计到达时间:</span>
            <span className="text-blue-600 dark:text-blue-400">
              {routePlan.eta_min} 分钟
            </span>
            <span className="text-muted-foreground">
              ({getRouteModeLabel(routePlan.mode)})
            </span>
          </div>
          {routePlan.summary && (
            <p className="text-xs text-muted-foreground mt-1">{routePlan.summary}</p>
          )}
        </div>
      )}
    </div>
  );
}

// 单个医院卡片（用于显示在消息中）
interface SingleHospitalProps {
  hospital: HospitalType;
  className?: string;
  onNavigate?: (hospital: HospitalType) => void;
}

export function SingleHospitalCard({
  hospital,
  className,
  onNavigate,
}: SingleHospitalProps) {
  return (
    <div
      className={cn(
        'p-3 bg-muted/50 rounded-lg border border-border',
        className
      )}
    >
      <div className="flex items-start gap-3">
        {/* 三甲标记 */}
        {hospital.is_3a && (
          <div className="flex-shrink-0">
            <Star className="w-5 h-5 text-yellow-500 fill-yellow-500" />
          </div>
        )}

        {/* 医院信息 */}
        <div className="flex-1 min-w-0">
          <h4 className="font-medium text-sm">{hospital.name}</h4>
          <div className="mt-1 space-y-0.5 text-xs text-muted-foreground">
            <div className="flex items-center gap-1">
              <MapPin className="w-3 h-3" />
              <span className="truncate">{hospital.address}</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-1">
                <Navigation className="w-3 h-3" />
                {formatDistance(hospital.distance_m)}
              </span>
              {hospital.phone && (
                <span className="flex items-center gap-1">
                  <Phone className="w-3 h-3" />
                  {hospital.phone}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* 导航按钮 */}
        {onNavigate && (
          <button
            onClick={() => onNavigate(hospital)}
            className="px-3 py-1.5 bg-blue-500 hover:bg-blue-600 text-white text-xs rounded-lg transition-colors flex items-center gap-1"
          >
            <Navigation className="w-3 h-3" />
            导航
          </button>
        )}
      </div>
    </div>
  );
}
