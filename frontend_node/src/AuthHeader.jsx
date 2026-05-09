import React from "react";
import img from "./assets/sarsora.SVG";
export default function AuthHeader({ title, subtitle }) {
  return (
    <div style={{textAlign: "center", }}>
      <img
        style={{
          background: "transparent",
          width: "32px",
          height: "38px",
        }}
        src={img}
        alt="DeepGuardX"
      />
      <h1 className="jomolhari-regular" style={{ color: "#113567" }}>
        {title}
      </h1>
      <p style={{ color: "#707070" , whiteSpace: "pre-line"}}>{subtitle}</p>
    </div>
  );
}
