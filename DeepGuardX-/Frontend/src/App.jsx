import { useState } from 'react'




import './App.css'
import Chat from './Chat.jsx';
import Layout from './Layout';
import Sidebar from './Sidebar.jsx';
import { createBrowserRouter } from 'react-router-dom';
import { RouterProvider } from 'react-router';
import Home from './Home.jsx';
import Library from './Library.jsx';

const router = createBrowserRouter([
  {
    path: "", element: <Layout />, children: [
      { path: "", element: <Home /> },
      { path: "/home", element: <Home /> },
      { path: "library", element: <Library /> },
      { path: "Chat", element: <Chat /> },

    ]

  }

]);

function App() {


  return (


    <RouterProvider router={router} />

  )
}

export default App
