import type { ComponentType } from 'react';

// ============= Preload Helper =============

type LazyComponent = () => Promise<{ default: ComponentType<unknown> }>;

const preloadedComponents = new Set<LazyComponent>();

export function preloadComponent(lazyComponent: LazyComponent) {
    if (preloadedComponents.has(lazyComponent)) return;

    preloadedComponents.add(lazyComponent);
    lazyComponent();
}

export type { LazyComponent };
