import { useState } from "react";
import {
  ChevronRight,
  Plus,
  FolderOpen,
  CircleCheck,
  CirclePlus,
} from "lucide-react";
import "./Categories.css";

export default function CreateCategoryModal({
  onClose,
  onSave,
  file,
  accessToken,
  categories = [],
}) {
  const [selectedCategoryId, setSelectedCategoryId] = useState("");
  const [selectedOptionType, setSelectedOptionType] = useState("general");
  const [newCategoryName, setNewCategoryName] = useState("");
  const [selectedOption, setSelectedOption] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const colors = [
    "#FFE3E3",
    "#BCCABD",
    "#E3D2C0",
    "#BFD0FD",
    "#FAF6B9",
    "#F7E3FF",
  ];

  async function handleSave() {
    if (!file || isLoading) return;

    let payload = null;
    if (selectedOptionType === "general") {
      payload = { useGeneral: true };
    } else if (selectedOptionType === "existing") {
      if (!selectedCategoryId) return alert("Please select a category");
      payload = { categoryId: selectedCategoryId };
    } else if (selectedOptionType === "new") {
      if (!newCategoryName.trim()) return alert("Please enter category name");
      payload = { newCategoryName: newCategoryName.trim() };
    }
    if (!payload) {
      alert("Please select an option");
      return;
    }

    try {
      setIsLoading(true);
      const res = await fetch(
        `http://localhost:3000/upload/addCategory/${file._id}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `bearer ${accessToken}`,
          },
          body: JSON.stringify(payload),
        },
      );

      if (res.ok) {
        onSave();
        onClose();
      } else {
        const errorData = await res.json();
        alert(`Error: ${errorData.message || "Something went wrong"}`);
      }
    } catch (error) {
      alert("Network error, please try again.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div style={styles.overlay}>
      <div style={styles.modal}>
        <div style={styles.header}>
          <h2>Select Destination</h2>
          <button className="close-modal" onClick={onClose} disabled={isLoading}>
            <CirclePlus style={{ transform: "rotate(90deg)" }} size={28} />
          </button>
        </div>

        <div className="description">Processing in progress... You can categorize it now</div>

        <div className="options" onClick={() => setSelectedOption(!selectedOption)}>
          <span>Category options</span>
          <ChevronRight
            size={18}
            style={{
              transform: selectedOption ? "rotate(90deg)" : "rotate(0deg)",
              transition: "0.3s",
            }}
          />
        </div>

        {/* الحاوية الرئيسية للقائمة */}
        <div className={`category-list ${selectedOption ? "open" : ""}`}>
          
          {/* 1. خيار General - ثابت لا يتحرك */}
          <div
            className={`general-option ${selectedOptionType === "general" ? "selected" : ""}`}
            onClick={() => {
              setSelectedOptionType("general");
              setSelectedCategoryId("");
              setNewCategoryName("");
            }}
          >
            <div className="option-left">
              <div className="icon"><FolderOpen size={18} /></div>
              <span>keep in general</span>
            </div>
            {selectedOptionType === "general" && <CircleCheck size={20} color="#4CAF50" />}
          </div>

          {/* 2. الجزء القابل للتمرير (التصنيفات الحالية فقط) */}
          <div style={styles.scrollArea} className="scroll">
            {categories.map((cat, index) => (
              <div
                key={cat._id}
                className={`general-option ${selectedOptionType === "existing" && selectedCategoryId === cat._id ? "selected" : ""}`}
                onClick={() => {
                  setSelectedOptionType("existing");
                  setSelectedCategoryId(cat._id);
                  setNewCategoryName("");
                }}
              >
                <div className="option-left">
                  <div className="icon colored" style={{ background: colors[index % colors.length] }}>
                    {cat.code}
                  </div>
                  <span>{cat.categoryName}</span>
                </div>
                {selectedOptionType === "existing" && selectedCategoryId === cat._id && <CircleCheck size={20} color="#4CAF50" />}
              </div>
            ))}
          </div>

          {/* 3. خيار إضافة تصنيف جديد - ثابت في الأسفل */}
          <div
            className={`add-new-category ${selectedOptionType === "new" ? "selected" : ""}`}
            onClick={() => {
              setSelectedOptionType("new");
              setSelectedCategoryId("");
            }}
          >
            <Plus size={16} />
            <span>add new category</span>
          </div>

          {selectedOptionType === "new" && (
            <input
              type="text"
              autoFocus
              placeholder="Enter name..."
              value={newCategoryName}
              onChange={(e) => setNewCategoryName(e.target.value)}
              className="input"
            />
          )}
        </div>

        <div style={styles.footer}>
          <button className="cancel" onClick={onClose} disabled={isLoading}>Cancel</button>
          <button className="save" onClick={handleSave} disabled={isLoading}>
            {isLoading ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}

const styles = {
  overlay: {
    position: "fixed",
    top: 0,
    left: 0,
    width: "100%",
    height: "100%",
    background: "rgba(0,0,0,0.4)",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    zIndex: 1000,
  },
  modal: {
    background: "#fff",
    padding: "16px 20px",
    borderRadius: "16px",
    width: "484px",
  },
  header: {
    color: "#113567",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  footer: {
    display: "flex",
    justifyContent: "space-between",
    marginTop: "20px",
  },
scrollArea: { 
    maxHeight: "200px", // حدد الارتفاع اللي تحبه للجزء اللي بيعمل سكرول
    overflowY: "auto",
  }
};
