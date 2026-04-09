import React from "react";

export default function Authcard({ children, width = "400px", height = "auto" , marginBottom = "98px" , margintop = "170px"}) {
  return (
    <div
      style={{
        // background: "green",
        width: width,
        height: height,
        marginTop: margintop,
        marginBottom: marginBottom,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {children}
    </div>
  );
}
