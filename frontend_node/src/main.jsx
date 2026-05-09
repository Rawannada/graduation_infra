// import { StrictMode } from 'react'
// import { createRoot } from 'react-dom/client'
// import 'bootstrap/dist/css/bootstrap.min.css'
// // import 'bootstrap/dist/css/bootstrap.min.css';  // عشان الشكل
// import 'bootstrap/dist/js/bootstrap.bundle.min.js'; // عشان الوظايف

// import './index.css'
// import App from './App.jsx'

// createRoot(document.getElementById('root')).render(

//     <App />
    

// )
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import 'bootstrap/dist/css/bootstrap.min.css'
import 'bootstrap/dist/js/bootstrap.bundle.min.js'

import './index.css'
import App from './App.jsx'

const queryClient = new QueryClient()

createRoot(document.getElementById('root')).render(
  <QueryClientProvider client={queryClient}>
    <App />
  </QueryClientProvider>
)