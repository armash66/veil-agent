import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App.tsx';
import { EvaluationRubricProvider } from './context/EvaluationRubricContext.tsx';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <EvaluationRubricProvider>
      <App />
    </EvaluationRubricProvider>
  </StrictMode>,
);
