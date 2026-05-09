import React from "react";
import img from "./assets/Group9.jpg";
import AuthLayout from "./AuthLayout";
import e2 from "./assets/e2.png";
import e1 from "./assets/e1.png";
import { Formik, useFormik } from "formik";
import * as Yup from "yup";
import axios from "axios";
import toast from "react-hot-toast";
import AuthHeader from "./AuthHeader";
import { useNavigate } from "react-router-dom";
import Authcard from "./AuthCard";
// [7:56 pm, 27/03/2026] Sara Arafa: /^(?=.[A-Za-z])(?=.\d)[A-Za-z\d]{8,}$/
// [7:56 pm, 27/03/2026] Sara Arafa: regex password
import AuthForm from './AuthForm';
export default function Signup() {
  const navigate = useNavigate();

  let user = {
    userName: "",
    email: "",
    password: "",
    confirmPassword: "",
   
  };
  const [loading, setLoading] = React.useState(false);

  async function signupfun(values) {
    setLoading(true);
    try {
     const response= await axios.post("/api/users/signUp", {
       userName: values.userName,
        email: values.email,
        password: values.password,
        cPassword: values.confirmPassword,
      });
console.log({
  userName: values.userName,
  email: values.email,
  password: values.password,
  cPassword: values.confirmPassword,
});
toast.success("Account created successfully! 🎉");

console.log(response.data);
console.log(values);
      // نحفظ الإيميل للـ OTP
      localStorage.setItem("email", values.email);
        localStorage.setItem("accessToken", response.data.accessToken);
setTimeout(() => {
  navigate("/code");
}, 1500);    } catch (err) {
      setLoading(false);
      toast.error(err.response?.data?.message || "Signup failed");
    }
  }
  const signup = useFormik({
    initialValues: user,
    onSubmit: signupfun,
    validationSchema: Yup.object().shape({
    userName: Yup.string()
  .trim()
  .min(3, "Name must be at least 3 characters")
  .max(30, "Name must be at most 30 characters")
  .matches(/^[\u0600-\u06FFa-zA-Z\s]+$/, "Name can only contain letters")
  .required("Name is required"),
      email: Yup.string()
        .email("Invalid email address")
        .required("Email is required"),
      password: Yup.string()
    .matches(
      /^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,}$/, 
      "Password must be at least 8 characters, include letters and numbers"
    )
    .required("Password is required"),
      confirmPassword: Yup.string()
        .oneOf([Yup.ref("password"), null], "Passwords must match")
        .required("Confirm Password is required"),
    }),
  });

  return (
    <AuthLayout>
      <Authcard width="531px" height="484px "margintop="140px">
        <AuthHeader
          title="Create a workspace"
          subtitle={
            <>
              a workspace is your place to
              <br />
              organize, create and collaborate
            </>
          }
        />
        <form
          onSubmit={signup.handleSubmit}
          style={{
            width: "297px",
            height: "300px",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "8px",
          }}
        >
           <input
            name="userName"
            value={signup.values.userName}
            onChange={signup.handleChange}
            onBlur={signup.handleBlur}
            className="auth-input"
            type="text"
            placeholder="user name"
          />
          {signup.touched.userName && signup.errors.userName && (
            <div style={{ color: "red", fontSize: "12px" }}>
              {signup.errors.userName}
            </div>
          )}
          <input
            name="email"
            value={signup.values.email}
            onChange={signup.handleChange}
            onBlur={signup.handleBlur}
            className="auth-input"
            type="email"
            placeholder="email address"
          />
          {signup.touched.email && signup.errors.email && (
            <div style={{ color: "red", fontSize: "12px" }}>
              {signup.errors.email}
            </div>
          )}
         
          <input
            name="password"
            value={signup.values.password}
            onChange={signup.handleChange}
            onBlur={signup.handleBlur}
            className="auth-input"
            type="password"
            placeholder="password"
          />
          {signup.touched.password && signup.errors.password && (
            <div style={{ color: "red", fontSize: "12px" }}>
              {signup.errors.password}
            </div>
          )}
          <input
            name="confirmPassword"
            value={signup.values.confirmPassword}
            onChange={signup.handleChange}
            onBlur={signup.handleBlur}
            className="auth-input"
            type="password"
            placeholder="confirm password"
          />
          {signup.touched.confirmPassword && signup.errors.confirmPassword && (
            <div style={{ color: "red", fontSize: "12px" }}>
              {signup.errors.confirmPassword}
            </div>
          )}
          {/* <input style={{marginTop:"20px", width:"385px", height:"52px", borderRadius:"24px", border:"1px solid #CDCDCD", padding:"10px"}} type="text" placeholder='code'  /> */}

          <button type="submit" className="auth-button" disabled={loading}>
  {loading ? "Signing Up..." : "Sign Up"}
</button>
          <button
            onClick={() => navigate("/Login")}
            type="button"
            className="auth-btn"
          >
            Log In
          </button>
        </form>
      </Authcard>
    </AuthLayout>
  );
}
