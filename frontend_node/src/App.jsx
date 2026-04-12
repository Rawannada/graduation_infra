import { useState } from "react";
import { FileProvider } from "./FileContext.jsx";
import "./Categories.css"
import "./App.css";
import Search from "./Search.jsx";
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
import Categories from "./Categories.jsx";
import UpdateProfile from "./UpdateProfile.jsx";
import CategoryFiles from "./CategoryFiles.jsx";
import { Navigate } from "react-router-dom";
import { DragTextProvider } from "./DragTextContext";
import ProtectedRoute from "./ProtectedRoute";
import AuthProvider from "./AuthContext";

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
    element: (
      <ProtectedRoute>
        <Layout />
      </ProtectedRoute>
    ),
    children: [
      { path: "", element: <Home /> },
      { path: "/home", element: <Home /> },
      { path: "/Categories", element: <Categories /> },
      { path: "/category-files/:categoryId/:categoryName", element: <CategoryFiles /> },
      { path: "/search", element: <Search /> },
      { path: "/Chat", element: <Chat /> },
    ],
  },
]);

function App() {
  return (
    <AuthProvider>

      <DragTextProvider>
        <FileProvider>
          <RouterProvider router={router} />
        </FileProvider>
      </DragTextProvider>
    </AuthProvider>
  );
}

export default App;
