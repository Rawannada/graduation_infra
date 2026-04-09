import { useState } from "react";
import { FileProvider } from "./FileContext.jsx";
import "./App.css";
import Chat from "./Chat.jsx";
import Layout from "./Layout";
import SideBar from "./SideBar.jsx";
import { createBrowserRouter } from "react-router-dom";
import { RouterProvider } from "react-router";
import Home from "./Home.jsx";
import ForgotPass from "./ForgotPass.jsx";
import SetPass from "./SetPass.jsx";
import SignUp from "./SignUp.jsx";
import Code from "./Code.jsx";
import PassCode from "./PassCode.jsx";
import AuthLayout from "./AuthLayout.jsx";
import PassSuccess from "./PassSuccess.jsx";
import Login from "./Login.jsx";
import UpdateProfile from "./UpdateProfile.jsx";
import { Navigate } from "react-router-dom";
const router = createBrowserRouter([
  {
    path: "/",
    element: <Navigate to="/Signup" />,
  },

  {
    path: "/signup",
    element: <SignUp />,
  },
  {
    path: "/login",
    element: <Login />,
  },
  {
    path: "/Code",
    element: <Code />,
  },
  // {
  //   path: "/Updateprofile",
  //   element: <UpdateProfile />,
  // },
  {
    path: "/Forgotpass",
    element: <ForgotPass />,
  },
  {
    path: "/PassCode",
    element: <PassCode />,
  },
  {
    path: "/Set",
    element: <SetPass />,
  },

  {
    path: "/Passsuccess",
    element: <PassSuccess />,
  },

  {
    path: "/Auth",
    element: <AuthLayout />,
  },
  {
    path: "",
    element: <Layout />,
    children: [
      { path: "", element: <Home /> },
      { path: "/home", element: <Home /> },
      // { path: "library", element: <Library /> },
      { path: "Chat", element: <Chat /> },
    ],
  },
]);

function App() {
  return (
    <FileProvider>
      <RouterProvider router={router} />
    </FileProvider>
  );
}

export default App;
