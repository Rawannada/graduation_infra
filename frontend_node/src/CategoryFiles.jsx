
import { useEffect, useState, useRef, useContext } from "react";
import { PanelLeft, FileText, Plus } from "lucide-react";
import { useParams } from "react-router-dom";
import "./Categories.css";
import axios from "axios";
import { FileContext } from "./FileContext";

export default function CategoryFiles() {
  const { categoryId, categoryName } = useParams();
  const [files, setFiles]            = useState([]);
  const fileRef                      = useRef(null);
  const accessToken                  = localStorage.getItem("accessToken");

  // ── pull the optimistic helper from shared context ─────────────────────
  const { optimisticAddFileToCategory } = useContext(FileContext);

  // ── Fetch files for this category ─────────────────────────────────────

  useEffect(() => {
    async function fetchFiles() {
      try {
        const res  = await fetch(
          `/api/upload/files/${categoryId}`,
          { method: "GET", headers: { Authorization: `bearer ${accessToken}` } }
        );
        const data = await res.json();

        if (!res.ok || !data.filesWithUrls) { setFiles([]); return; }
        setFiles(data.filesWithUrls || []);
      } catch (err) { console.error(err); }
    }
    fetchFiles();
  }, [categoryId]);

  // ── Upload ─────────────────────────────────────────────────────────────

  const handleUploadFile = async (file) => {
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await axios.post(
        `/api/upload/addFile/${categoryId}`,
        formData,
        {
          headers: {
            Authorization: `bearer ${accessToken}`,
            "Content-Type": "multipart/form-data",
          },
        }
      );

      const uploaded = res.data.file || res.data.pdf || res.data.CSV;

      if (uploaded) {
        const fileObj = {
          _id:       uploaded._id,
          fileName:  file.name,
          fileType:  uploaded.fileType || "pdf",
          url:       uploaded.url || "",
          createdAt: uploaded.createdAt || new Date().toISOString(),
        };

        // 1. update THIS page instantly
        setFiles((prev) =>
          prev.find((f) => f._id === fileObj._id) ? prev : [...prev, fileObj]
        );

        // 2. update Sidebar instantly (shared context)
        optimisticAddFileToCategory(categoryId, fileObj);

      } else {
        // fallback: just add with local file name
        setFiles((prev) => [...prev, { _id: Date.now(), fileName: file.name }]);
      }

    } catch (error) {
      console.log("Upload error:", error.response?.data || error.message);
    }
  };

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <div className="files-page">
      <div className="title">
        <PanelLeft size={20}/>
        <span>{categoryName}</span>
      </div>

      <div className="files-grid">
        {files?.length === 0 ? (
          <p className="empty">No files found</p>
        ) : (
          files.map((file) => (
            <div className="file-card" key={file._id}>
              <FileText size={20}/>
              <div style={{ fontWeight:"400" }}>{file.fileName || "Unnamed file"}</div>
            </div>
          ))
        )}

        <div className="add-file">
          <button className="add" onClick={() => fileRef.current.click()}>
            <Plus size={20}/>
          </button>
          <span>add file</span>
          <input
            type="file"
            ref={fileRef}
            style={{ display:"none" }}
            onChange={(e) => {
              const file = e.target.files[0];
              if (file) handleUploadFile(file);
            }}
          />
        </div>
      </div>
    </div>
  );
}
