import React from "react";
import img from "./assets/Group9.jpg";
import Authlayout from "./AuthLayout.jsx";
import Authcard from "./AuthCard.jsx";
import AuthHeader from "./AuthHeader.jsx";
import { Formik, useFormik } from "formik";
import * as Yup from "yup";
import { useNavigate } from "react-router-dom";
import axios from "axios";
export default function Forgotpass() {
  const navigate = useNavigate();
  let user = {
    email: "",
  };
  // function Sendcode() {

  //   window.alert(
    //     `Email: ${login.values.email}\nA code has been sent to your email address to reset your password.`,
    //   );
    // }
    const login = useFormik({
    initialValues: user,
    onSubmit: async (values) => {
  try {
    const response = await axios.patch("http://localhost:3000/users/forgetPassword", {
      email: values.email,
    });
    localStorage.setItem("email", values.email);
    if (response.data.message) {
      alert(response.data.message); // OTP Sent to email
      navigate("/PassCode"); // redirect لصفحة تغيير الباسورد
    }
  } catch (error) {
    console.error(error);
    alert(
      error.response?.data?.message || "Something went wrong. Please try again."
    );
  }
},
    // onSubmit: Sendcode,
    validationSchema: Yup.object().shape({
      email: Yup.string()
        .email("Invalid email address")
        .required("Email is required"),
    
    }),
  });

  return (
    <Authlayout>
    
      

      <Authcard width="623px " hight="350px"  marginBottom="109px">
          <AuthHeader
            title="forgot password?"
            subtitle="enter your email address to receive a code and reset your password"
          />
        <form
          onSubmit={login.handleSubmit}
          style={{
            width: "345px",
            height: "168px",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "8px",
          }}
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
          
         
          <button
            type="submit"
            className="auth-button"
          >
            Send Code
          </button>
          <button
          onClick={()=>navigate("/login")}
            type="button"
           className="auth-btn"
          >
            back to login
          </button>
        </form>
      </Authcard>
      <p style={{ width: "588px", textAlign: "center", color: "#707070" }}>
        by continuing, you agree to ----- terms and privacy policy
      </p>
    
    </Authlayout>
  );
}
