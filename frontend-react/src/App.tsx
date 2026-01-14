import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import { Dashboard } from './components/Dashboard';
import { ChatInterface } from './components/ChatInterface';
import { MemoryGraph } from './components/MemoryGraph';
import { ProfilePage } from './components/ProfilePage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="chat" element={<ChatInterface />} />
          <Route path="memory" element={<MemoryGraph />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
