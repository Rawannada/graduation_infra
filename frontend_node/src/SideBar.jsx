import { useState, useRef, useEffect, useContext } from "react";
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
  LayoutGrid,
  ChartColumn,
} from "lucide-react";
import logoo from "./assets/logoo.svg";

export default function Sidebar() {
  const { setDragtext } = useContext(DragTextContext);
  const { user } = useContext(AuthContext);
  const navigate = useNavigate();
  const accessToken = localStorage.getItem("accessToken");

  const {
    pdfFiles,
    setPdfFiles,
    csvFiles,
    setCsvFiles,
    recentFiles,
    setRecentFiles,
    fetchRecentFiles,
    fetchGeneralFiles,
    categories,
    categoryFiles,
    fetchCategories,
    fetchCategoryFiles,
    optimisticAddFileToCategory,
    optimisticRemoveFile, // ← NEW
  } = useContext(FileContext);

  const [openSections, setOpenSections] = useState({});
  const [openFiles, setOpenFiles] = useState(false);
  const [showLogoutModal, setShowLogoutModal] = useState(false);
  const [addingCategoryModal, setAddingCategoryModal] = useState(false);
  const [open, setOpen] = useState(false);
  const [activeFileIndex, setActiveFileIndex] = useState(null);
  const [menuOpenIndex, setMenuOpenIndex] = useState(null);
  const [uploadTargetCategory, setUploadTargetCategory] = useState(null);

  const dropdownRef = useRef();
  const fileInputRef = useRef();
  const catFileInputRef = useRef();

  // ── Bootstrap ──────────────────────────────────────────────────────────

  useEffect(() => {
    fetchRecentFiles(accessToken);
    fetchCategories(accessToken);
  }, [accessToken]);

  useEffect(() => {
    fetchRecentFiles(accessToken);
  }, [pdfFiles, csvFiles]);

  useEffect(() => {
    const onRecent = () => fetchRecentFiles(accessToken);
    const onGeneral = () => fetchGeneralFiles(accessToken);
    const onCategories = () => fetchCategories(accessToken);
    window.addEventListener("recent-update", onRecent);
    window.addEventListener("general-update", onGeneral);
    window.addEventListener("categories-update", onCategories);
    return () => {
      window.removeEventListener("recent-update", onRecent);
      window.removeEventListener("general-update", onGeneral);
      window.removeEventListener("categories-update", onCategories);
    };
  }, [accessToken, fetchRecentFiles, fetchGeneralFiles, fetchCategories]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target))
        setOpen(false);
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // ── Helpers ────────────────────────────────────────────────────────────

  function toggleSection(id) {
    setOpenSections((prev) => {
      const willOpen = !prev[id];
      if (willOpen && !categoryFiles[id]) fetchCategoryFiles(accessToken, id);
      return { ...prev, [id]: willOpen };
    });
  }

  // ── Logout ─────────────────────────────────────────────────────────────

  async function handleLogout() {
    const token = localStorage.getItem("accessToken");
    try {
      await fetch("/api/logout", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `bearer ${token}`,
        },
        body: JSON.stringify({ flag: "current" }),
      });
    } catch {
      /* continue */
    }
    localStorage.removeItem("accessToken");
    window.location.href = "/login";
  }

  // ── Upload inside a category ───────────────────────────────────────────

  const handleCategoryUploadClick = (categoryId) => {
    setUploadTargetCategory(categoryId);
    catFileInputRef.current.value = null;
    catFileInputRef.current.click();
  };

  const handleCategoryFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const targetId = uploadTargetCategory;
    if (!targetId) return;

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(
        `/api/upload/addFile/${targetId}`,
        {
          method: "POST",
          body: formData,
          headers: { Authorization: `bearer ${accessToken}` },
        },
      );
      const data = await res.json();

      if (res.ok) {
        const uploaded = data.file || data.pdf || data.CSV;
        if (uploaded) {
          optimisticAddFileToCategory(targetId, {
            _id: uploaded._id,
            fileName: file.name,
            fileType: uploaded.fileType || "pdf",
            url: uploaded.url || "",
            createdAt: uploaded.createdAt || new Date().toISOString(),
          });
        } else {
          fetchCategoryFiles(accessToken, targetId);
        }
        window.dispatchEvent(new Event("recent-update"));
      }
    } catch (err) {
      console.error(err);
    }

    e.target.value = null;
    setUploadTargetCategory(null);
  };

  // ── Delete file ────────────────────────────────────────────────────────

  // async function handleDeleteFile(file) {
  //   const fileId = file._id || file.id;
  //   if (!fileId) return;

  //   // ── optimistic: remove from ALL lists instantly ──────────────────────
  //   optimisticRemoveFile(fileId);

  //   // also clean pdfFiles / csvFiles state
  //   if (file.fileType === "csv" || file.type === "csv") {
  //     setCsvFiles((prev) => prev.filter((f) => (f._id || f.id) !== fileId));
  //   } else {
  //     setPdfFiles((prev) => prev.filter((f) => (f._id || f.id) !== fileId));
  //   }
  //   setMenuOpenIndex(null);

  //   // fire API in background
  //   try {
  //     const res = await fetch(`/api/upload/delete/${fileId}`, {
  //       method: "DELETE",
  //       headers: { Authorization: `bearer ${accessToken}` },
  //     });
  //     if (!res.ok) {
  //       // rollback: re-fetch everything
  //       fetchRecentFiles(accessToken);
  //       fetchGeneralFiles(accessToken);
  //     }
  //   } catch (err) {
  //     console.error(err);
  //     fetchRecentFiles(accessToken);
  //     fetchGeneralFiles(accessToken);
  //   }
  // }
  // async function handleDeleteFile(file) {
  //   const fileId = file._id || file.id;
  //   if (!fileId) return;

  //   // 1. close the menu first
  //   setMenuOpenIndex(null);

  //   // 2. wait one tick so React re-renders the closed menu before mutating state
  //   await new Promise((r) => setTimeout(r, 0));

  //   // 3. optimistic: remove from ALL lists instantly
  //   optimisticRemoveFile(fileId);

  //   // 4. clean pdfFiles / csvFiles state
  //   if (file.fileType === "csv" || file.type === "csv") {
  //     setCsvFiles((prev) => prev.filter((f) => (f._id || f.id) !== fileId));
  //   } else {
  //     setPdfFiles((prev) => prev.filter((f) => (f._id || f.id) !== fileId));
  //   }

  //   // 5. fire API in background
  //   try {
  //     const res = await fetch(`/api/upload/delete/${fileId}`, {
  //       method: "DELETE",
  //       headers: { Authorization: `bearer ${accessToken}` },
  //     });
  //     if (!res.ok) {
  //       fetchRecentFiles(accessToken);
  //       fetchGeneralFiles(accessToken);
  //     }
  //   } catch (err) {
  //     console.error(err);
  //     fetchRecentFiles(accessToken);
  //     fetchGeneralFiles(accessToken);
  //   }
  // }
  // async function handleDeleteFile(file) {
  //     const fileId = file._id || file.id;
  //     if (!fileId) return;

  //     try {
  //       const res = await fetch(`/api/upload/delete/${fileId}`, {
  //         method: "DELETE",
  //         headers: { Authorization: `bearer ${accessToken}` },
  //       });
  //       if (!res.ok) throw new Error("Delete failed");

  //       setRecentFiles((prev) => prev.filter((f) => (f._id || f.id) !== fileId));
  //       if (file.fileType === "csv" || file.type === "csv") {
  //         setCsvFiles((prev) => prev.filter((f) => (f._id || f.id) !== fileId));
  //       } else {
  //         setPdfFiles((prev) => prev.filter((f) => (f._id || f.id) !== fileId));
  //       }
  //       window.dispatchEvent(new Event("recent-update"));
  //       setMenuOpenIndex(null);
  //     } catch (err) { console.error(err); }
  //   }

  async function handleDeleteFile(file) {
    const fileId = file._id || file.id;
    if (!fileId) return;

    // optimistic UI
    optimisticRemoveFile(fileId);
    setMenuOpenIndex(null);

    try {
      const res = await fetch(`/api/upload/delete/${fileId}`, {
        method: "DELETE",
        headers: { Authorization: `bearer ${accessToken}` },
      });

      if (!res.ok) throw new Error();
    } catch (err) {
      console.error(err);

      // rollback
      fetchRecentFiles(accessToken);
      fetchGeneralFiles(accessToken);
    }
  }
  function handleLogoClick() {
    navigate("/home");
   
  }

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <div className="sidebar">
      {showLogoutModal && (
        <div
          className="modal-overlay-l"
          onClick={() => setShowLogoutModal(false)}
        >
          <div className="modal-l" onClick={(e) => e.stopPropagation()}>
            <h3>Are you sure you want to log out?</h3>
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

      <input type="file" ref={fileInputRef} style={{ display: "none" }} />
      <input
        type="file"
        ref={catFileInputRef}
        style={{ display: "none" }}
        onChange={handleCategoryFileChange}
      />

      <div className="sidecontent">
        <div className="logo-box">
          <img
            src={logoo}
            alt="Logo"
            className="logo"
            onClick={handleLogoClick}
          />
        </div>

        <div className="links">
          <div className="user">
            <div
              className={`username ${open ? "active" : ""}`}
              onClick={() => setOpen(!open)}
            >
              <div>{user?.userName}</div>
              <div>
                {open ? <ChevronDown size={17} /> : <ChevronRight size={17} />}
              </div>
            </div>
            <div
              onClick={() => navigate("/search")}
              style={{ cursor: "pointer" }}
            >
              <Search size={17} />
            </div>
          </div>

          {open && (
            <div className="dropdown" ref={dropdownRef}>
              <span style={{ fontWeight: "600" }}>
                {user?.userName || user?.email?.split("@")[0]}
              </span>
              <span style={{ fontWeight: "600", color: "#666666" }}>
                {user?.email}
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
          </NavLink>
          <NavLink to="/categories" className="category-link">
            <LayoutGrid size={18} />
            categories
          </NavLink>
        </div>

        <div className="files">
          <h4 className="private">my collections</h4>
          <div
            style={{ marginLeft: "14px", paddingTop: "16px" }}
            className="collection"
          >
            {/* ── All Files ── */}
            <div
              className="files-header"
              onClick={() => setOpenFiles(!openFiles)}
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
                  transform: openFiles ? "rotate(90deg)" : "rotate(0deg)",
                  transition: "0.3s",
                }}
              />
              <span>All Files</span>
            </div>

            {openFiles && (
              <div className="files-content">
                {recentFiles.length === 0 && (
                  <div
                    style={{
                      fontSize: "12px",
                      color: "#999",
                      marginBottom: "6px",
                      paddingLeft: "4px",
                    }}
                  >
                    No files yet
                  </div>
                )}
                {recentFiles.map((file, index) => {
                  const isCSV =
                    file.fileName?.endsWith(".csv") ||
                    file.type === "csv" ||
                    file.fileType === "csv";
                  const nameToShow =
                    file.fileName || file.name || "Untitled File";
                  const shortName =
                    nameToShow.length > 15
                      ? nameToShow.slice(0, 15) + "..."
                      : nameToShow;
                  const hovered = activeFileIndex === index;
                  const menuOpen = menuOpenIndex === index;

                  return (
                    <div
                      key={file._id || index}
                      className="file-item"
                      style={{ position: "relative", cursor: "pointer" }}
                      onMouseEnter={() => setActiveFileIndex(index)}
                      onMouseLeave={() => setActiveFileIndex(null)}
                      onClick={() => {
                        if (menuOpenIndex !== null) return;
                        navigate(isCSV ? "/dashboard" : "/chat", {
                          state: {
                            fileUrl: file.url,
                            fileId: file._id,
                            accessToken,
                          },
                        });
                      }}
                    >
                      {isCSV ? (
                        <ChartColumn size={20} />
                      ) : (
                        <FileText size={20} />
                      )}
                      {shortName}

                      {hovered && !menuOpen && (
                        <span
                          style={{
                            position: "absolute",
                            top: 0,
                            right: 0,
                            color: "#000",
                          }}
                          onClick={(e) => {
                            e.stopPropagation();
                            setMenuOpenIndex(
                              menuOpenIndex === index ? null : index,
                            );
                          }}
                        >
                          <EllipsisVertical size={17} />
                        </span>
                      )}

                      {menuOpen && (
                        <div
                          style={{
                            width: "170px",
                            position: "absolute",
                            top: "100%",
                            left: 0,
                            background: "white",
                            border: "1px solid #ccc",
                            borderRadius: "16px",
                            padding: "5px",
                            zIndex: 100,
                          }}
                        >
                          <div
                            style={{
                              background: "#DDE4EE",
                              height: "28px",
                              cursor: "pointer",
                              display: "flex",
                              alignItems: "center",
                              borderRadius: "16px",
                              marginBottom: "5px",
                              padding: "5px 10px",
                            }}
                            onClick={() => setMenuOpenIndex(null)}
                          >
                            <Plus size={15} style={{ marginRight: "5px" }} />
                            <span>add to category</span>
                          </div>
                          <div
                            style={{
                              padding: "5px 10px",
                              cursor: "pointer",
                              color: "red",
                              display: "flex",
                              alignItems: "center",
                              borderRadius: "16px",
                              marginBottom: "5px",
                            }}
                            onClick={() => handleDeleteFile(file)}
                          >
                            <Trash2 size={15} style={{ marginRight: "5px" }} />
                            <span>delete</span>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* ── Dynamic Categories ── */}
            {categories.map((cat) => {
              const isOpen = openSections[cat._id] ?? false;
              const catFiles = categoryFiles[cat._id] || [];

              return (
                <div key={cat._id}>
                  <div
                    className="files-header"
                    onClick={() => toggleSection(cat._id)}
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
                        transform: isOpen ? "rotate(90deg)" : "rotate(0deg)",
                        transition: "0.3s",
                      }}
                    />
                    <span>{cat.categoryName || cat.name}</span>
                  </div>

                  {isOpen && (
                    <div className="files-content">
                      {catFiles.length === 0 && (
                        <div
                          style={{
                            fontSize: "12px",
                            color: "#999",
                            marginBottom: "6px",
                            paddingLeft: "4px",
                          }}
                        >
                          
                        </div>
                      )}
                     {catFiles.map((file, index) => {
  const isCSV =
    file.fileName?.endsWith(".csv") ||
    file.type === "csv" ||
    file.fileType === "csv";

  const nameToShow =
    file.fileName || file.name || "Untitled File";

  const shortName =
    nameToShow.length > 15
      ? nameToShow.slice(0, 15) + "..."
      : nameToShow;

  return (
    <div
      key={file._id || index}
      className="file-item"
      style={{ cursor: "pointer" }}
      onClick={() => {
        navigate(isCSV ? "/dashboard" : "/chat", {
          state: {
            fileUrl: file.url,
            fileId: file._id,
            accessToken,
          },
        });
      }}
    >
      {isCSV ? (
        <ChartColumn size={20} />
      ) : (
        <FileText size={20} />
      )}

      {shortName}
    </div>
  );
})}
                      {/* <button */}
                        {/* className="upload-to-btn" */}
                        {/* onClick={() => handleCategoryUploadClick(cat._id)} */}
                      {/* > */}
                        {/* <Plus size={16} /> */}
                        {/* Upload File */}
                      {/* </button> */}
                    </div>
                  )}
                </div>
              );
            })}

            {addingCategoryModal && (
              <AddCategoryModal onClose={() => setAddingCategoryModal(false)} 
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
