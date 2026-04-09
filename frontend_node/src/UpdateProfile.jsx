import React, { useState } from "react";
import img from "./assets/Group9.jpg";
import Authlayout from "./AuthLayout.jsx";
import Authcard from "./AuthCard.jsx";
import AuthHeader from "./AuthHeader.jsx";

import { Formik, useFormik } from "formik";
import * as Yup from "yup";
import { useNavigate } from "react-router-dom";
import { Upload } from "lucide-react";
import axios from "axios";


export default function Updateprofile() {
 async function handleContinue(values) {
  const { fullName } =values;

  // if (!fullName && !image) {
  //   alert("Please provide your name or upload an image");
  //   return;
  // }

  const formData = new FormData();
  if (fullName) formData.append("fullName", fullName);
  // if (workspace) formData.append("workspace", workspace);
  if (image) formData.append("image", image);

  try {
    const token = localStorage.getItem("accessToken"); //
    if (!accessToken) {
      alert("You are not logged in");
      return;
    } // توكن من signup/confirmEmail
   const res = await axios.post("http://localhost:5000/users/updateProfile", formData, {
      headers: {
        // "Content-Type": "multipart/form-data",
        Authorization: `Bearer ${token}`,
      },
    });
 console.log(res.data);
    navigate("/home"); // بعد ما ينجح
  } catch (err) {
    alert(err.response?.data?.message || "Update failed");
  }
}

  const [image, setImage] = useState(null);

  const navigate = useNavigate();
  let user = {
    fullName: "",
    // workspace: "",
   
  };
  
  const login = useFormik({
    initialValues: user,
    onSubmit: handleContinue,
    validationSchema: Yup.object().shape({
      fullName: Yup.string().required("Name is required"),
      // workspace: Yup.string().required("Workspace is required"),
      
    }),
  });

  return (
    <Authlayout>
   <Authcard width="504px" height="564px" margintop="117px" marginBottom="0">
      <input
        type="file"
        accept="image/*"
        style={{ display: "none" }}
        id="fileInput"
        onChange={(e) => setImage(e.target.files[0])}
      />
      

      
       <AuthHeader
        title="Create a workspace"
  subtitle={<>a workspace is your place to<br/>organize, create and collaborate</>}/>
        <div
          style={{
            width: "95px",
            height: "95px",
            background: "#ECEBEB",
            borderRadius: "50%",
          }}

        >
           {image && (
    <img
      src={URL.createObjectURL(image)}
      alt="preview"
      style={{ width: "100%", height: "100%", objectFit: "cover" }}
    />
  )}
        </div>
        <div
          onClick={() => document.getElementById("fileInput").click()}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "4px",
            color: "#707070",
            marginTop: "10px",
          }}
        >
          <Upload color="#707070" size={18} />
          <span> upload image</span>
        </div>
        <form
          onSubmit={login.handleSubmit}
          style={{
            marginTop: "20px",
            width: "315px",
            height: "152px",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "8px",
          }}
        >
          <input
            name="fullName"
            value={login.values.fullName}
            onChange={login.handleChange}
            onBlur={login.handleBlur}
                      className="auth-input"

            type="text"
            placeholder="name"
          />
          {login.touched.fullName && login.errors.fullName && (
            <div style={{ color: "red", fontSize: "12px" }}>
              {login.errors.fullName}
            </div>
          )}

          {/* <input
            name="workspace"
            value={login.values.workspace}
            onChange={login.handleChange}
            onBlur={login.handleBlur}
                                  className="auth-input"

            type="text"
            placeholder="deepGuardX.com/ name"
          /> */}
          {/* {login.touched.workspace && login.errors.workspace && (
            <div style={{ color: "red", fontSize: "12px" }}>
              {login.errors.workspace}
            </div>
          )} */}

          <button
           
            type="submit"
                                  className="auth-button"

          >
            Continue
          </button>
        </form>
      
       <p style={{ width: "588px", textAlign: "center", color: "#707070",marginTop:"10px" }}>
        continuing as <br/>
        email22@gmail.com<br/>
        not you? sign out




      </p>
</Authcard>
    </Authlayout>
  );
}
