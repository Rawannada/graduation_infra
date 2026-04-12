import { useEffect, useState ,useRef} from "react";
import { PanelLeft, FileText, Plus } from "lucide-react";
import { useParams } from "react-router-dom";
import "./Categories.css";
import axios from "axios";

export default function CategoryFiles() {
  const { categoryId, categoryName } = useParams();
  const [files, setFiles] = useState([]);
const fileRef = useRef(null);
  const accessToken = localStorage.getItem("accessToken");

  const handleUploadFile = async (file, categoryId) => {
  const accessToken = localStorage.getItem("accessToken");

  const formData = new FormData();
  formData.append("file", file); // مهم جدًا الاسم يكون "file"

  try {
    const res = await axios.post(
      `http://localhost:3000/upload/addFile/${categoryId}`,
      formData,
      {
        headers: {
          Authorization: `bearer ${accessToken}`,
          "Content-Type": "multipart/form-data",
        },
      }
    );
setFiles((prev) => [...prev, res.data.file]);
    console.log("Upload success:", res.data);
  } catch (error) {
    console.log("Upload error:", error.response?.data || error.message);
  }
};
  useEffect(() => {
    async function fetchFiles() {
      try {
        const res = await fetch(
          `http://localhost:3000/upload/files/${categoryId}`,
          {
            method: "GET",
            headers: {
              Authorization: `bearer ${accessToken}`,
            },
          },
        );

        const data = await res.json();
        console.log(data);

if (!res.ok || !data.filesWithUrls) {
  setFiles([]);
  return;
}
        setFiles(data.filesWithUrls || []);
      } catch (err) {
        console.error(err);
      }
    }

    fetchFiles();
  }, [categoryId]);

  return (
    <div className="files-page">
      <div className="title">
        <PanelLeft size={20} />
        <span>{categoryName}</span>
      </div>
      <div className="files-grid">
        {files?.length === 0 ? (
          <p className="empty">No files found</p>
        ) : (
          files.map((file) => (
            <div className="file-card" key={file._id}>
              <FileText  size={20} />

              <div style={{fontWeight:"400"}}>{file.fileName || "Unnamed file"}</div>
            </div>
          ))
        )}
        <div className="add-file">
  <button className="add" onClick={() => fileRef.current.click()}>
    <Plus size={20} />
  </button>

  <span>add file</span>

  <input
    type="file"
    ref={fileRef}
    style={{ display: "none" }}
    onChange={(e) => {
      const file = e.target.files[0];
      if (file) {
        handleUploadFile(file, categoryId);
      }
    }}
  />
</div>
      </div>
    </div>
  );
}
