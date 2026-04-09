
import e1 from "./assets/e1.png";
import e2 from "./assets/e2.png";
export default function AuthLayout({ children }) {
  return (
    <div
      style={{
        position: "relative",
        minHeight: "100vh",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
                 
                           


        // justifyContent: "center",
      }}
    >
      <img
        src={e1}
        style={{ position: "absolute", top: 0, right: 0, zIndex: -1 }}
      />

      <img
        src={e2}
        style={{ position: "absolute", bottom: 0, left: 0, zIndex: -1 }}
      />

      {children}
    </div>
  );
}