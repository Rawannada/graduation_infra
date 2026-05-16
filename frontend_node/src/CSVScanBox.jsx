import { useEffect, useRef, useState, useContext } from "react";
import { useNavigate } from "react-router-dom";
import { ShieldCheck, ShieldAlert, ChartColumn } from "lucide-react";
import { FileContext } from "./FileContext";
import { DragTextContext } from "./DragTextContext";
import { useCategories } from "./useCategories";
import CreateCategoryModal from "./CreateCategoryModal";
import ReportModal from "./ReportModal";
import Lottie from "lottie-react";
import water from "./assets/water.json";

export default function CSVScanBox({ fetchRecent, fetchGeneralFiles }) {
  const navigate = useNavigate();
  const inputRef = useRef(null);
  const accessToken = localStorage.getItem("accessToken");

  const { csvFiles, setCsvFiles, optimisticAddFile } = useContext(FileContext); // ← NEW
  const { dragTexts, updateDragText } = useContext(DragTextContext);
  const { categories } = useCategories(accessToken);

  const [scanned, setScanned] = useState(false);
  const [loading, setLoading] = useState(false);
  const [isSafe, setIsSafe] = useState(null);
  const [riskLevel, setRiskLevel] = useState(null);
  const [report, setReport] = useState(null);
  const [showReport, setShowReport] = useState(false);
  const [showCategoryModal, setShowCategoryModal] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);

  useEffect(() => {
    updateDragText("csv", "Drag & drop your CSV here\n or\n click to browse");
    setScanned(false);
    setCsvFiles([]);
  }, []);

  // ── Upload ──────────────────────────────────────────────────────────────

  async function uploadFile(file) {
    updateDragText("Uploading CSV...");
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/upload/CSV", {
        method: "POST",
        body: formData,
        headers: { Authorization: `bearer ${accessToken}` },
      });
      const data = await res.json();
      console.log("Upload response:", data);
      // ── optimistic: appear in sidebar immediately ──────────────────────
      const uploaded = data.CSV || data.file;
      if (uploaded) {
        optimisticAddFile({
          _id: uploaded._id,
          fileName: file.name,
          fileType: "csv",
          url: uploaded.url || "",
          createdAt: uploaded.createdAt || new Date().toISOString(),
        });
      }

      setCsvFiles([{ _id: uploaded._id, name: file.name, originalFile: file }]);

      updateDragText("csv", "CSV selected for scanning");
    } catch (err) {
      console.error(err);
      updateDragText("csv", "Upload failed");
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

  // ── Scan ────────────────────────────────────────────────────────────────
  function handleenter(e) {
    e.preventDefault();
    updateDragText("csv", "Drop your file here");
  }
  function handleleave(e) {
    e.preventDefault();
    updateDragText("csv", "Drag & drop your CSV here\n or\n click to browse");
  }
  function handledrag(e) {
    e.preventDefault();
    updateDragText("csv", "drop your file here ");
  }

  function handleScan(e) {
    e.stopPropagation();
    if (!csvFiles?.length || loading || scanned) return;
    setShowCategoryModal(true);
    setModalVisible(true);
  }

  async function startScan() {
    if (!csvFiles?.length) return;
    const fileId = csvFiles[csvFiles.length - 1]?._id;
    setLoading(true);

    try {
      const res = await fetch(`/api/security/scan/${fileId}`, {
        method: "POST",
        headers: { Authorization: `bearer ${accessToken}` },
      });
      const data = await res.json();

      await new Promise((r) => setTimeout(r, 3000));

      if (res.ok) {
        setIsSafe(data.fileIsSafe);
        setRiskLevel(data.updatedFile?.security?.riskLevel || "unknown");
        setScanned(true);
        setReport(data.updatedFile);
        updateDragText("csv", "Scan completed");
        await fetchRecent();
        await fetchGeneralFiles();
        window.dispatchEvent(new Event("general-update"));
      } else {
        updateDragText("csv", "Scan failed");
      }
    } catch (err) {
      console.error("Scan Error:", err);
      updateDragText("csv", "Scan error");
    }
    setLoading(false);
  }

  const handleCancel = (e) => {
    e.stopPropagation();
    setIsSafe(null);
    setScanned(false);
    setCsvFiles([]);
    updateDragText("csv", "Drag & drop your CSV here\n or\n click to browse");
    if (inputRef.current) inputRef.current.value = null;
  };

  function handlenavigate(e) {
    e.preventDefault();
    if (!csvFiles?.length) return;
    const currentFile = csvFiles[csvFiles.length - 1];
    const fileUrl = URL.createObjectURL(currentFile.originalFile);
    navigate("/CSVColumns", {
      state: {
        fileUrl,
        fileId: currentFile?._id,
        accessToken,
        fileName: currentFile?.name,
      },
    });
  }

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <>
      {showCategoryModal && (
        <div className={`modal-wrapper ${modalVisible ? "show" : "hide"}`}>
          <CreateCategoryModal
            categories={categories}
            file={csvFiles[csvFiles.length - 1]}
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

      <input
        type="file"
        ref={inputRef}
        onChange={handleChange}
        hidden
        accept=".csv"
      />

      <div
        className={`drag ${loading ? "drag-loading" : ""} ${scanned && isSafe ? "drag-safe" : ""} ${scanned && !isSafe ? "drag-unsafe" : ""} ${!scanned && !loading && csvFiles.length > 0 ? "drag-prescan" : ""} ${scanned ? "no-hover" : ""}`}
      >
        {scanned && riskLevel && (
          <div
            className="comprehensivee"
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
                  File name shows no signs of a virus or malware signatures
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
          className={`draginner ${scanned ? "draginner-small" : ""} ${loading ? "innerloading" : ""} ${csvFiles.length > 0 && !scanned && !loading ? "draginner-prescan" : ""}`}
          onClick={() => csvFiles.length === 0 && inputRef.current.click()}
          onDragOver={handledrag}
          onDrop={handledrop}
          onDragEnter={handleenter}
          onDragLeave={handleleave}
        >
          {loading && (
            <div style={{ width: 100, height: 100 }}>
              <Lottie animationData={water} speed={0.5} loop />
            </div>
          )}

          {!scanned && !loading && csvFiles.length === 0 && (
            <div className="initialtext">
              <div className="fileicon">
                <ChartColumn size={35} />
                <span>Secure CSV Analysis</span>
              </div>
              <div className="dragtext">{dragTexts.csv}</div>
            </div>
          )}

          {!scanned && !loading && csvFiles.length > 0 && (
            <>
              <div className="dragtext">{dragTexts.csv}</div>
              <div className="file-name">{csvFiles[0].name}</div>
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

          {scanned && !loading && (
            <div className="d-flex flex-column align-items-center gap-3">
              <div className="d-flex gap-3">
                <button
                  className="another-scan-btn"
                  onClick={() => {
                    handleCancel({ stopPropagation: () => { } });
                    inputRef.current.click();
                  }}
                >
                  scan another file
                </button>
                <button
                  className={`summarize-btn ${!isSafe ? "disabled-btn" : ""}`}
                  onClick={handlenavigate}
                  disabled={!isSafe}
                >
                  Select Columns & Visualize
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
