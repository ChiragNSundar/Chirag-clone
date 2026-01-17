/**
 * Skeleton Loading Components
 * Animated placeholder components for loading states
 */
import clsx from 'clsx';

interface SkeletonProps {
    className?: string;
    animate?: boolean;
    style?: React.CSSProperties;
}

/**
 * Base skeleton component with shimmer animation
 */
export function Skeleton({ className, animate = true, style }: SkeletonProps) {
    return (
        <div
            className={clsx(
                'bg-zinc-800 rounded',
                animate && 'animate-pulse',
                className
            )}
            style={style}
        />
    );
}

/**
 * Skeleton for text lines
 */
export function SkeletonText({ lines = 3, className }: { lines?: number; className?: string }) {
    return (
        <div className={clsx('space-y-2', className)}>
            {Array.from({ length: lines }).map((_, i) => (
                <Skeleton
                    key={i}
                    className={clsx(
                        'h-4',
                        i === lines - 1 ? 'w-2/3' : 'w-full'
                    )}
                />
            ))}
        </div>
    );
}

/**
 * Skeleton for avatar/circular elements
 */
export function SkeletonAvatar({ size = 40 }: { size?: number }) {
    return (
        <Skeleton
            className="rounded-full"
            style={{ width: size, height: size }}
        />
    );
}

/**
 * Skeleton for chat messages
 */
export function SkeletonMessage({ isUser = false }: { isUser?: boolean }) {
    return (
        <div className={clsx('flex gap-3', isUser && 'flex-row-reverse')}>
            <SkeletonAvatar size={32} />
            <div className={clsx('flex-1 max-w-[70%]', isUser && 'flex justify-end')}>
                <Skeleton className="h-20 rounded-2xl" />
            </div>
        </div>
    );
}

/**
 * Skeleton for stat cards
 */
export function SkeletonStatCard() {
    return (
        <div className="glass-panel p-5 space-y-4">
            <div className="flex justify-between items-start">
                <Skeleton className="w-10 h-10 rounded-xl" />
                <Skeleton className="w-12 h-4" />
            </div>
            <div className="space-y-2">
                <Skeleton className="w-16 h-8" />
                <Skeleton className="w-24 h-4" />
            </div>
        </div>
    );
}

/**
 * Skeleton for chart
 */
export function SkeletonChart() {
    return (
        <div className="glass-panel p-6">
            <Skeleton className="w-32 h-6 mb-4" />
            <div className="flex items-end gap-2 h-48">
                {[40, 60, 80, 50, 70, 90, 55, 75].map((height, i) => (
                    <Skeleton
                        key={i}
                        className="flex-1 rounded-t"
                        style={{ height: `${height}%` }}
                    />
                ))}
            </div>
        </div>
    );
}

/**
 * Skeleton for dashboard grid
 */
export function SkeletonDashboard() {
    return (
        <div className="p-6 space-y-6">
            {/* Header */}
            <div className="flex items-center gap-3">
                <Skeleton className="w-8 h-8 rounded" />
                <div className="space-y-2">
                    <Skeleton className="w-48 h-6" />
                    <Skeleton className="w-64 h-4" />
                </div>
            </div>

            {/* Stats grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <SkeletonStatCard />
                <SkeletonStatCard />
                <SkeletonStatCard />
                <SkeletonStatCard />
            </div>

            {/* Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <SkeletonChart />
                <SkeletonChart />
                <SkeletonChart />
            </div>
        </div>
    );
}

/**
 * Skeleton for profile page
 */
export function SkeletonProfile() {
    return (
        <div className="p-6 space-y-6">
            {/* Header with avatar */}
            <div className="flex items-center gap-4">
                <SkeletonAvatar size={80} />
                <div className="space-y-2">
                    <Skeleton className="w-32 h-8" />
                    <Skeleton className="w-48 h-4" />
                </div>
            </div>

            {/* Content sections */}
            <div className="space-y-4">
                <Skeleton className="w-24 h-6" />
                <SkeletonText lines={4} />
            </div>

            <div className="space-y-4">
                <Skeleton className="w-20 h-6" />
                <div className="flex flex-wrap gap-2">
                    {Array.from({ length: 5 }).map((_, i) => (
                        <Skeleton key={i} className="w-20 h-8 rounded-full" />
                    ))}
                </div>
            </div>
        </div>
    );
}
