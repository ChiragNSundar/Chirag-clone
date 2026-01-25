import { useState } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import { Layout } from './components/Layout';
// Replace direct imports with Lazy components
import {
  LazyDashboard,
  LazyTrainingCenter,
  LazyMemoryGraph,
  LazyProfilePage,
  LazyAutopilotPage,
  LazyWrapper
} from './utils/lazyLoad';
// ChatInterface remains eager loaded as it's the main entry point often accessed
import { ChatInterface } from './components/ChatInterface';
import { ErrorBoundary } from './components/ErrorBoundary';

function App() {
  const [isTrainingAuthenticated, setIsTrainingAuthenticated] = useState(false);
  const location = useLocation();

  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route path="/" element={<Layout />}>
          <Route index element={
            <LazyWrapper>
              <LazyDashboard />
            </LazyWrapper>
          } />

          {/* ChatInterface is eager loaded for speed */}
          <Route path="chat" element={
            <ErrorBoundary>
              <ChatInterface />
            </ErrorBoundary>
          } />

          <Route path="memory" element={
            <LazyWrapper>
              <LazyMemoryGraph />
            </LazyWrapper>
          } />

          <Route path="profile" element={
            <LazyWrapper>
              <LazyProfilePage />
            </LazyWrapper>
          } />

          <Route
            path="training"
            element={
              <LazyWrapper>
                <ErrorBoundary>
                  <LazyTrainingCenter
                    isAuthenticated={isTrainingAuthenticated}
                    onAuthenticate={() => setIsTrainingAuthenticated(true)}
                  />
                </ErrorBoundary>
              </LazyWrapper>
            }
          />

          <Route path="autopilot" element={
            <LazyWrapper>
              <LazyAutopilotPage />
            </LazyWrapper>
          } />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </AnimatePresence>
  );
}

export default App;
