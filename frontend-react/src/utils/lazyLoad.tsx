import { Suspense, lazy, type ComponentType } from 'react';

// ============= Lazy Loaded Components =============
// All components use named exports, so we map them to default

// Dashboard - named export
export const LazyDashboard = lazy(() =>
    import('../components/Dashboard').then(m => ({ default: m.Dashboard }))
);

// Training Center - named export
export const LazyTrainingCenter = lazy(() =>
    import('../components/TrainingCenter').then(m => ({ default: m.TrainingCenter }))
);

// Profile Page - named export
export const LazyProfilePage = lazy(() =>
    import('../components/ProfilePage').then(m => ({ default: m.ProfilePage }))
);

// Autopilot Page - named export
export const LazyAutopilotPage = lazy(() =>
    import('../components/AutopilotPage').then(m => ({ default: m.AutopilotPage }))
);

// Memory Graph - named export
export const LazyMemoryGraph = lazy(() =>
    import('../components/MemoryGraph').then(m => ({ default: m.MemoryGraph }))
);

// Voice Chat - named export (function)
export const LazyVoiceChat = lazy(() =>
    import('../components/VoiceChat').then(m => ({ default: m.VoiceChat }))
);

// ============= Loading Fallbacks =============

export function DashboardFallback() {
    return (
        <div className="p-6 space-y-6 animate-pulse">
            <div className="h-8 w-48 bg-zinc-800 rounded" />
            <div className="grid grid-cols-4 gap-4">
                {[...Array(4)].map((_, i) => (
                    <div key={i} className="h-24 bg-zinc-800 rounded-xl" />
                ))}
            </div>
            <div className="grid grid-cols-3 gap-4">
                {[...Array(3)].map((_, i) => (
                    <div key={i} className="h-48 bg-zinc-800 rounded-xl" />
                ))}
            </div>
        </div>
    );
}

export function PageFallback() {
    return (
        <div className="p-6 flex items-center justify-center min-h-[400px]">
            <div className="text-center">
                <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                <p className="text-zinc-400">Loading...</p>
            </div>
        </div>
    );
}

// ============= Wrapper Component =============

interface LazyWrapperProps {
    children: React.ReactNode;
    fallback?: React.ReactNode;
}

export function LazyWrapper({ children, fallback }: LazyWrapperProps) {
    return (
        <Suspense fallback={fallback ?? <PageFallback />}>
            {children}
        </Suspense>
    );
}

// ============= Route Config Helper =============

export function createLazyRoute<P extends object>(
    Component: ComponentType<P>,
    fallback?: React.ReactNode
) {
    return function LazyRoute(props: P) {
        return (
            <Suspense fallback={fallback ?? <PageFallback />}>
                <Component {...props} />
            </Suspense>
        );
    };
}

// ============= Preload Helper =============

type LazyComponent = () => Promise<{ default: ComponentType<unknown> }>;

const preloadedComponents = new Set<LazyComponent>();

export function preloadComponent(lazyComponent: LazyComponent) {
    if (preloadedComponents.has(lazyComponent)) return;

    preloadedComponents.add(lazyComponent);
    lazyComponent();
}

// Preload on hover
export function withPreload<P extends object>(
    LazyComponent: React.LazyExoticComponent<ComponentType<P>>,
    loader: LazyComponent
) {
    return function PreloadableComponent(props: P) {
        return (
            <div onMouseEnter={() => preloadComponent(loader)}>
                <LazyComponent {...props} />
            </div>
        );
    };
}

