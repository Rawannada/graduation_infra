import React from "react";
import img from "./assets/logo.jpg";
import { Formik, useFormik } from "formik";
import * as Yup from "yup";
import Authlayout from "./AuthLayout.jsx";
import Authcard from "./AuthCard.jsx";
import AuthHeader from "./AuthHeader.jsx";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import AuthForm from "./AuthForm";

export default function Login() {
    const [loading, setLoading] = React.useState(false);
  const navigate = useNavigate();
  let user = {
    email: "",
    password: "",
  };

  const login = useFormik({
    initialValues: user,
    validationSchema: Yup.object().shape({
      email: Yup.string()
        .email("Invalid email address")
        .required("Email is required"),
       password: Yup.string()
          .matches(
            /^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,}$/, 
            "Password must be at least 8 characters, include letters and numbers"
          )
          .required("Password is required"),
    }),
    onSubmit: async (values, { setSubmitting }) => {
      setLoading(true);
      try {
        const response = await axios.post(
          "http://localhost:3000/users/signIn",
          values,
        );
        // لو الدخول ناجح
        console.log(response.data);
        window.alert("Login successful!");
        localStorage.setItem("accessToken", response.data.accessToken);
          navigate("/home");
        // ممكن تخزن التوكن أو تعمل redirect
        // localStorage.setItem("token", response.data.token);
        // navigate("/dashboard");
      } catch (error) {
        console.error(error);
        window.alert(
          error.response?.data?.message ||
            "Login failed. Check your credentials.",
        );
      } finally {
        setSubmitting(false);
        setLoading(false);
      }
    },
  });

  return (
    <Authlayout>
      <Authcard width="531px" height="363px">
        <AuthHeader
          title="welcome to DeepGuardX"
          subtitle="login or create an account"
        />
        <form
          onSubmit={login.handleSubmit}
          className="auth-form"
        >
          <input
            name="email"
            value={login.values.email}
            onChange={login.handleChange}
            onBlur={login.handleBlur}
             className="auth-input"
            type="email"
            placeholder="email address"
          />
          {login.touched.email && login.errors.email && (
            <div style={{ color: "red", fontSize: "12px" }}>
              {login.errors.email}
            </div>
          )}
          <input
            name="password"
            value={login.values.password}
            onChange={login.handleChange}
            onBlur={login.handleBlur}
             className="auth-input"
            type="password"
            placeholder="password"
          />
          {login.touched.password && login.errors.password && (
            <div style={{ color: "red", fontSize: "12px" }}>
              {login.errors.password}
            </div>
          )}

          <div
           className="auth-links"
          >
            <span  onClick={() => navigate("/forgotpass")}>forgot password?</span>
            <span
              onClick={() => navigate("/signup")}
              style={{ cursor: "pointer", color: "#113567", fontWeight: "500" }}
            >
              sign up
            </span>
          </div>
          <button type="submit" className="auth-button" disabled={loading}>
  {loading ? "Logging in..." : "Log In"}
</button>
         
        </form>
      </Authcard>
      <p style={{ width: "588px", textAlign: "center", color: "#707070" }}>
        by continuing, you agree to ----- terms and privacy policy
      </p>
    </Authlayout>
  );
}
