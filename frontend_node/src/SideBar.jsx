import React, { useState, useRef, useEffect } from "react";
import Drop from "./Drop";
import { useContext } from "react";
import { FileContext } from "./FileContext";
import { NavLink, useNavigate } from "react-router-dom";
import AddCategoryModal from "./AddCategoryModal";
import { AuthContext } from "./AuthContext";
import { DragTextContext } from "./DragTextContext";
import {
  Search,
  Plus,
  Settings,
  Sun,
  LogOut,
  FileText,
  House,
  ChevronDown,
  ChevronRight,
  EllipsisVertical,
  Trash2,
  FileCog,
  LayoutGrid,
} from "lucide-react";
import logo from "./assets/mainlogo.jpg";
import logoo from "./assets/logoo.svg";

export default function Sidebar() {
  const { dragtext, setDragtext } = useContext(DragTextContext);
  const { user } = useContext(AuthContext);
  const GENERAL_CATEGORY_ID = "69dacc95968ba38aadc7bd1c";
  const [generalFiles, setGeneralFiles] = useState([]);
  const navigate = useNavigate();
  const [recent, setRecent] = useState([]);
  const accessToken = localStorage.getItem("accessToken");
  const [openFiles, setOpenFiles] = useState(false);
  const [openCat1, setOpenCat1] = useState(false);
  const [showLogoutModal, setShowLogoutModal] = useState(false);
  const [AddingCategoryModal, setAddingCategoryModal] = useState(false);
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef();
  const { files, setFiles } = useContext(FileContext);
  const [activeFileIndex, setActiveFileIndex] = useState(null); // للـhover
  const [menuOpenIndex, setMenuOpenIndex] = useState(null); // للقائمة المفتوحة
  function openAddCategoryModal() {
    setAddingCategoryModal(true);
  }



  async function handleLogout() {
    const token = localStorage.getItem("accessToken");

    try {
      await fetch("/api/logout", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `bearer ${token}`,
        },
        body: JSON.stringify({
          flag: "current",
        }),
      });
    } catch (err) {
      console.log("logout API failed, but continuing...");
    }

    // مهم جدًا حتى لو الـ API فشل
    localStorage.removeItem("accessToken");
    window.location.href = "/login";
  }

  useEffect(() => {
    async function fetchRecent() {
      try {
        const res = await fetch("/api/upload/recent", {
          headers: { Authorization: `bearer ${accessToken}` },
        });
        const data = await res.json();
        if (data.files) setRecent(data.files);
      } catch (err) {
        console.error(err);
      }
    }
    fetchRecent();
  }, []);
  // 👇 يقفل لما تدوسي برا
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);
  const fileInputRef = useRef(); // 👈 ده المهم

  // 👇 لما تضغطي على الزرار
  const handleUploadClick = () => {
    fileInputRef.current.click();
  };

  // 👇 لما تختاري فايل
  const handleFileChange = async (e) => {
    setDragtext("Uploading file...");

    const file = e.target.files[0];
    if (file) {
      const formData = new FormData();
      formData.append("file", file);

      try {
        const res = await fetch("/api/upload/", {
          method: "POST",
          body: formData,
          headers: {
            Authorization: `bearer ${accessToken}`,
          },
        });
        const data = await res.json();
        console.log(data);

        setFiles((prev) => [
          ...prev,
          { _id: data.pdf._id, name: file.name, originalFile: file },
        ]);
        setDragtext("File uploaded and ready for scan");
      } catch (err) {
        console.error(err);
      }
    }
    e.target.value = null; // 👈 مهم
  };
  return (
    <div className="sidebar">
      {showLogoutModal && (
        <div
          className="modal-overlay-l"
          onClick={() => setShowLogoutModal(false)}
        >
          <div className="modal-l" onClick={(e) => e.stopPropagation()}>
            <h3>Are you sure you want to log out?</h3>

            {/* <p>
        Log out of your account? You’ll need to sign in again to continue.
      </p> */}

            <div className="modal-actions-l">
              <button className="logout-btn-l" onClick={handleLogout}>
                Log out
              </button>

              <button
                className="cancel-btn-l"
                onClick={() => setShowLogoutModal(false)}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
      <input
        type="file"
        ref={fileInputRef}
        style={{ display: "none" }}
        onChange={handleFileChange}
      />
      <div className="sidecontent">
        <div className="logo-box">
          <img src={logoo} alt="Logo" className="logo" />
        </div>
        <div className="links">
          <div className="user">
            <div
              className={`username ${open ? "active" : ""}`}
              onClick={() => setOpen(!open)}
            >
              <div> {user?.userName || user?.email?.split("@")[0]}</div>
              <div>
                {open ? <ChevronDown size={17} /> : <ChevronRight size={17} />}
              </div>
            </div>

            <div
              onClick={() => navigate("/search")}
              style={{ cursor: "pointer" }}
            >
              {" "}
              <Search size={17} />
            </div>
          </div>
          {open && (
            <div className="dropdown">
              <span style={{ fontWeight: "600" }}>
                {user?.userName || user?.email?.split("@")[0]}
              </span>{" "}
              <span style={{ fontWeight: "600", color: "#666666" }}>
                {user.email}
              </span>
              <hr />
              <div className="settings">
                <Settings size={17} />
                <span>Settings</span>
              </div>
              <div className="settings">
                <Sun size={17} />
                <span>theme</span>
              </div>
              <div
                className="settings"
                onClick={() => setShowLogoutModal(true)}
              >
                <LogOut size={17} />
                <span>Logout</span>
              </div>
            </div>
          )}
          <NavLink to="/home" className="home-link">
            <House size={18} />
            Home
          </NavLink>{" "}
          <NavLink to="/categories" className="category-link">
            <LayoutGrid size={18} />
            categories
          </NavLink>{" "}
        </div>
        <div className="files">
          <h4 className="private">my collections</h4>
          <div
            style={{
              marginLeft: "14px",
              paddingTop: "16px",
            }}
            className="collection"
          >
            <div
              className="files-header"
              onClick={() => setOpenFiles(!openFiles)}
              style={{
                display: "flex",
                alignItems: "center",
                cursor: "pointer",
                marginBottom: "10px",
                // padding: "8px",
              }}
            >
              <ChevronRight
                size={18}
                style={{
                  transform: openFiles ? "rotate(90deg)" : "rotate(0deg)",
                  transition: "0.3s",
                }}
              />
              <span>All Files</span>
            </div>

            {/* المحتوى */}
            {openFiles && (
              <div className="files-content">
                {[...recent, ...files].length === 0
                  ? ""
                  : [...recent, ...files].map((file, index) => {
                    const name =
                      file.name ||
                      file.fileName ||
                      (file.url && file.url.split("\\").pop());
                    const shortName =
                      name.length > 10 ? name.slice(0, 10) + "..." : name;

                    const hovered = activeFileIndex === index;
                    const menuOpen = menuOpenIndex === index;

                    return (
                      <div
                        key={file.url || file.name || index}
                        className="file-item"
                        style={{ position: "relative", cursor: "pointer" }}
                        onMouseEnter={() => setActiveFileIndex(index)}
                        onMouseLeave={() => setActiveFileIndex(null)}
                        onClick={() =>
                          setMenuOpenIndex(menuOpen ? null : index)
                        }
                      >
                        <FileText size={20} />
                        {shortName}

                        {/* أيقونة تظهر عند hover */}
                        {hovered && !menuOpen && (
                          <span
                            style={{
                              position: "absolute",
                              top: "0",
                              right: "0",
                              color: "#000",
                            }}
                          >
                            <EllipsisVertical size={17} />
                          </span>
                        )}

                        {/* قائمة الخيارات تظهر عند الضغط */}
                        {menuOpen && (
                          <div
                            style={{
                              width: "170px",
                              height: "80px",
                              position: "absolute",
                              top: "100%",
                              left: "0",
                              background: "white",

                              border: "1px solid #ccc",
                              borderRadius: "16px",
                              padding: "5px",
                              zIndex: 100,
                            }}
                          >
                            {/* <div
                  style={{ padding: "5px 10px", cursor: "pointer" }}
                  onClick={() => {
                    console.log("Rename", file.name);
                    setMenuOpenIndex(null);
                  }}
                >
                  Rename
                </div> */}
                            <div
                              style={{
                                background: "#DDE4EE",
                                height: "28px",
                                cursor: "pointer",
                                display: "flex",
                                alignItems: "center",
                                borderRadius: "16px",
                                marginBottom: "5px ",
                                padding: "5px 10px",
                              }}
                              onClick={() => {
                                console.log("Rename", file.name);
                                setMenuOpenIndex(null);
                              }}
                            >
                              <Plus
                                size={15}
                                style={{ marginRight: "5px" }}
                              />
                              <span> add to category</span>
                            </div>

                            <div
                              style={{
                                padding: "5px 10px",
                                cursor: "pointer",
                                color: "red",
                                display: "flex",
                                alignItems: "center",
                                borderRadius: "16px",
                                marginBottom: "5px ",
                                padding: "5px 10px",
                              }}
                              onClick={async () => {
                                const fileId = file._id || file.id;

                                if (!fileId) {
                                  console.warn("No fileId found", file);
                                  return;
                                }

                                try {
                                  const accessToken =
                                    localStorage.getItem("accessToken");

                                  const res = await fetch(
                                    `/api/upload/delete/${fileId}`,
                                    {
                                      method: "DELETE",
                                      headers: {
                                        Authorization: `bearer ${accessToken}`,
                                      },
                                    },
                                  );
                                  const data = await res.json(); // 👈 ده المهم
                                  console.log("Response:", data);

                                  if (!res.ok)
                                    throw new Error("Delete failed");

                                  console.log("Deleted", fileId);

                                  // تحديث UI
                                  setFiles((prev) =>
                                    prev.filter(
                                      (f) => (f._id || f.id) !== fileId,
                                    ),
                                  );
                                  setRecent((prev) =>
                                    prev.filter(
                                      (f) => (f._id || f.id) !== fileId,
                                    ),
                                  );

                                  setMenuOpenIndex(null);
                                } catch (err) {
                                  console.error(err);
                                }
                              }}
                            >
                              <Trash2
                                size={15}
                                style={{ marginRight: "5px" }}
                              />
                              <span> delete</span>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}

                <button className="upload-btn" onClick={handleUploadClick}>
                  <Plus size={16} />
                  Upload File
                </button>
              </div>
            )}
            <div
              className="files-header"
              onClick={() => setOpenCat1(!openCat1)}
              style={{
                display: "flex",
                alignItems: "center",
                cursor: "pointer",
                marginBottom: "10px",
              }}
            >
              <ChevronRight
                size={18}
                style={{
                  transform: openCat1 ? "rotate(90deg)" : "rotate(0deg)",
                  transition: "0.3s",
                }}
              />
              <span>general category</span>
            </div>
            {openCat1 && (
              <div className="files-content">
                {generalFiles.length === 0
                  ? ""
                  : generalFiles.map((file) => (
                    <div key={file._id} className="file-item">
                      <FileText size={16} />
                      {file.fileName}
                    </div>
                  ))}

                <button className="upload-to-btn" onClick={handleUploadClick}>
                  <Plus size={16} />
                  Upload File
                </button>
              </div>
            )}

            {/* <button className="add-category-btn" onClick={openAddCategoryModal}>
              <Plus size={16} />
              add category
            </button> */}

            {AddingCategoryModal && (
              <AddCategoryModal onClose={() => setAddingCategoryModal(false)} />
            )}
          </div>

          {/* {files.length === 0 ? (<>
 
  <span className="file-item">
    <FileText size={16} />
      File_Name
  </span></>
) : (
  files.map((file, index) => (
    <span key={index} className="file-item">
      <FileText size={16} />
      {file.name}
    </span>
  ))
)}
  
  <button className="upload-btn" onClick={handleUploadClick}>
    <Plus color="#666666" size={16} />
    Upload File
  </button> */}
        </div>
      </div>
    </div>
  );
}
