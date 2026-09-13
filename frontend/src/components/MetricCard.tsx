/**
 * Metric Card Component
 *
 * Displays a single metric with icon, label, and value
 */
import { LucideIcon } from 'lucide-react';

interface MetricCardProps {
  icon: LucideIcon;
  label: string;
  value: string | number;
  subtitle?: string;
  trend?: {
    value: number;
    isPositive: boolean;
  };
  color?: 'blue' | 'green' | 'purple' | 'orange' | 'red';
}

const colorClasses = {
  blue: {
    bg: 'bg-gradient-to-br from-blue-500 to-blue-600',
    text: 'text-blue-600',
    ring: 'ring-blue-500/20',
    glow: 'shadow-blue-500/20',
  },
  green: {
    bg: 'bg-gradient-to-br from-green-500 to-emerald-600',
    text: 'text-green-600',
    ring: 'ring-green-500/20',
    glow: 'shadow-green-500/20',
  },
  purple: {
    bg: 'bg-gradient-to-br from-purple-500 to-violet-600',
    text: 'text-purple-600',
    ring: 'ring-purple-500/20',
    glow: 'shadow-purple-500/20',
  },
  orange: {
    bg: 'bg-gradient-to-br from-orange-500 to-amber-600',
    text: 'text-orange-600',
    ring: 'ring-orange-500/20',
    glow: 'shadow-orange-500/20',
  },
  red: {
    bg: 'bg-gradient-to-br from-red-500 to-rose-600',
    text: 'text-red-600',
    ring: 'ring-red-500/20',
    glow: 'shadow-red-500/20',
  },
};

export default function MetricCard({
  icon: Icon,
  label,
  value,
  subtitle,
  trend,
  color = 'blue',
}: MetricCardProps) {
  const colors = colorClasses[color];

  return (
    <div className="group relative bg-white rounded-xl shadow-sm border border-gray-100 p-6 hover:shadow-xl hover:shadow-gray-200/50 hover:-translate-y-1 transition-all duration-300">
      {/* Gradient overlay on hover */}
      <div className={`absolute inset-0 rounded-xl bg-gradient-to-br ${colors.ring} opacity-0 group-hover:opacity-100 transition-opacity duration-300`}></div>

      <div className="relative">
        <div className="flex items-center justify-between mb-4">
          <div className={`p-3 rounded-xl ${colors.bg} shadow-lg ${colors.glow} transform group-hover:scale-110 transition-transform duration-300`}>
            <Icon className="w-6 h-6 text-white" />
          </div>
          {trend && (
            <span
              className={`text-sm font-semibold px-2 py-1 rounded-full ${
                trend.isPositive ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
              }`}
            >
              {trend.isPositive ? '↑' : '↓'} {Math.abs(trend.value)}%
            </span>
          )}
        </div>

        <div>
          <p className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">{label}</p>
          <p className={`text-4xl font-bold ${colors.text} mb-1`}>{value}</p>
          {subtitle && <p className="text-sm text-gray-600 font-medium">{subtitle}</p>}
        </div>
      </div>
    </div>
  );
}
