import React from "react";
import img from "./assets/Group9.jpg";
import bg1 from "./assets/bg1.png";
import { useNavigate } from "react-router-dom";
import { Check } from "lucide-react";
import Authlayout from "./AuthLayout.jsx";
import Authcard from "./AuthCard.jsx";
import AuthHeader from "./AuthHeader.jsx";
export default function Success() {
  const navigate = useNavigate();

  return (
    <Authlayout>
      <Authcard width="542px" height="353px ">
        <img
          style={{
            background: "transparent",
            width: "33px",
            height: "39px",
          }}
          src={img}
          alt="DeepGuardX"
        />
        <h1 className="jomolhari-regular" style={{ color: "#113567" }}>
          password reset successfully
        </h1>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: "111px",
            height: "111px",
            textAlign: "center",
            borderRadius: "50%",
            border: "8px solid #113567",
            backgroundColor: "transparent",
          }}
        >
          <Check style={{ width: "70px", height: "70px", color: "#113567" }} />
        </div>
        <p style={{ textAlign: "center", color: "#707070", marginTop: "20px" }}>
          you can log in with your new password
        </p>

        <button onClick={() => navigate("/login")} className="auth-button">
          Log In
        </button>
      </Authcard>
    </Authlayout>
  );
}
