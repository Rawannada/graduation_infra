import React, { useState, useRef, useEffect } from "react";
import Drop from "./Drop";
import { useContext } from "react";
import { FileContext } from "./FileContext";
import { NavLink } from "react-router-dom";
import {
  Search,
  Plus,
  LibraryBig,
  FileText,
  House,
  ChevronDown,
  ChevronRight,
   EllipsisVertical,
   Trash2,
    FileCog,
} from "lucide-react";
import logo from "./assets/mainlogo.jpg";

export default function Sidebar() {
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef();
const { files, setFiles } = useContext(FileContext);
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

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // 👇 لما تضغطي على الزرار
  const handleUploadClick = () => {
    fileInputRef.current.click();
  };

  // 👇 لما تختاري فايل
  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
     setFiles((prev) => [...prev, file]);
    }
      e.target.value = null; // 👈 مهم
  };
  return (

    <div className="sidebar">
       <input
            type="file"
            ref={fileInputRef}
            style={{ display: "none" }}
            onChange={handleFileChange}
          />
      <div className="sidecontent">
        <div className="logo-box">
          <img src={logo} alt="Logo" className="logo" />
        </div>
        <div className="links">
          <div
            className={`username ${open ? "active" : ""}`}
            onClick={() => setOpen(!open)}
          >
            User Name
            {open ? <ChevronDown size={17} /> : <ChevronRight size={17} />}
          </div>
          {open && (
            <div className="dropdown">
              <span>username</span>
              <span>use@gmail.com</span>
              <hr />

              <span>Settings</span>
              <span>theme</span>
              <span>Logout</span>
            </div>
          )}
          <NavLink to="/home" className="home-link">
            <House size={18} />
            Home
          </NavLink>{" "}
        </div>
        <div className="files">
  <h4 className="private">Private</h4>
  
  {files.length === 0 ? (<>
 
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
  </button>
</div>
      </div>
    </div>
  );
}
