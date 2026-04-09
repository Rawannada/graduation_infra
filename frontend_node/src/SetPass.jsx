import React from "react";
import Authlayout from "./AuthLayout.jsx";
import Authcard from "./AuthCard.jsx";
import AuthHeader from "./AuthHeader.jsx";
import axios from "axios";
import { useFormik } from "formik";
import * as Yup from "yup";
import { useNavigate } from "react-router-dom";

export default function Setpass() {
  const navigate = useNavigate();
  let newpass = {
    password: "",
    confirmPassword: "",
  };
 
const login = useFormik({
  initialValues: newpass,
  validationSchema: Yup.object({
    password: Yup.string()
      .min(8, "Password must be at least 8 characters")
      .required("Password is required"),
    confirmPassword: Yup.string()
      .oneOf([Yup.ref("password"), null], "Passwords must match")
      .required("Confirm Password is required"),
  }),
  onSubmit: async (values) => {
    const email = localStorage.getItem("email"); // البريد المخزن من Forgot Password / OTP
    if (!email) {
      alert("Email not found, please restart the password reset process");
      navigate("/forgot-password");
      return;
    }

    try {
      const response = await axios.patch(
        "http://localhost:3000/users/resetPassword",
        {
          email,
          password: values.password,
          cPassword: values.confirmPassword,
        }
      );

      alert(response.data.message || "Password updated successfully");
      navigate("/Passsuccess"); // صفحة نجاح تغيير الباسورد
    } catch (err) {
      console.error(err);
      alert(err.response?.data?.message || "Something went wrong. Please try again");
    }
  },
});

  return (
    <Authlayout>
      <Authcard width="546px" height="332px">
        <AuthHeader
          title="Set new password"
          subtitle="Your new password must be different from previous used passwords"
        />
        <form
          onSubmit={login.handleSubmit}
          style={{
            width: "388px",
            height: "255px",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "8px",
          }}
        >
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

          <input
            name="confirmPassword"
            value={login.values.confirmPassword}
            onChange={login.handleChange}
            onBlur={login.handleBlur}
            className="auth-input"
            type="password"
            placeholder="confirm password"
          />
          {login.touched.confirmPassword && login.errors.confirmPassword && (
            <div style={{ color: "red", fontSize: "12px" }}>
              {login.errors.confirmPassword}
            </div>
          )}
          <button type="submit" className="auth-button">
            Reset password
          </button>
        </form>
      </Authcard>
     
    </Authlayout>
  );
}
