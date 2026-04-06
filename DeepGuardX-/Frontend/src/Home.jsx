import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlignCenter, PanelLeft, CircleX } from "lucide-react";
import Lottie from "lottie-react";
import water from "./assets/water.json";

import {
  CloudUpload,
  FileUp,
  FolderOpen,
  Upload,
  ShieldCheck,
  ShieldAlert,
} from "lucide-react";
import Chat from "./Chat";
export default function Home() {
  const navigate = useNavigate();
  const [scanned, setscanned] = useState(false);
  const inputRef = useRef(null);
  const [showbtns, setShowbtns] = useState(false);
  const [dragtext, setDragtext] = useState(
    "Drag & drop your files here or click to browse"
  );
  const [file, setFile] = useState(null);
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isSafe, setisSafe] = useState(null);
  const [boxstate, setboxstate] = useState();
  const [sessionId, setSessionId] = useState(null);
  const [riskLevel, setRiskLevel] = useState(null);
  const [summary, setSummary] = useState(null);
  const [report, setReport] = useState(null);
  const [showReport, setShowReport] = useState(false);

  //   button handlers
  const handleCancel = (e) => {
    e.stopPropagation();
    setFile(null);
    setisSafe(null);
    setscanned(false);
    setFiles([]);
    setShowbtns(false);
    setDragtext("Drag & drop your files here or click to browse");

    // إعادة تهيئة الـ input
    if (inputثسRef.current) {
      inputRef.current.value = null;
    }
  };

  // const handleScan = (e) => {
  //   e.stopPropagation();
  //   setLoading(true);
  //   setShowbtns(false);
  //   setscanned(false);

  //   setTimeout(() => {
  //     const result = Math.random() > 0.5; // مؤقت (هيجي من backend بعدين)
  //     setisSafe(result); // ⭐ مهم
  //     setLoading(false);
  //     setscanned(true); // ⭐ مهم
  //   }, 3000);
  // };

  //   button handlers end

  async function handleChange(e) {
    const selectedFiles = e.target.files;
    if (!selectedFiles.length) return;

    const file = selectedFiles[0];
    setFiles([file]);
    setShowbtns(false);
    setLoading(true);
    setDragtext("Uploading file...");

    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await fetch("http://192.168.1.4:3000/upload", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      console.log(data);
      console.log("Status code:", res.status);

      setSessionId(data.sessionId);
      setRiskLevel(data.report.risk_level);
      setSummary(data.summarization);
      setReport(data.report);

      setisSafe(data.report.risk_level === 1 || data.report.risk_level === 2);
      setscanned(true);
      setDragtext("Scan completed");
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }
  function handlenavigate(e) {
    e.preventDefault();
    navigate("/Chat", { state: { summary, sessionId } });
  }
  function handleclick(e) {
    e.preventDefault();
    console.log("🖱 clicking input");
    inputRef.current.click();
  }

  function handledrag(e) {
    e.preventDefault();
    setDragtext("drop your files here ");
  }

  // drop
  async function handledrop(e) {
    e.preventDefault();
    const droppedFiles = e.dataTransfer.files;
    if (!droppedFiles.length) return;

    const file = droppedFiles[0];
    setFiles([file]);
    setDragtext("Uploading file...");
    setShowbtns(false);
    setLoading(true);

    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await fetch("http://192.168.1.4:3000/upload", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      setSessionId(data.sessionId);
      setRiskLevel(data.report.risk_level);
      setSummary(data.summarization);
      setReport(data.report);

      setisSafe(data.report.risk_level === 1 || data.report.risk_level === 2);
      setscanned(true);
      setDragtext("Scan completed");
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  function handledragleave(e) {
    e.preventDefault();
    setDragtext("Drag & drop your files here or click to browse");
  }

  function handleenter(e) {
    e.preventDefault();
    setDragtext("Drop your file here");
  }

  return (
    <div className="homecom">
      <div className="title">
        {" "}
        <PanelLeft /> Home
      </div>
      <div className="home-content">
        {/* <div style={{width:100,height:100 }}>
            <Lottie animationData={water} speed={0.25} loop={true} className="lottie-water" />
        </div> */}
        <div className="options">
          {/* <div className="option upload">
            <Upload size={24} />
            <br />
            upload
          </div> */}
          <div className="option filechat">
            <FileUp size={24} />
            <br /> chat with file
          </div>
          <div className="option folderchat">
            <FolderOpen size={24} />
            <br />
            chat with folder
          </div>
        </div>
        <div
          className={`drag 
  ${loading ? "drag-loading" : ""} 
  ${scanned && isSafe ? "drag-safe" : ""} 
  ${scanned && !isSafe ? "drag-unsafe" : ""} 
  ${scanned ? "no-hover" : ""}
`}
        >
          {scanned && !loading && (
            <div className={`scan-result-text ${isSafe ? "safe" : "unsafe"}`}>
              {isSafe ? (
                <>
                  {" "}
                  <ShieldCheck /> file name shows no signs of a virus or malware
                  signatures
                </>
              ) : (
                <>
                  {" "}
                  <ShieldAlert /> File Contains Malicious Signatures
                </>
              )}
            </div>
          )}

          {!scanned && !loading && showbtns && <div></div>}
          <div
            style={{ cursor: "pointer" }}
            className={`draginner
               ${scanned ? "draginner-small" : ""}
               ${loading ? "innerloading" : ""}`}
            onClick={handleclick}
            onDragOver={handledrag}
            onDrop={handledrop}
            onDragEnter={handleenter}
            onDragLeave={handledragleave}
          >
            {loading && (
              <div className="text-center mt-3">
                <div style={{ position: "relative", width: 100, height: 100 }}>
                  {/* Lottie animation */}
                  <Lottie
                    animationData={water}
                    loop={true}
                    style={{ width: "100%", height: "100%" }}
                  />

                  {/* Gradient overlay */}
                  <div
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      width: "100%",
                      height: "100%",
                      background:
                        "linear-gradient(45deg, #597557, #7C977A, #9EB59D, #CBD9CA)",
                      mixBlendMode: "color", // يحط اللون على الأنيميشن
                      pointerEvents: "none", // يخلي الضغط يروح للـ Lottie
                      borderRadius: "50%", // لو محتاجة شكل دائري
                    }}
                  />
                </div>

                <p>Scanning...</p>
              </div>
            )}
            {/* قبل الـ scan */}
            {!scanned && !loading && (
              <>
                {files.length === 0 && <CloudUpload size={48} color="grey" />}
                <div className="text-center">
                  <div
                    className={`dragtext ${files.length > 0 ? "file-selected" : ""
                      }`}
                  >
                    {dragtext}
                  </div>

                  {/* اسم الملف تحت الجملة */}
                  {files.length > 0 && (
                    <div
                      className="file-name"
                      style={{ marginTop: "8px", fontWeight: "500" }}
                    >
                      {files[0].name.length > 20
                        ? files[0].name.slice(0, 20) + "..." // لو الاسم طويل
                        : files[0].name}
                    </div>
                  )}
                </div>

                {showbtns && (
                  <div className="btns d-flex justify-content-center gap-3">
                    <button
                      type="button"
                      className="cancel-btn"
                      onClick={handleCancel}
                    >
                      cancel
                    </button>
                    {/* <button className="scan-btn" onClick={handleScan}>
                      scan now
                    </button> */}
                  </div>
                )}
              </>
            )}

            {/* بعد الـ scan */}
            {scanned && !loading && (
              <div className="d-flex flex-column align-items-center gap-3">
                <div className="d-flex gap-3">
                  <button className=" another-scan-btn" onClick={handleCancel}>
                    scan another file
                  </button>
                  <button
                    className={`summarize-btn ${!isSafe ? "disabled-btn" : ""}`}
                    onClick={handlenavigate}
                    disabled={!isSafe}
                  >
                    Summarize & Discuss
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {scanned && riskLevel && (
          <div
            style={{
              display: "flex",
              flexDirection: "Column",
              gap: "4px",
              fontWeight: "600",
              fontSize: "18px",
              marginTop: "8px",
            }}
          >
            {riskLevel === 3 ? (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "2px",
                  fontWeight: "600",
                  fontSize: "18px",
                }}
              >
                <div>Risk Level:</div>
                <div style={{ color: "red" }}>High</div>
              </div>
            ) : (
              "Comprehensive Threat Analysis"
            )}
            {report && (
              <a
                href="#"
                onClick={(e) => {
                  e.preventDefault();
                  setShowReport(!showReport);
                }}
                style={{
                  color: "#4F204E",
                  textDecoration: "underline",
                  cursor: "pointer",
                  fontSize: "18px",
                  fontWeight: "600",
                }}
              >
                {showReport ? "Hide report" : "View full report"}
              </a>
            )}
          </div>
        )}

        {showReport && report && (
          <div className="modal-overlay">
            <div className="modal-content">
              {/* Header */}
              <div
                style={{ backgroundColor: "#EAEAEA" }}
                className="modal-header"
              >
                <h3 style={{ color: "#4F204E" }}>Technical Analysis Report</h3>
                <button
                  className="close-btn"
                  onClick={() => setShowReport(false)}
                >
                  <CircleX />
                </button>
              </div>

              {/* Body */}
              <div className="modal-body">
                <pre>{JSON.stringify(report, null, 2)}</pre>
              </div>
            </div>
          </div>
        )}

        {/* input */}
        <input
          type="file"
          ref={inputRef}
          hidden
          onChange={(e) => {
            console.log("📁 file selected", e.target.files);
            handleChange(e);
          }}
        />
      </div>
    </div>
  );
}
