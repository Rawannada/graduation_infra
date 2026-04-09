

import Authlayout from "./AuthLayout.jsx";
import Authcard from "./AuthCard.jsx";
import AuthHeader from "./AuthHeader.jsx";
import { useNavigate } from "react-router-dom";
import { useRef, useState } from "react";
import axios from "axios";

export default function Code() {
  
  const navigate = useNavigate();
  const [otp, setOtp] = useState(["", "", "", "", "", ""]);
  const inputsRef = useRef([]);
  async function confirmOTP() {
    const email = localStorage.getItem("email"); // email اللي اتخزن من signup
    const OTP = otp.join(""); // نجمع الستة أرقام مع بعض

    if (OTP.length < 6) {
      alert("Please enter complete OTP");
      return;
    }

    try {
     const response= await axios.post("http://localhost:3000/users/confirmCode", {
        email,
        OTP,
      });
      navigate("/Set");
    } catch (err) {
      alert(err.response?.data?.message || "Invalid OTP");
    }
  }
  const handleChange = (value, index) => {
    if (!/^\d?$/.test(value)) return;

    const newOtp = [...otp];
    newOtp[index] = value;
    setOtp(newOtp);

    if (value && index < 5) {
      inputsRef.current[index + 1].focus();
    }
  };

  const handleKeyDown = (e, index) => {
    if (e.key === "Backspace" && !otp[index] && index > 0) {
      inputsRef.current[index - 1].focus();
    }
  };

  return (
    <Authlayout>
    

      <Authcard  width="498px" height="345px" marginBottom="77px">
        <AuthHeader
          title="we emailed you a code"
          subtitle={`check your inbox at ${localStorage.getItem("femail")}`}
        />
        <form
          style={{
            width: "312px",
            height: "168px",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "13px",
          }}
        >
          <div style={{ display: "flex", gap: "4px" }}>
            {otp.map((digit, index) => (
              <input
                key={index}
                type="text"
                maxLength="1"
                value={digit}
                ref={(el) => (inputsRef.current[index] = el)}
                onChange={(e) => handleChange(e.target.value, index)}
                onKeyDown={(e) => handleKeyDown(e, index)}
                style={{
                  width: "43px",
                  height: "43px",
                  textAlign: "center",
                  fontSize: "20px",
                  borderRadius: "10px",
                  backgroundColor: "#E7E7E7",
                  border: "none",
                }}
              />
            ))}
          </div>

          <button
            onClick={confirmOTP}
            type="button"
            className="auth-button"
          >
            continue
          </button>
          <div
            style={{
              width: "296px",
              display: "flex",
              flexDirection: "row",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "16px",
            }}
          >
            <button
              onClick={() => window.open("https://mail.google.com", "_blank")}
                            className="mini-btn"

            >
              open gmail
            </button>
            <button
              onClick={() => window.open("https://outlook.live.com", "_blank")}
              className="mini-btn"
            >
              open outlook
            </button>
          </div>
        </form>
      </Authcard>
      <p style={{ width: "588px", textAlign: "center", color: "#707070" }}>
        continuing as <br/>
        email22@gmail.com<br/>
        log in with another email here




      </p>
    
    </Authlayout>
  );
}
