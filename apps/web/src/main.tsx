import { QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider } from '@tanstack/react-router';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { queryClient } from './lib/query-client';
import { router } from './router';
import './styles.css';
import './features.css';
import './dashboard-editor.css';
import './monthly-review.css';
import './chart-studio.css';

const root = document.getElementById('root');
if (!root) throw new Error('Root element #root is missing.');

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
