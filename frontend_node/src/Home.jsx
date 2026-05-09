import { useEffect, useRef, useState, useContext, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  PanelLeft,
  ShieldCheck,
  ShieldAlert,
  ChevronRight,
  ChevronLeft,
  FileText,
  FilePlusCorner,
  ChartColumn,
} from "lucide-react";
import Lottie from "lottie-react";
import water from "./assets/water.json";

import { FileContext } from "./FileContext";
import { DragTextContext } from "./DragTextContext";
import { useCategories } from "./useCategories";
import CreateCategoryModal from "./CreateCategoryModal";
import RecentCategories from "./RecentCategories";
import CSVScanBox from "./CSVScanBox";
import ReportModal from "./ReportModal";
import { useQuery } from "@tanstack/react-query";

export default function Home() {
  const navigate = useNavigate();
  const inputRef = useRef(null);
  const accessToken = localStorage.getItem("accessToken");

  const { dragTexts, updateDragText } = useContext(DragTextContext);
  const {
    pdfFiles,
    setPdfFiles,
    csvFiles,
    setCsvFiles,
    recentFiles,
    fetchRecentFiles,
    fetchGeneralFiles,
    optimisticAddFile, // ← NEW
  } = useContext(FileContext);

  const { categories } = useCategories(accessToken);

  const [scanned, setScanned] = useState(false);
  const [showCategoryModal, setShowCategoryModal] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [loading, setLoading] = useState(false);
  const [isSafe, setIsSafe] = useState(null);
  const [riskLevel, setRiskLevel] = useState(null);
  const [report, setReport] = useState(null);
  const [showReport, setShowReport] = useState(false);

  const hasFiles = pdfFiles.length > 0 || csvFiles.length > 0;
  const activeType =
    pdfFiles.length > 0 ? "pdf" : csvFiles.length > 0 ? "csv" : null;

  const allFiles = useMemo(
    () =>
      [...(pdfFiles || []), ...(csvFiles || []), ...(recentFiles || [])].sort(
        (a, b) => new Date(b.createdAt) - new Date(a.createdAt),
      ),
    [pdfFiles, csvFiles, recentFiles],
  );

  function timeAgo(date) {
    const seconds = Math.floor((new Date() - new Date(date)) / 1000);
    const intervals = [
      { label: "y", seconds: 31536000 },
      { label: "mo", seconds: 2592000 },
      { label: "d", seconds: 86400 },
      { label: "h", seconds: 3600 },
      { label: "m", seconds: 60 },
    ];
    for (let i of intervals) {
      const count = Math.floor(seconds / i.seconds);
      if (count > 0) return `${count}${i.label} ago`;
    }
    return "just now";
  }

  // ── Effects ──────────────────────────────────────────────────────────────

  useEffect(() => {
    updateDragText("pdf", "drag & drop your PDF here\nor\n click to browse");
    setScanned(false);
    setIsSafe(null);
    setReport(null);
    setRiskLevel(null);
    setPdfFiles([]);
  }, []);

  useEffect(() => {
    fetchRecentFiles(accessToken);
  }, [accessToken]);

  useEffect(() => {
    const handler = () => fetchRecentFiles(accessToken);
    window.addEventListener("recent-update", handler);
    return () => window.removeEventListener("recent-update", handler);
  }, [accessToken]);

  // ── Upload ────────────────────────────────────────────────────────────────

  async function uploadFile(file) {
    updateDragText("Uploading file...");
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/upload/", {
        method: "POST",
        body: formData,
        headers: { Authorization: `bearer ${accessToken}` },
      });
      const data = await res.json();

      // ── optimistic: appear in sidebar immediately ──────────────────────
      const uploaded = data.pdf || data.file;
      if (uploaded) {
        optimisticAddFile({
          _id: uploaded._id,
          fileName: file.name,
          fileType: "pdf",
          url: uploaded.url || "",
          createdAt: uploaded.createdAt || new Date().toISOString(),
        });
      }

      setPdfFiles([{ _id: uploaded._id, name: file.name, originalFile: file }]);
      updateDragText("pdf", "file selected for scanning");
    } catch (err) {
      console.error("Upload Error:", err);
      updateDragText("pdf", "Upload failed");
    }
  }

  function handleChange(e) {
    const file = e.target.files?.[0];
    if (file) uploadFile(file);
  }
  function handledrop(e) {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file) uploadFile(file);
  }

  // ── Scan ──────────────────────────────────────────────────────────────────

  const handleScan = (e) => {
    e.stopPropagation();
    if (!pdfFiles?.length || loading || scanned) return;
    setShowCategoryModal(true);
    setModalVisible(true);
  };

  async function startScan() {
    if (!pdfFiles?.length) return;
    setLoading(true);
    setScanned(false);

    try {
      const currentFile = pdfFiles[pdfFiles.length - 1];
      const res = await fetch(
        `/api/security/scan/${currentFile._id}`,
        { method: "POST", headers: { Authorization: `bearer ${accessToken}` } },
      );
      const data = await res.json();

      await new Promise((r) => setTimeout(r, 3000));

      setIsSafe(data.fileIsSafe);
      setReport(data.updatedFile);
      setRiskLevel(data.updatedFile?.security?.riskLevel);
      setScanned(true);
      setLoading(false);
      updateDragText("pdf", "Scan completed");
      await fetchRecentFiles(accessToken);
      await fetchGeneralFiles(accessToken);
      window.dispatchEvent(new Event("general-update"));
    } catch (err) {
      console.error("Scan Error:", err);
    }
  }

  // ── Cancel / New Scan ─────────────────────────────────────────────────────

  const handleCancel = (e) => {
    e.stopPropagation();
    setIsSafe(null);
    setScanned(false);
    setPdfFiles([]);
    updateDragText("pdf", "drag & drop your PDF here\nor\n click to browse");
    if (inputRef.current) inputRef.current.value = null;
  };

  const handleNewScan = () => {
    handleCancel({ stopPropagation: () => {} });
    inputRef.current.click();
  };

  function handlenavigate(e) {
    e.preventDefault();
    if (!pdfFiles?.length) return;
    const currentFile = pdfFiles[pdfFiles.length - 1];
    const fileUrl = URL.createObjectURL(currentFile.originalFile);
    navigate("/Chat", {
      state: { fileUrl, fileId: currentFile?._id, accessToken ,fileName: currentFile.originalFile.name},
    });
  }

  function handledrag(e) {
    e.preventDefault();
    updateDragText("pdf", "drop your file here ");
  }
  function handledragleave(e) {
    e.preventDefault();
    updateDragText("pdf", "Drag & drop your CSV here\n or\n click to browse");
  }
  function handleenter(e) {
    e.preventDefault();
    updateDragText("pdf", "Drop your file here");
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="homecom">
      {showCategoryModal && (
        <div className={`modal-wrapper ${modalVisible ? "show" : "hide"}`}>
          <CreateCategoryModal
            categories={categories}
            file={pdfFiles[pdfFiles.length - 1]}
            accessToken={accessToken}
            onClose={() => {
              setShowCategoryModal(false);
              startScan();
            }}
            onSave={() => {
              setShowCategoryModal(false);
              startScan();
            }}
          />
        </div>
      )}

      <div className="title">
        <PanelLeft size={20} />
        <span>Home</span>
      </div>

      <div className="home-content">
        {!scanned && !loading && !hasFiles && <RecentCategories />}

        <div className="boxs">
          {/* ── PDF Box ── */}
          {csvFiles.length === 0 && (
            <div
              className={`drag ${loading ? "drag-loading" : ""} ${scanned ? (isSafe ? "drag-safe" : "drag-unsafe") : ""} ${!scanned && !loading && activeType === "pdf" ? "drag-prescan" : ""} ${scanned ? "no-hover" : ""}`}
            >
              {scanned && !loading && (
                <div
                  className={`scan-result-text ${isSafe ? "safe" : "unsafe"}`}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    marginLeft: "30px",
                  }}
                >
                  {isSafe ? (
                    <>
                      <ShieldCheck size={30} />
                      <span>
                        File name shows no signs of a virus or malware
                        signatures
                      </span>
                    </>
                  ) : (
                    <>
                      <ShieldAlert size={20} />
                      <span>File Contains Malicious Signatures</span>
                    </>
                  )}
                </div>
              )}

              <div
                style={{ cursor: "pointer" }}
                className={`draginner ${scanned ? "draginner-small" : ""} ${loading ? "innerloading" : ""} ${activeType === "pdf" && !scanned && !loading ? "draginner-prescan" : ""}`}
                onClick={() => {
                  if (pdfFiles.length === 0) inputRef.current.click();
                }}
                onDragOver={handledrag}
                onDrop={handledrop}
                onDragEnter={handleenter}
                onDragLeave={handledragleave}
              >
                {!scanned && !loading && pdfFiles.length === 0 && (
                  <div className="initialtext">
                    <div className="fileicon">
                      <FilePlusCorner size={35} />
                      <span>secure PDF analysis</span>
                    </div>
                    <div className="dragtext">{dragTexts.pdf}</div>
                  </div>
                )}

                {pdfFiles.length > 0 && !scanned && !loading && (
                  <>
                    <div className="dragtext">{dragTexts.pdf}</div>
                    <div className="file-name">{pdfFiles[0].name}</div>
                    <div className="btns">
                      <button className="cancel-btn" onClick={handleCancel}>
                        Cancel
                      </button>
                      <button className="scan-btn" onClick={handleScan}>
                        Scan Now
                      </button>
                    </div>
                  </>
                )}

                {loading && (
                  <div style={{ width: 100, height: 100 }}>
                    <Lottie animationData={water} speed={0.5} loop />
                  </div>
                )}

                {scanned && !loading && (
                  <div className="d-flex flex-column align-items-center gap-3">
                    <div className="d-flex gap-3">
                      <button
                        className="another-scan-btn"
                        onClick={handleNewScan}
                      >
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
          )}

          {scanned && riskLevel && (
            <div
              className="comprehensive"
              style={{
                display: "flex",
                flexDirection: "Column",
                gap: "3px",
                fontWeight: "600",
                fontSize: "18px",
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
                  <div style={{ color: "red" }}>HIGH</div>
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
                    color: "#113567",
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

          {showReport && (
            <ReportModal report={report} onClose={() => setShowReport(false)} />
          )}

          {!scanned && !loading && activeType !== "pdf" && (
            <CSVScanBox
              fetchRecent={() => fetchRecentFiles(accessToken)}
              fetchGeneralFiles={() => fetchGeneralFiles(accessToken)}
            />
          )}
        </div>

        {!scanned && !loading && !hasFiles && (
          <div className="recent-content">
            <div className="header">
              <span>recent</span>
              <div className="buttons">
                <button
                  className="scroll-btn left"
                  onClick={() =>
                    document
                      .getElementById("recentRow")
                      .scrollBy({ left: -300, behavior: "smooth" })
                  }
                >
                  <ChevronLeft />
                </button>
                <button
                  className="scroll-btn right"
                  onClick={() =>
                    document
                      .getElementById("recentRow")
                      .scrollBy({ left: 300, behavior: "smooth" })
                  }
                >
                  <ChevronRight />
                </button>
              </div>
            </div>

            {allFiles.length === 0 ? (
              <div style={{ marginRight: "730px" }}>No recent files yet</div>
            ) : (
              <div className="recent-slider" id="recentRow">
                {allFiles.map((file) => {
                  const isCSV =
                    file.fileName?.endsWith(".csv") ||
                    file.type === "csv" ||
                    file.fileType === "csv";
                  return (
                    <div
                      key={file._id}
                      className="recent-item-home"
                      onClick={() => {
                        if (file.url)
                          navigate(isCSV ? "/dashboard" : "/Chat", {
                            state: {
                              fileUrl: file.url,
                              fileId: file._id,
                              accessToken,
                            },
                          });
                      }}
                    >
                      {isCSV ? (
                        <ChartColumn size={18} />
                      ) : (
                        <FileText size={18} />
                      )}
                      <div className="createdAt">
                        <div>{file.fileName}</div>
                        <div className="time">{timeAgo(file.createdAt)}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      <input
        type="file"
        ref={inputRef}
        hidden
        onChange={handleChange}
        accept=".pdf"
      />
    </div>
  );
}
