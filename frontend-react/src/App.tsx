import { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import { Dashboard } from './components/Dashboard';
import { ChatInterface } from './components/ChatInterface';
import { MemoryGraph } from './components/MemoryGraph';
import { ProfilePage } from './components/ProfilePage';
import { TrainingCenter } from './components/TrainingCenter';

function App() {
  const [isTrainingAuthenticated, setIsTrainingAuthenticated] = useState(false);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="chat" element={<ChatInterface />} />
          <Route path="memory" element={<MemoryGraph />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route
            path="training"
            element={
              <TrainingCenter
                isAuthenticated={isTrainingAuthenticated}
                onAuthenticate={() => setIsTrainingAuthenticated(true)}
              />
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
